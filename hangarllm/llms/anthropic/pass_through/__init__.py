from hangarllm.hangarllm_core_utils.renamed_package_shim import alias_renamed_package

__getattr__ = alias_renamed_package(
    __name__,
    "hangarllm.llms.anthropic.messages",
    nested_renames=((f"{__name__}.messages", "hangarllm.llms.anthropic.messages.native"),),
)
