from types import MappingProxyType

from litellm._process_defaults import hangarllm_env_aliases


def test_hangarllm_vars_fill_unset_litellm_vars():
    aliases = hangarllm_env_aliases(MappingProxyType({"HANGARLLM_MASTER_KEY": "sk-1", "PATH": "/bin"}))
    assert dict(aliases) == {"LITELLM_MASTER_KEY": "sk-1"}


def test_explicit_litellm_var_wins_over_hangarllm_var():
    environ = MappingProxyType({"HANGARLLM_MASTER_KEY": "sk-hangar", "LITELLM_MASTER_KEY": "sk-explicit"})
    assert dict(hangarllm_env_aliases(environ)) == {}


def test_empty_hangarllm_var_is_not_mirrored():
    assert dict(hangarllm_env_aliases(MappingProxyType({"HANGARLLM_SALT_KEY": ""}))) == {}
