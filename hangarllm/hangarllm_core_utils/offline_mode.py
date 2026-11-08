import os


def is_offline_mode() -> bool:
    """True when ``HANGARLLM_OFFLINE_MODE=true``. A catalog, check or tokenizer HangarLLM fetches on its own, rather
    than from a destination the operator configured, must check this and use its bundled copy or skip instead"""
    return os.getenv("HANGARLLM_OFFLINE_MODE", "").strip().lower() == "true"
