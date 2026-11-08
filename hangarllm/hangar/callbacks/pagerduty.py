"""
PagerDuty alerting for HangarLLM.

Opens a PagerDuty incident (Events API v2) when

* the number of failed LLM calls inside a sliding window reaches
  ``failure_threshold`` (default 60 failures / 60 s), or
* the number of requests that are still running after
  ``hanging_threshold_seconds`` reaches ``hanging_threshold_fails`` inside
  ``hanging_threshold_window_seconds`` (default 60 hanging requests / 600 s).

Config::

    general_settings:
      alerting: ["pagerduty"]
      alerting_args:
        failure_threshold: 10
        failure_threshold_window_seconds: 60
        hanging_threshold_seconds: 300
        hanging_threshold_fails: 5
        hanging_threshold_window_seconds: 600

The routing key is read from ``PAGERDUTY_API_KEY`` (or ``PAGERDUTY_ROUTING_KEY``).
"""

import asyncio
import os
from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from typing import Final, Literal

from hangarllm._logging import verbose_logger
from hangarllm.integrations.custom_logger import CustomLogger
from hangarllm.llms.custom_httpx.http_handler import get_async_httpx_client, httpxSpecialProvider
from hangarllm.proxy._types import UserAPIKeyAuth
from hangarllm.types.integrations.pagerduty import AlertingConfig, PagerDutyInternalEvent

PAGERDUTY_EVENTS_URL: Final = "https://events.pagerduty.com/v2/enqueue"

_DEFAULTS: Final[AlertingConfig] = {
    "failure_threshold": 60,
    "failure_threshold_window_seconds": 60,
    "hanging_threshold_seconds": 600,
    "hanging_threshold_fails": 60,
    "hanging_threshold_window_seconds": 600,
}
_MAX_TRACKED_CALLS: Final = 10_000
_RECENT_ERRORS_IN_ALERT: Final = 10


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PagerDutyAlerting(CustomLogger):
    def __init__(self, alerting_args: AlertingConfig | dict | None = None, **kwargs: object) -> None:
        super().__init__()
        routing_key: Final = os.getenv("PAGERDUTY_API_KEY") or os.getenv("PAGERDUTY_ROUTING_KEY")
        if not routing_key:
            raise ValueError("PagerDuty alerting needs PAGERDUTY_API_KEY (your Events API v2 routing key)")
        self.api_key: str = routing_key
        merged: dict[str, object] = dict(_DEFAULTS)  # mutable-ok: merged once at init
        if alerting_args:
            merged.update({k: v for k, v in dict(alerting_args).items() if v is not None})
        self.alerting_args: AlertingConfig = merged  # type: ignore[assignment]
        self._failure_events: deque[PagerDutyInternalEvent] = deque()
        self._hanging_events: deque[PagerDutyInternalEvent] = deque()
        self._finished_calls: OrderedDict[str, None] = OrderedDict()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ helpers
    def _arg(self, name: str) -> float:
        value: Final = self.alerting_args.get(name, _DEFAULTS.get(name))  # type: ignore[call-overload]
        return float(value) if isinstance(value, (int, float)) else float(_DEFAULTS[name])  # type: ignore[literal-required]

    def _mark_finished(self, call_id: object) -> None:
        if not isinstance(call_id, str):
            return
        self._finished_calls[call_id] = None
        while len(self._finished_calls) > _MAX_TRACKED_CALLS:
            self._finished_calls.popitem(last=False)

    @staticmethod
    def _prune(events: "deque[PagerDutyInternalEvent]", window_seconds: float) -> None:
        cutoff: Final = _now() - timedelta(seconds=window_seconds)
        while events and events[0]["timestamp"] < cutoff:
            events.popleft()

    @staticmethod
    def _serialisable(event: PagerDutyInternalEvent) -> dict[str, object]:
        return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in event.items()}

    # ------------------------------------------------------------------ failures
    async def async_log_failure_event(self, kwargs, response_obj, start_time, end_time):
        kwargs = kwargs or {}
        self._mark_finished(kwargs.get("hangarllm_call_id"))
        payload: Final = kwargs.get("standard_logging_object") or {}
        error_info: Final = payload.get("error_information") or {}
        metadata: Final = payload.get("metadata") or {}
        event: Final = PagerDutyInternalEvent(
            failure_event_type="failed_response",
            timestamp=_now(),
            error_class=error_info.get("error_class"),
            error_code=error_info.get("error_code"),
            error_llm_provider=error_info.get("llm_provider"),
            user_api_key_hash=metadata.get("user_api_key_hash"),
            user_api_key_alias=metadata.get("user_api_key_alias"),
            user_api_key_team_id=metadata.get("user_api_key_team_id"),
            user_api_key_team_alias=metadata.get("user_api_key_team_alias"),
            user_api_key_user_id=metadata.get("user_api_key_user_id"),
        )
        window: Final = self._arg("failure_threshold_window_seconds")
        async with self._lock:
            self._failure_events.append(event)
            self._prune(self._failure_events, window)
            count = len(self._failure_events)
            if count < self._arg("failure_threshold"):
                return
            recent = [self._serialisable(e) for e in list(self._failure_events)[-_RECENT_ERRORS_IN_ALERT:]]
            self._failure_events.clear()
        await self.send_alert(
            summary=f"High LLM API Failure Rate: {count} in the last {int(window)} seconds.",
            severity="critical",
            custom_details={"recent_errors": recent},
        )

    async def async_log_success_event(self, kwargs, response_obj, start_time, end_time):
        self._mark_finished((kwargs or {}).get("hangarllm_call_id"))

    # ------------------------------------------------------------------ hanging
    async def async_pre_call_hook(self, user_api_key_dict: UserAPIKeyAuth, cache, data: dict, call_type):
        call_id: Final = data.get("hangarllm_call_id")
        if isinstance(call_id, str):
            asyncio.create_task(self._watch_for_hang(call_id, data, user_api_key_dict))

    async def _watch_for_hang(self, call_id: str, data: dict, user_api_key_dict: UserAPIKeyAuth) -> None:
        await asyncio.sleep(self._arg("hanging_threshold_seconds"))
        if call_id in self._finished_calls:
            return
        await self.hanging_response_handler(
            {"request_id": data.get("hangarllm_call_id"), "hangarllm_call_id": call_id, "model": data.get("model")},
            user_api_key_dict,
        )

    async def hanging_response_handler(self, request_data: dict, user_api_key_dict: UserAPIKeyAuth) -> None:
        event: Final = PagerDutyInternalEvent(
            failure_event_type="hanging_response",
            timestamp=_now(),
            error_class="HangingRequest",
            error_code=None,
            error_llm_provider=None,
            user_api_key_hash=user_api_key_dict.api_key,
            user_api_key_alias=user_api_key_dict.key_alias,
            user_api_key_team_id=user_api_key_dict.team_id,
            user_api_key_team_alias=user_api_key_dict.team_alias,
            user_api_key_user_id=user_api_key_dict.user_id,
        )
        window: Final = self._arg("hanging_threshold_window_seconds")
        async with self._lock:
            self._hanging_events.append(event)
            self._prune(self._hanging_events, window)
            count = len(self._hanging_events)
            if count < self._arg("hanging_threshold_fails"):
                return
            recent = [self._serialisable(e) for e in list(self._hanging_events)[-_RECENT_ERRORS_IN_ALERT:]]
            self._hanging_events.clear()
        await self.send_alert(
            summary=f"High Number of Hanging LLM Requests: {count} in the last {int(window)} seconds.",
            severity="critical",
            custom_details={"recent_errors": recent, "last_request": request_data},
        )

    # ------------------------------------------------------------------ transport
    async def send_alert(
        self,
        summary: str,
        severity: Literal["critical", "warning", "error", "info"] = "critical",
        custom_details: dict | None = None,
    ) -> None:
        body: Final = {
            "routing_key": self.api_key,
            "event_action": "trigger",
            "payload": {
                "summary": summary,
                "severity": severity,
                "source": "HangarLLM Proxy",
                "timestamp": _now().isoformat(),
                "component": "hangarllm-gateway",
                "custom_details": custom_details or {},
            },
            "client": "HangarLLM",
        }
        try:
            client: Final = get_async_httpx_client(llm_provider=httpxSpecialProvider.LoggingCallback)
            response: Final = await client.post(url=PAGERDUTY_EVENTS_URL, json=body)
            verbose_logger.debug("HangarLLM PagerDuty alert sent: status=%s", response.status_code)
        except Exception as e:  # noqa: BLE001 - alerting must never break traffic
            verbose_logger.error("HangarLLM: failed to send PagerDuty alert - %s", e)


HangarPagerDutyAlerting = PagerDutyAlerting
