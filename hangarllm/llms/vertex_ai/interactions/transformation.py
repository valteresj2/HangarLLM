from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from hangarllm.hangarllm_core_utils.url_utils import encode_url_path_segment, join_api_base
from hangarllm.llms.gemini.interactions.transformation import GoogleAIStudioInteractionsConfig
from hangarllm.llms.vertex_ai.common_utils import validate_vertex_location
from hangarllm.llms.vertex_ai.vertex_llm_base import VertexBase
from hangarllm.types.llms.vertex_ai import VERTEX_CREDENTIALS_TYPES
from hangarllm.types.router import GenericHangarLLMParams
from hangarllm.types.utils import LlmProviders

VERTEX_INTERACTIONS_API_VERSION: Final = "v1beta1"
VERTEX_INTERACTIONS_DEFAULT_LOCATION: Final = "global"


@dataclass(frozen=True, slots=True)
class VertexInteractionsTarget:
    base_url: str
    project_id: str
    location: str

    @property
    def collection_url(self) -> str:
        return join_api_base(
            self.base_url,
            f"{VERTEX_INTERACTIONS_API_VERSION}/projects/{self.project_id}/locations/{self.location}/interactions",
        )

    def interaction_url(self, interaction_id: str) -> str:
        encoded_interaction_id: Final = encode_url_path_segment(interaction_id, field_name="interaction_id")
        return f"{self.collection_url}/{encoded_interaction_id}"


class VertexAIInteractionsConfig(VertexBase, GoogleAIStudioInteractionsConfig):
    def __init__(
        self,
        mint_access_token: Callable[[VERTEX_CREDENTIALS_TYPES | None, str | None], tuple[str, str]] | None = None,
    ) -> None:
        super().__init__()
        self._mint_access_token: Final[Callable[[VERTEX_CREDENTIALS_TYPES | None, str | None], tuple[str, str]]] = (
            mint_access_token or self._mint_access_token_with_vertex_base
        )

    def _mint_access_token_with_vertex_base(
        self,
        credentials: VERTEX_CREDENTIALS_TYPES | None,
        project_id: str | None,
    ) -> tuple[str, str]:
        return self._ensure_access_token(
            credentials=credentials, project_id=project_id, custom_llm_provider="vertex_ai"
        )

    @property
    def custom_llm_provider(self) -> LlmProviders:
        return LlmProviders.VERTEX_AI

    @property
    def api_version(self) -> str:
        return VERTEX_INTERACTIONS_API_VERSION

    def get_default_vertex_location(self) -> str:
        return VERTEX_INTERACTIONS_DEFAULT_LOCATION

    def _mint(self, hangarllm_params: GenericHangarLLMParams) -> tuple[str, str]:
        raw_params: Final = hangarllm_params.model_dump()
        return self._mint_access_token(
            self.safe_get_vertex_ai_credentials(raw_params),
            self.safe_get_vertex_ai_project(raw_params),
        )

    def _target(self, api_base: str | None, hangarllm_params: GenericHangarLLMParams) -> VertexInteractionsTarget:
        _, project_id = self._mint(hangarllm_params)
        if not project_id:
            raise ValueError(
                "Vertex AI project is required. Set vertex_project, hangarllm.vertex_project, or VERTEXAI_PROJECT"
            )
        location: Final = validate_vertex_location(
            self.explicit_vertex_ai_location(hangarllm_params.model_dump()) or VERTEX_INTERACTIONS_DEFAULT_LOCATION
        )
        return VertexInteractionsTarget(
            base_url=self.get_api_base(api_base or None, location),
            project_id=project_id,
            location=location,
        )

    def validate_environment(
        self,
        headers: Mapping[str, str],
        model: str,
        hangarllm_params: GenericHangarLLMParams | None,
    ) -> dict:  # mutable-ok: BaseInteractionsAPIConfig declares plain-dict headers
        access_token, _ = self._mint(hangarllm_params or GenericHangarLLMParams())
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            **headers,
        }

    def get_complete_url(
        self,
        api_base: str | None,
        model: str | None,
        agent: str | None = None,
        hangarllm_params: Mapping[str, object] | None = None,
        stream: bool | None = None,
    ) -> str:
        params: Final = (
            GenericHangarLLMParams.model_validate(hangarllm_params) if hangarllm_params else GenericHangarLLMParams()
        )
        collection_url: Final = self._target(api_base, params).collection_url
        return f"{collection_url}?alt=sse" if stream else collection_url

    def _interaction_by_id_request(
        self,
        interaction_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        url_suffix: str = "",
    ) -> tuple[str, dict]:  # mutable-ok: BaseInteractionsAPIConfig declares a plain-dict request body
        target: Final = self._target(api_base or None, hangarllm_params)
        return f"{target.interaction_url(interaction_id)}{url_suffix}", {}

    def transform_get_interaction_request(
        self,
        interaction_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        headers: Mapping[str, str],
    ) -> tuple[str, dict]:  # mutable-ok: BaseInteractionsAPIConfig declares a plain-dict request body
        return self._interaction_by_id_request(interaction_id, api_base, hangarllm_params)

    def transform_delete_interaction_request(
        self,
        interaction_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        headers: Mapping[str, str],
    ) -> tuple[str, dict]:  # mutable-ok: BaseInteractionsAPIConfig declares a plain-dict request body
        return self._interaction_by_id_request(interaction_id, api_base, hangarllm_params)

    def transform_cancel_interaction_request(
        self,
        interaction_id: str,
        api_base: str,
        hangarllm_params: GenericHangarLLMParams,
        headers: Mapping[str, str],
    ) -> tuple[str, dict]:  # mutable-ok: BaseInteractionsAPIConfig declares a plain-dict request body
        return self._interaction_by_id_request(interaction_id, api_base, hangarllm_params, url_suffix=":cancel")
