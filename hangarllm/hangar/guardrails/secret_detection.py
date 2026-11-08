"""
Secret detection / redaction guardrail ("hide_secrets").

Scans prompts, chat messages (text and content parts), ``input`` / ``prompt``
fields and tool-call arguments for credentials and replaces each hit with
``[REDACTED]`` before the request leaves the gateway.

Detection is pure-regex (no third-party scanner) and covers ~50 credential
formats plus ``<credential-like key> = <value>`` assignments in code, shell,
YAML and JSON. Tune it with ``detect_secrets_config``::

    guardrails:
      - guardrail_name: hide-secrets
        hangarllm_params:
          guardrail: hide-secrets
          mode: pre_call
          default_on: true
          detect_secrets_config:
            disabled_patterns: ["jwt"]           # turn individual detectors off
            custom_patterns:                       # add your own
              internal_token: "itk_[A-Za-z0-9]{32}"

A key can opt out with ``metadata: {"hide_secrets": false}`` (admins only).
"""

import hangarllm
import os
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from hangarllm._logging import verbose_proxy_logger
from hangarllm.integrations.custom_guardrail import CustomGuardrail
from hangarllm.types.guardrails import GuardrailEventHooks

REDACTED: Final = "[REDACTED]"


@dataclass(frozen=True, slots=True)
class SecretPattern:
    name: str
    regex: re.Pattern[str]
    group: int = 0  # which capture group is the secret (0 = whole match)


def _p(name: str, pattern: str, group: int = 0, flags: int = 0) -> SecretPattern:
    return SecretPattern(name=name, regex=re.compile(pattern, flags), group=group)


_CRED_KEY: Final = (
    r"(?:[A-Za-z0-9_\-]*?(?:password|passwd|pwd|passphrase|secret|api[_\-]?key|apikey|access[_\-]?key"
    r"|token|auth[_\-]?token|access[_\-]?token|refresh[_\-]?token|bearer[_\-]?token|client[_\-]?secret|private[_\-]?key"
    r"|secret[_\-]?key|credentials?)[A-Za-z0-9_\-]*)"
)

DEFAULT_PATTERNS: Final[tuple[SecretPattern, ...]] = (
    _p(
        "private_key_block",
        r"-----BEGIN (?:[A-Z]+ )?PRIVATE KEY(?: BLOCK)?-----[\s\S]+?-----END (?:[A-Z]+ )?PRIVATE KEY(?: BLOCK)?-----",
    ),
    _p("aws_access_key_id", r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b"),
    _p("aws_secret_access_key", r"(?i)aws.{0,20}?(?:secret|key).{0,20}?['\"=:\s]+([A-Za-z0-9/+]{40})\b", 1),
    _p("anthropic_api_key", r"\bsk-ant-(?:api|admin)\d{2}-[A-Za-z0-9_\-]{80,}\b"),
    _p("openai_api_key", r"\bsk-(?:proj-|svcacct-|admin-)?[A-Za-z0-9_\-]{20,}T3BlbkFJ[A-Za-z0-9_\-]{20,}\b"),
    _p("openai_project_key", r"\bsk-(?:proj|svcacct|admin)-[A-Za-z0-9_\-]{40,}\b"),
    _p("hangar_virtual_key", r"\b(?:sk-[A-Za-z0-9]{22}|hgr_[0-9A-Za-z]{38})\b"),
    _p("google_api_key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    _p("google_oauth_client_secret", r"\bGOCSPX-[A-Za-z0-9_\-]{28}\b"),
    _p("gcp_service_account", r"\"private_key_id\"\s*:\s*\"([a-f0-9]{40})\"", 1),
    _p("azure_storage_key", r"(?i)AccountKey=([A-Za-z0-9+/=]{60,})", 1),
    _p("azure_sas_signature", r"(?i)[?&]sig=([A-Za-z0-9%+/=]{30,})", 1),
    _p("github_token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,255}\b"),
    _p("github_fine_grained_pat", r"\bgithub_pat_[A-Za-z0-9_]{60,255}\b"),
    _p("gitlab_token", r"\bgl(?:pat|dt|ptt|rt|cbt|imt|ft|oas)-[A-Za-z0-9_\-]{20,}\b"),
    _p("bitbucket_app_password", r"\bATBB[A-Za-z0-9_\-]{28,}\b"),
    _p("slack_token", r"\bxox[abposr]-[A-Za-z0-9\-]{10,}\b"),
    _p("slack_webhook", r"https://hooks\.slack\.com/services/T[A-Za-z0-9_]+/B[A-Za-z0-9_]+/[A-Za-z0-9_]+"),
    _p("discord_webhook", r"https://(?:ptb\.|canary\.)?discord(?:app)?\.com/api/webhooks/\d+/[A-Za-z0-9_\-]+"),
    _p("teams_webhook", r"https://[a-z0-9\-]+\.webhook\.office\.com/webhookb2/[A-Za-z0-9@\-/]+"),
    _p("telegram_bot_token", r"\b\d{8,10}:AA[A-Za-z0-9_\-]{33}\b"),
    _p("stripe_key", r"\b(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{20,}\b"),
    _p("square_token", r"\b(?:sq0atp|sq0csp|EAAA)[A-Za-z0-9_\-]{22,}\b"),
    _p("paypal_braintree_token", r"\baccess_token\$production\$[a-z0-9]{16}\$[a-f0-9]{32}\b"),
    _p("shopify_token", r"\bshp(?:at|ca|pa|ss)_[a-fA-F0-9]{32}\b"),
    _p("twilio_api_key", r"\bSK[0-9a-fA-F]{32}\b"),
    _p("sendgrid_api_key", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b"),
    _p("mailgun_api_key", r"\bkey-[0-9a-zA-Z]{32}\b"),
    _p("mailchimp_api_key", r"\b[0-9a-f]{32}-us\d{1,2}\b"),
    _p("npm_token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    _p("pypi_token", r"\bpypi-AgEIcHlwaS5vcmc[A-Za-z0-9_\-]{50,}\b"),
    _p("huggingface_token", r"\bhf_[A-Za-z0-9]{34,}\b"),
    _p("databricks_token", r"\bdapi[a-f0-9]{32}(?:-\d)?\b"),
    _p("digitalocean_token", r"\bdo[opr]_v1_[a-f0-9]{64}\b"),
    _p("hashicorp_vault_token", r"\bhv[sbr]\.[A-Za-z0-9_\-]{24,}\b"),
    _p("doppler_token", r"\bdp\.(?:pt|st|sa|ct|scim|audit)\.[A-Za-z0-9]{40,44}\b"),
    _p("grafana_token", r"\bgl(?:c|sa)_[A-Za-z0-9_+/=\-]{32,}\b"),
    _p("new_relic_key", r"\bNR(?:AK|II|JS)-[A-Z0-9]{27}\b"),
    _p("linear_api_key", r"\blin_api_[A-Za-z0-9]{40}\b"),
    _p("postman_api_key", r"\bPMAK-[a-f0-9]{24}-[a-f0-9]{34}\b"),
    _p("atlassian_api_token", r"\bATATT3[A-Za-z0-9_\-=]{180,}\b"),
    _p("dropbox_token", r"\bsl\.[A-Za-z0-9_\-]{130,}\b"),
    _p("figma_token", r"\bfig[dhu]_[A-Za-z0-9_\-]{40,}\b"),
    _p("planetscale_token", r"\bpscale_(?:tkn|pw|oauth)_[A-Za-z0-9_\-.]{32,64}\b"),
    _p("netlify_token", r"\bnfp_[A-Za-z0-9]{36}\b"),
    _p("cloudflare_api_token", r"(?i)cloudflare.{0,20}?['\"=:\s]+([A-Za-z0-9_\-]{40})\b", 1),
    _p("jwt", r"\beyJ[A-Za-z0-9_\-]{8,}\.eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{10,}\b"),
    _p("basic_auth_in_url", r"\b[a-zA-Z][a-zA-Z0-9+.\-]*://[^\s:/@\"']+:([^\s/@\"']{3,})@", 1),
    _p("bearer_header", r"(?i)\bauthorization\s*:\s*(?:bearer|basic|token)\s+([A-Za-z0-9_\-.=+/]{16,})", 1),
    # credential-like key followed by a value: KEY=value, key: value, "key": "value"
    _p(
        "credential_assignment",
        r"(?i)" + _CRED_KEY + r"[\"']?\s*(?::|=|:=|=>)\s*(?:>\s*\n\s*)?[\"']?([^\s\"',;&|)}\]]{6,})",
        1,
    ),
)

_BENIGN_VALUES: Final = frozenset(
    {"null", "none", "true", "false", "undefined", "changeme", "redacted", "[redacted]", "password", "example"}
)


def _looks_like_placeholder(value: str) -> bool:
    lowered: Final = value.strip("\"'").lower()
    return (
        lowered.replace(".", "").isdigit()  # counts and limits such as max_tokens=4096
        or lowered in _BENIGN_VALUES
        or lowered.startswith(("$", "{{", "<", "os.environ", "process.env", "env.", "${"))
        or set(lowered) <= {"*", "x", "."}
    )


class SecretScanner:
    def __init__(self, config: Mapping[str, object] | None = None) -> None:
        config = config or {}
        disabled_raw: Final = config.get("disabled_patterns") or ()
        disabled: Final = (
            {d for d in disabled_raw if isinstance(d, str)} if isinstance(disabled_raw, Sequence) else set()
        )
        enabled_raw: Final = config.get("plugins_used") or config.get("enabled_patterns")
        enabled: Final = (
            {e.get("name") if isinstance(e, Mapping) else e for e in enabled_raw}
            if isinstance(enabled_raw, Sequence) and not isinstance(enabled_raw, str)
            else None
        )
        patterns: list[SecretPattern] = [  # mutable-ok: built once per guardrail
            p for p in DEFAULT_PATTERNS if p.name not in disabled and (enabled is None or p.name in enabled)
        ]
        custom: Final = config.get("custom_patterns")
        if isinstance(custom, Mapping):
            for name, regex in custom.items():
                if isinstance(name, str) and isinstance(regex, str):
                    patterns.append(_p(name, regex))
        self.patterns: tuple[SecretPattern, ...] = tuple(patterns)

    def find(self, text: str) -> list[tuple[str, int, int]]:
        """(pattern_name, start, end) spans of secret values; overlapping spans merged, longest first."""
        spans: list[tuple[str, int, int]] = []  # mutable-ok: collected hits
        for pattern in self.patterns:
            for match in pattern.regex.finditer(text):
                start, end = match.span(pattern.group)
                if start < 0 or end <= start:
                    continue
                if pattern.name == "credential_assignment" and _looks_like_placeholder(text[start:end]):
                    continue
                spans.append((pattern.name, start, end))
        spans.sort(key=lambda s: (s[1], -(s[2] - s[1])))
        merged: list[tuple[str, int, int]] = []  # mutable-ok: non-overlapping result
        for name, start, end in spans:
            if merged and start < merged[-1][2]:
                prev = merged[-1]
                merged[-1] = (prev[0], prev[1], max(prev[2], end))
                continue
            merged.append((name, start, end))
        return merged

    def redact(self, text: str) -> tuple[str, list[str]]:
        hits: Final = self.find(text)
        if not hits:
            return text, []
        out: list[str] = []  # mutable-ok: string builder
        cursor = 0
        for _, start, end in hits:
            out.append(text[cursor:start])
            out.append(REDACTED)
            cursor = end
        out.append(text[cursor:])
        return "".join(out), [name for name, _, _ in hits]


class HangarSecretDetection(CustomGuardrail):
    def __init__(
        self,
        detect_secrets_config: Mapping[str, object] | None = None,
        event_hook: object = None,
        guardrail_name: str | None = None,
        default_on: bool = False,
        **kwargs: object,
    ) -> None:
        self.scanner: SecretScanner = SecretScanner(detect_secrets_config)
        super().__init__(
            guardrail_name=guardrail_name or "hide_secrets",
            supported_event_hooks=[GuardrailEventHooks.pre_call, GuardrailEventHooks.during_call],
            event_hook=event_hook or GuardrailEventHooks.pre_call,  # type: ignore[arg-type]
            default_on=default_on if guardrail_name else True,
            **kwargs,
        )

    # -------------------------------------------------------------- public API
    def scan_message_for_secrets(self, text: str) -> list[str]:
        return [text[s:e] for _, s, e in self.scanner.find(text)]

    def redact_text(self, text: str) -> str:
        return self.scanner.redact(text)[0]

    def redact_tool_payload(self, payload: object) -> object:
        """Recursively redact a decoded JSON tool payload (dict / list / str)."""
        if isinstance(payload, str):
            return self.redact_text(payload)
        if isinstance(payload, Mapping):
            out: dict[object, object] = {}  # mutable-ok: rebuilt payload
            for key, value in payload.items():
                if isinstance(value, str) and isinstance(key, str):
                    # scan "key=value" so credential-keyed values are caught, then keep only the value part
                    probe = f"{key}={value}"
                    redacted_probe = self.redact_text(probe)
                    out[key] = redacted_probe[len(key) + 1 :] if redacted_probe.startswith(f"{key}=") else REDACTED
                else:
                    out[key] = self.redact_tool_payload(value)
            return out
        if isinstance(payload, list):
            return [self.redact_tool_payload(item) for item in payload]
        return payload

    # -------------------------------------------------------------- request walking
    def _redact_json_string(self, raw: str) -> str:
        try:
            decoded = json.loads(raw)
        except (TypeError, ValueError):
            return self.redact_text(raw)
        return json.dumps(self.redact_tool_payload(decoded))

    def _redact_content(self, content: object, found: list[str]) -> object:
        if isinstance(content, str):
            redacted, names = self.scanner.redact(content)
            found.extend(names)
            return redacted
        if isinstance(content, list):
            return [self._redact_content(part, found) for part in content]
        if isinstance(content, dict):
            part: dict[str, object] = dict(content)  # mutable-ok: rewritten part
            for field in ("text", "content", "input", "arguments", "query", "output"):
                if field not in part:
                    continue
                value = part[field]
                if field == "arguments" and isinstance(value, str):
                    new = self._redact_json_string(value)
                    if new != value:
                        found.append("tool_arguments")
                    part[field] = new
                elif isinstance(value, (dict, list)) and field in ("input", "arguments"):
                    new_obj = self.redact_tool_payload(value)
                    if new_obj != value:
                        found.append("tool_input")
                    part[field] = new_obj
                else:
                    part[field] = self._redact_content(value, found)
            if isinstance(part.get("action"), dict):
                part["action"] = self._redact_content(part["action"], found)
            if isinstance(part.get("function"), dict):
                part["function"] = self._redact_content(part["function"], found)
            return part
        return content

    def redact_request(self, data: dict) -> list[str]:
        found: list[str] = []  # mutable-ok: names of detectors that fired
        messages = data.get("messages")
        if isinstance(messages, list):
            new_messages = []
            for message in messages:
                if not isinstance(message, dict):
                    new_messages.append(message)
                    continue
                msg = dict(message)
                if "content" in msg:
                    msg["content"] = self._redact_content(msg["content"], found)
                if isinstance(msg.get("tool_calls"), list):
                    msg["tool_calls"] = [self._redact_content(tc, found) for tc in msg["tool_calls"]]
                if isinstance(msg.get("function_call"), dict):
                    msg["function_call"] = self._redact_content(msg["function_call"], found)
                new_messages.append(msg)
            data["messages"] = new_messages
        for field in ("prompt", "input", "instructions", "system", "query"):
            if field in data and isinstance(data[field], (str, list, dict)):
                data[field] = self._redact_content(data[field], found)
        return found

    @staticmethod
    def _key_opted_out(user_api_key_dict: object) -> bool:
        metadata: Final = getattr(user_api_key_dict, "metadata", None) or {}
        permissions: Final = getattr(user_api_key_dict, "permissions", None) or {}
        return metadata.get("hide_secrets") is False or permissions.get("hide_secrets") is False

    async def async_pre_call_hook(self, user_api_key_dict, cache, data: dict, call_type):
        if not self.should_run_guardrail(data=data, event_type=GuardrailEventHooks.pre_call):
            return data
        if self._key_opted_out(user_api_key_dict):
            return data
        found: Final = self.redact_request(data)
        if found:
            verbose_proxy_logger.info(
                "HangarLLM hide_secrets: redacted %d secret(s): %s", len(found), sorted(set(found))
            )
            from hangarllm.proxy.common_utils.callback_utils import add_guardrail_to_applied_guardrails_header

            add_guardrail_to_applied_guardrails_header(request_data=data, guardrail_name=self.guardrail_name)
        return data


def default_secret_guardrail() -> HangarSecretDetection:
    """On for every request. Only recognizable provider keys are masked, so ordinary prompts stay intact."""
    return HangarSecretDetection(
        detect_secrets_config={
            "disabled_patterns": ["credential_assignment", "basic_auth_in_url", "bearer_header", "jwt"]
        }
    )


def install_default_secret_guardrail() -> None:
    if os.getenv("HANGARLLM_DISABLE_SECRET_GUARDRAIL", "").strip().lower() == "true":
        return
    if any(isinstance(callback, HangarSecretDetection) for callback in hangarllm.callbacks):
        return
    hangarllm.logging_callback_manager.add_hangarllm_callback(default_secret_guardrail())


# upstream-compatible name used by callback_utils / guardrail_initializers
_ENTERPRISE_SecretDetection = HangarSecretDetection
