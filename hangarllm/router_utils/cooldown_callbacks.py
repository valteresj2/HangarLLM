"""
Callbacks triggered on cooling down deployments
"""

import copy
from typing import TYPE_CHECKING, Any, Final

import hangarllm
from hangarllm._logging import verbose_logger
from hangarllm.router_deprecated import renamed_router_param

if TYPE_CHECKING:
    from hangarllm.integrations.prometheus import PrometheusLogger
    from hangarllm.router_api import RoutingContext
else:
    PrometheusLogger = Any


@renamed_router_param("hangarllm_router_instance")
async def router_cooldown_event_callback(
    ctx: "RoutingContext",
    deployment_id: str,
    exception_status: str | int,
    cooldown_time: float | None,
):
    """
    Callback triggered when a deployment is put into cooldown by hangarllm

    - Updates deployment state on Prometheus
    - Increments cooldown metric for deployment on Prometheus
    """
    verbose_logger.debug("In router_cooldown_event_callback - updating prometheus")
    _deployment: Final = ctx.registry().deployment(deployment_id)
    if _deployment is None:
        verbose_logger.warning(
            "in router_cooldown_event_callback but _deployment is None for deployment_id=%s. Doing nothing",
            deployment_id,
        )
        return
    _hangarllm_params: Final = _deployment.hangarllm_params
    temp_hangarllm_params = copy.deepcopy(_hangarllm_params)
    temp_hangarllm_params = dict(temp_hangarllm_params)
    _model_name: Final = _deployment.model_name or ""
    _api_base: Final = hangarllm.get_api_base(model=_model_name, optional_params=temp_hangarllm_params) or ""
    model_info: Final = _deployment["model_info"]
    model_id: Final = model_info.id

    hangarllm_model_name: Final = temp_hangarllm_params.get("model") or ""
    llm_provider = ""
    try:
        _, llm_provider, _, _ = hangarllm.get_llm_provider(
            model=hangarllm_model_name,
            custom_llm_provider=temp_hangarllm_params.get("custom_llm_provider"),
        )
    except Exception:
        pass

    # get the prometheus logger from in memory loggers
    prometheusLogger: Final[PrometheusLogger | None] = get_prometheus_logger_from_callbacks()

    if prometheusLogger is not None:
        prometheusLogger.set_deployment_complete_outage(
            hangarllm_model_name=_model_name,
            model_id=model_id,
            api_base=_api_base,
            api_provider=llm_provider,
        )

        prometheusLogger.increment_deployment_cooled_down(
            hangarllm_model_name=_model_name,
            model_id=model_id,
            api_base=_api_base,
            api_provider=llm_provider,
            exception_status=str(exception_status),
        )

    return


def get_prometheus_logger_from_callbacks() -> PrometheusLogger | None:
    """
    Checks if prometheus is a initalized callback, if yes returns it
    """
    from hangarllm.integrations.prometheus import PrometheusLogger

    if PrometheusLogger is None:
        return None

    for _callback in hangarllm._async_success_callback:
        if isinstance(_callback, PrometheusLogger):
            return _callback
    for global_callback in hangarllm.callbacks:
        if isinstance(global_callback, PrometheusLogger):
            return global_callback

    return None


_get_prometheus_logger_from_callbacks = get_prometheus_logger_from_callbacks
