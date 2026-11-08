
import hangarllm


def test_reducto_provider_registration():
    model, custom_llm_provider, _, _ = hangarllm.get_llm_provider(
        model="reducto/parse-v3"
    )

    assert model == "parse-v3"
    assert custom_llm_provider == "reducto"


