"""
Llama Guard moderation (``callbacks: ["llamaguard_moderations"]``).

Sends the conversation to a Llama Guard model (``hangarllm_settings.llamaguard_model_name``,
e.g. ``together_ai/meta-llama/Llama-Guard-3-8B`` or a router model group) using
the published Llama Guard prompt format, and blocks the request when the model
answers ``unsafe``.

Custom categories: ``hangarllm_settings.llamaguard_unsafe_content_categories`` -
path to a text file with one ``S<n>: <name>. <description>`` block per category.
"""

from collections.abc import Mapping
from typing import Final

from fastapi import HTTPException

import hangarllm
from hangarllm._logging import verbose_proxy_logger
from hangarllm.integrations.custom_logger import CustomLogger

DEFAULT_CATEGORIES: Final = """S1: Violent Crimes.
S2: Non-Violent Crimes.
S3: Sex Crimes.
S4: Child Exploitation.
S5: Defamation.
S6: Specialized Advice.
S7: Privacy.
S8: Intellectual Property.
S9: Indiscriminate Weapons.
S10: Hate.
S11: Self-Harm.
S12: Sexual Content.
S13: Elections."""


def _load_categories(path: str | None) -> str:
    if not path:
        return DEFAULT_CATEGORIES
    try:
        with open(path, encoding="utf-8") as handle:
            return handle.read().strip() or DEFAULT_CATEGORIES
    except OSError as e:
        raise ValueError(f"Could not read llamaguard_unsafe_content_categories file {path!r}: {e}") from e


def _role_label(role: object) -> str:
    return "Agent" if role == "assistant" else "User"


def _text(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, Mapping) and isinstance(p.get("text"), str))
    return ""


class HangarLlamaGuard(CustomLogger):
    def __init__(self, model_name: str | None = None) -> None:
        super().__init__()
        self.model: str | None = model_name or hangarllm.llamaguard_model_name
        if not self.model:
            raise ValueError("llamaguard_moderations needs hangarllm_settings.llamaguard_model_name")
        self.unsafe_categories: str = _load_categories(hangarllm.llamaguard_unsafe_content_categories)

    def build_prompt(self, messages: list[Mapping[str, object]]) -> str:
        conversation: Final = "\n\n".join(
            f"{_role_label(m.get('role'))}: {_text(m.get('content'))}" for m in messages if m.get("role") != "system"
        )
        last_role: Final = _role_label(messages[-1].get("role")) if messages else "User"
        return (
            f"Task: Check if there is unsafe content in '{last_role}' messages in conversations according to our "
            "safety policy with the below categories.\n\n"
            f"<BEGIN UNSAFE CONTENT CATEGORIES>\n{self.unsafe_categories}\n<END UNSAFE CONTENT CATEGORIES>\n\n"
            f"<BEGIN CONVERSATION>\n\n{conversation}\n\n<END CONVERSATION>\n\n"
            f"Provide your safety assessment for ONLY THE LAST {last_role} message in the above conversation:\n"
            "- First line must read 'safe' or 'unsafe'.\n"
            "- If unsafe, a second line must include a comma-separated list of violated categories."
        )

    async def async_moderation_hook(self, data: dict, user_api_key_dict, call_type):
        messages: Final = data.get("messages")
        if not isinstance(messages, list) or not messages:
            return
        prompt: Final = self.build_prompt([m for m in messages if isinstance(m, Mapping)])
        from hangarllm.proxy.proxy_server import llm_router

        try:
            kwargs: Final = {"model": self.model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 32}
            response = (
                await llm_router.acompletion(**kwargs)
                if llm_router is not None
                else await hangarllm.acompletion(**kwargs)
            )
        except Exception as e:  # noqa: BLE001 - retried against the provider directly below
            # fall back to a direct provider call if the router does not know the model
            try:
                response = await hangarllm.acompletion(**kwargs)
            except Exception:  # noqa: BLE001
                verbose_proxy_logger.error("HangarLLM llamaguard: moderation call failed - %s", e)
                return
        verdict: Final = (response.choices[0].message.content or "").strip()  # type: ignore[union-attr]
        if verdict.lower().startswith("unsafe"):
            categories: Final = verdict.splitlines()[1].strip() if len(verdict.splitlines()) > 1 else ""
            raise HTTPException(
                status_code=400,
                detail={"error": "Violated content safety policy", "categories": categories},
            )
        return


_ENTERPRISE_LlamaGuard = HangarLlamaGuard
