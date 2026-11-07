import importlib


def test_hangarllm_is_the_litellm_module():
    import hangarllm
    import litellm

    assert hangarllm is litellm


def test_hangarllm_submodule_resolves_to_litellm_submodule_without_renaming_it():
    aliased = importlib.import_module("hangarllm.types.utils")
    original = importlib.import_module("litellm.types.utils")

    assert aliased is original
    assert original.__name__ == "litellm.types.utils"
    assert original.__spec__.name == "litellm.types.utils"


def test_from_import_through_alias_returns_litellm_objects():
    from hangarllm.router import Router as AliasedRouter

    from litellm.router import Router

    assert AliasedRouter is Router
