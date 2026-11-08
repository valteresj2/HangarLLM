from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from hangarllm.integrations.custom_prompt_management import CustomPromptManagement
    from hangarllm.types.prompts.init_prompts import PromptHangarLLMParams, PromptSpec

    from .gitlab_prompt_manager import GitLabPromptManager

from hangarllm.integrations.custom_prompt_management import CustomPromptManagement
from hangarllm.types.prompts.init_prompts import PromptHangarLLMParams, PromptSpec, SupportedPromptIntegrations

from .gitlab_prompt_manager import GitLabPromptCache, GitLabPromptManager

# Global instances
global_gitlab_config: Final[dict | None] = None


def set_global_gitlab_config(config: dict) -> None:
    """
    Set the global gitlab configuration for prompt management.

    Args:
        config: Dictionary containing gitlab configuration
                - workspace: gitlab workspace name
                - repository: Repository name
                - access_token: gitlab access token
                - branch: Branch to fetch prompts from (default: main)
    """
    import hangarllm

    hangarllm.global_gitlab_config = config


def prompt_initializer(hangarllm_params: "PromptHangarLLMParams", prompt_spec: "PromptSpec") -> "CustomPromptManagement":
    """
    Initialize a prompt from a Gitlab repository.
    """
    gitlab_config: Final = getattr(hangarllm_params, "gitlab_config", None)
    prompt_id: Final = getattr(hangarllm_params, "prompt_id", None)

    if not gitlab_config:
        raise ValueError("gitlab_config is required for gitlab prompt integration")

    try:
        gitlab_prompt_manager: Final = GitLabPromptManager(
            gitlab_config=gitlab_config,
            prompt_id=prompt_id,
        )

        return gitlab_prompt_manager
    except Exception as e:
        raise e


def _gitlab_prompt_initializer(
    hangarllm_params: PromptHangarLLMParams,
    prompt: PromptSpec,
) -> CustomPromptManagement:
    """
    Build a GitLab-backed prompt manager for this prompt.
    Expected fields on hangarllm_params:
      - prompt_integration="gitlab"  (handled by the caller)
      - gitlab_config: Dict[str, Any] (project/access_token/branch/prompts_path/etc.)
      - git_ref (optional): per-prompt tag/branch/SHA override
    """
    # You can store arbitrary integration-specific config on PromptHangarLLMParams.
    # If your dataclass doesn't have these attributes, add them or put inside
    # `hangarllm_params.extra` and pull them from there.
    gitlab_config: Final[dict[str, object]] = getattr(hangarllm_params, "gitlab_config", None) or {}
    git_ref: Final[str | None] = getattr(hangarllm_params, "git_ref", None)

    if not gitlab_config:
        raise ValueError("gitlab_config is required for gitlab prompt integration")

    # prompt.prompt_id can map to a file path under prompts_path (e.g. "chat/greet/hi")
    return GitLabPromptManager(
        gitlab_config=gitlab_config,
        prompt_id=prompt.prompt_id,
        ref=git_ref,
    )


prompt_initializer_registry: Final = {
    SupportedPromptIntegrations.GITLAB.value: _gitlab_prompt_initializer,
}

# Export public API
__all__ = [
    "GitLabPromptCache",
    "GitLabPromptManager",
    "global_gitlab_config",
    "set_global_gitlab_config",
]
