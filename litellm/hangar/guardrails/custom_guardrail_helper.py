"""
Tag-based guardrail modes.

A guardrail can declare ``mode`` as a ``Mode`` object::

    guardrails:
      - guardrail_name: pii
        litellm_params:
          guardrail: presidio
          mode:
            tags:
              "env:prod": "pre_call"
              "env:dev": "logging_only"
            default: ["pre_call", "post_call"]

The request's tags (key, team, project, caller and serving-deployment tags, in
that precedence order) are walked in order; the first tag listed in ``Mode.tags``
selects which event hook(s) run. Tags injected only by baggage mapping never
select a mode unless the caller or a policy also asked for them. With no
matching tag, ``Mode.default`` applies; with no default the guardrail does not run.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from litellm.types.guardrails import GuardrailEventHooks, Mode

_METADATA_SLOTS: Final = ("litellm_metadata", "metadata")


def _as_list(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []
    return [value] if isinstance(value, str) else list(value)


def request_tags_for_mode(data: Mapping[str, object]) -> list[str]:
    from litellm.router_strategy.tag_based_routing import without_baggage_mapped_tags

    tags: list[str] = []  # mutable-ok: ordered de-duplicated accumulation
    for slot in _METADATA_SLOTS:
        metadata = data.get(slot)
        if not isinstance(metadata, Mapping):
            continue
        raw = metadata.get("tags")
        if not isinstance(raw, Sequence) or isinstance(raw, str):
            continue
        str_tags = [t for t in raw if isinstance(t, str)]
        kept = without_baggage_mapped_tags(str_tags, metadata, keep_serving_deployment_tags=True) or ()
        for tag in kept:
            if tag not in tags:
                tags.append(tag)
    return tags


class HangarCustomGuardrailHelper:
    @staticmethod
    def _should_run_if_mode_by_tag(
        data: Mapping[str, object],
        event_hook: Mode,
        event_type: GuardrailEventHooks,
    ) -> bool | None:
        """True / False when the Mode decides, None when it has neither a matching tag nor a default."""
        for tag in request_tags_for_mode(data):
            if tag in event_hook.tags:
                return event_type.value in _as_list(event_hook.tags[tag])
        if event_hook.default is not None:
            return event_type.value in _as_list(event_hook.default)
        return False


EnterpriseCustomGuardrailHelper = HangarCustomGuardrailHelper
