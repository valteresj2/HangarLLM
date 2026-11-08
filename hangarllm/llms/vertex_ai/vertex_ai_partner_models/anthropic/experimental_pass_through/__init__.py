from hangarllm.hangarllm_core_utils.renamed_package_shim import alias_renamed_package

__getattr__ = alias_renamed_package(__name__, "hangarllm.llms.vertex_ai.vertex_ai_partner_models.anthropic.messages")
