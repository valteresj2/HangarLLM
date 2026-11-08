"""Per-session state shared by the runtime, handlers and harness configs."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, TypeAlias

from pydantic import BaseModel

from hangarllm.harness.options import HarnessOptions
from hangarllm.harness.sandbox.base import Sandbox
from hangarllm.harness.types import Approval, Harness, PermissionMode

if TYPE_CHECKING:
    from hangarllm.harness.endpoint import ModelEndpoint

ApprovalHandler: TypeAlias = Callable[
    [Approval], bool | Awaitable[bool]  # mutable-ok: Callable parameter list in a type alias, not a runtime collection
]


@dataclass(frozen=True)
class GatewayTarget:
    """Resolved HangarLLM AI Gateway for `hangarllm_proxy/` models. Internal, not exported."""

    api_base: str
    api_key: str


@dataclass
class SessionContext:
    """Everything a handler and config need for a session. Owned by the runtime."""

    harness: Harness
    sandbox: Sandbox
    session_id: str
    # Model name as sent to the runtime (hangarllm_proxy/ prefix already stripped).
    model: str | None = None
    gateway: GatewayTarget | None = None
    api_key: str | None = None
    api_base: str | None = None
    endpoint: ModelEndpoint | None = None
    instructions: str | None = None
    tools: Sequence[Callable[..., object]] = ()
    skills: Sequence[str] = ()
    disable_tools: Sequence[str] = ()
    permissions: PermissionMode = "full"
    on_approval: ApprovalHandler | None = None
    output: type[BaseModel] | None = None
    max_turns: int | None = None
    timeout: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    options: HarnessOptions | None = None
    # Set by the handler after each turn.
    final_text: str = ""
    output_json: str | None = None
    # Usage for in-process harnesses that call HangarLLM directly (no model endpoint).
    input_tokens: int = 0
    output_tokens: int = 0
    cost: float = 0.0
    calls: int = 0
