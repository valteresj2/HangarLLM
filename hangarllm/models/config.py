"""
Config table model.

Canonical definition for ``hangarllm_config``. Re-exported from
``hangarllm.proxy._types`` for backwards compatibility.
"""

from hangarllm.types.llms.base import HangarLLMPydanticObjectBase


class HangarLLM_Config(HangarLLMPydanticObjectBase):
    param_name: str
    param_value: dict
