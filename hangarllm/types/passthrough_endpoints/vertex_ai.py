"""
Used for /vertex_ai/ pass through endpoints
"""

from hangarllm.types.llms.base import HangarLLMBaseModel

from ..llms.vertex_ai import VERTEX_CREDENTIALS_TYPES


class VertexPassThroughCredentials(HangarLLMBaseModel):
    # Example: vertex_project = "my-project-123"
    vertex_project: str | None = None

    # Example: vertex_location = "us-central1"
    vertex_location: str | None = None

    # Example: vertex_credentials = "/path/to/credentials.json" or "os.environ/GOOGLE_CREDS"
    vertex_credentials: VERTEX_CREDENTIALS_TYPES | None = None
