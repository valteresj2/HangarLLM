"""
Base OCR types shared by the Rust OCR route and Python consumers.
"""

import builtins
from collections.abc import Mapping
from typing import Final, Literal

from pydantic import PrivateAttr

from hangarllm.types.llms.base import HangarLLMPydanticObjectBase

DocumentType = Mapping[str, object]

OCRRequestFormat = Literal["hangarllm", "native"]

OCR_REQUEST_FORMATS: Final[tuple[OCRRequestFormat, ...]] = ("hangarllm", "native")

OCR_REQUEST_FORMAT_PARAM: Final = "req_format"

OCR_REQUEST_FORMAT_HEADER: Final = "x-req-format"

PROVIDER_NATIVE_RESPONSE_KEY: Final = "provider_native_response"


def parse_ocr_request_format(value: object) -> OCRRequestFormat:
    if value == "hangarllm":
        return "hangarllm"
    if value == "native":
        return "native"
    raise ValueError(
        f"Invalid `{OCR_REQUEST_FORMAT_PARAM}`: {value!r}. Expected one of {', '.join(OCR_REQUEST_FORMATS)}."
    )


class OCRPageDimensions(HangarLLMPydanticObjectBase):
    """Page dimensions from OCR response."""

    dpi: int | None = None
    height: int | None = None
    width: int | None = None


class OCRPageImage(HangarLLMPydanticObjectBase):
    """Image extracted from OCR page."""

    image_base64: str | None = None
    bbox: dict[str, builtins.object] | None = None

    model_config = {"extra": "allow"}


class OCRPage(HangarLLMPydanticObjectBase):
    """Single page from OCR response."""

    index: int
    markdown: str
    images: list[OCRPageImage] | None = None
    dimensions: OCRPageDimensions | None = None

    model_config = {"extra": "allow"}


class OCRUsageInfo(HangarLLMPydanticObjectBase):
    """Usage information from OCR response."""

    pages_processed: int | None = None
    pages_processed_annotation: int | None = None
    credits: float | None = None
    doc_size_bytes: int | None = None

    model_config = {"extra": "allow"}


class OCRResponse(HangarLLMPydanticObjectBase):
    """
    Standard OCR response format.
    Standardized to Mistral OCR format - other providers should transform to this format.
    """

    pages: list[OCRPage]
    model: str
    document_annotation: builtins.object | None = None
    usage_info: OCRUsageInfo | None = None
    content: str | None = None
    tables: list[dict[str, builtins.object]] | None = None
    keyValuePairs: list[dict[str, builtins.object]] | None = None
    object: str = "ocr"

    model_config = {"extra": "allow"}

    _hidden_params: dict = PrivateAttr(default_factory=dict)

    @property
    def hidden_params(self) -> dict[str, builtins.object]:  # mutable-ok: API requires mutation
        return self._hidden_params

    @hidden_params.setter
    def hidden_params(self, hidden_params: dict[str, builtins.object]) -> None:  # mutable-ok: API requires mutation
        self._hidden_params = hidden_params

    def set_provider_native_response(self, native_response: Mapping[str, builtins.object]) -> None:
        """Keep the provider's own response payload alongside the normalized one."""
        self._hidden_params[PROVIDER_NATIVE_RESPONSE_KEY] = native_response

    def get_provider_native_response(self) -> Mapping[str, builtins.object] | None:
        """The provider's own response payload, when `req_format=native` was requested."""
        native_response: Final = self._hidden_params.get(PROVIDER_NATIVE_RESPONSE_KEY)
        return native_response if isinstance(native_response, dict) else None
