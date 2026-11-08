from typing import Final, Literal

import hangarllm
from hangarllm.exceptions import BadRequestError
from hangarllm.hangarllm_core_utils.get_llm_provider_logic import declared_authenticating_provider
from hangarllm.llms.bedrock_mantle.chat.claude_transformation import bedrock_mantle_chat_config
from hangarllm.types.utils import LlmProviders, LlmProvidersSet


def get_supported_openai_params(
    model: str,
    custom_llm_provider: str | None = None,
    request_type: Literal["chat_completion", "embeddings", "transcription"] = "chat_completion",
    base_model: str | None = None,
) -> list | None:
    """
    Returns the supported openai params for a given model + provider

    Example:
    ```
    get_supported_openai_params(model="anthropic.claude-3", custom_llm_provider="bedrock")
    ```

    Args:
        base_model: An optional capability hint for deployments whose ``model``
            label isn't recognized on its own (e.g. an Azure deployment name, or a
            friendly Bedrock alias). It is additive: the result is the union of the
            params supported by ``model`` and by ``base_model``, so a hint can only
            add capabilities, never strip ones the real model already supports.

    Returns:
    - List if custom_llm_provider is mapped
    - None if unmapped
    """
    if not custom_llm_provider:
        custom_llm_provider = declared_authenticating_provider(model)
    if not custom_llm_provider:
        try:
            custom_llm_provider = hangarllm.get_llm_provider(model=model)[1]
        except BadRequestError:
            return None

    if custom_llm_provider in LlmProvidersSet:
        provider_config = hangarllm.ProviderConfigManager.get_provider_chat_config(
            model=model,
            provider=LlmProviders(custom_llm_provider),
            base_model=base_model,
        )
    elif custom_llm_provider.split("/")[0] in LlmProvidersSet:
        provider_config = hangarllm.ProviderConfigManager.get_provider_chat_config(
            model=model,
            provider=LlmProviders(custom_llm_provider.split("/")[0]),
            base_model=base_model,
        )
    else:
        provider_config = None

    if provider_config and request_type == "chat_completion":
        supported_params = provider_config.get_supported_openai_params(model=model)
        if base_model and base_model != model:
            base_model_params: Final = provider_config.get_supported_openai_params(model=base_model)
            supported_params = list(dict.fromkeys([*supported_params, *base_model_params]))
        return supported_params

    if custom_llm_provider == "bedrock" or custom_llm_provider == "bedrock_converse":
        return hangarllm.AmazonConverseConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "meta_llama":
        provider_config = hangarllm.ProviderConfigManager.get_provider_chat_config(
            model=model, provider=LlmProviders.LLAMA
        )
        if provider_config:
            return provider_config.get_supported_openai_params(model=model)
    elif custom_llm_provider == "ollama":
        return hangarllm.OllamaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ollama_chat":
        return hangarllm.OllamaChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anthropic":
        return hangarllm.AnthropicConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anthropic_text":
        return hangarllm.AnthropicTextConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "fireworks_ai":
        if request_type == "embeddings":
            return hangarllm.FireworksAIEmbeddingConfig().get_supported_openai_params(model=model)
        elif request_type == "transcription":
            return None
        else:
            return hangarllm.FireworksAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nvidia_nim":
        if request_type == "chat_completion":
            return hangarllm.nvidiaNimConfig.get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return hangarllm.nvidiaNimEmbeddingConfig.get_supported_openai_params()
    elif custom_llm_provider == "cerebras":
        return hangarllm.CerebrasConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nadir":
        return hangarllm.NadirConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "baseten":
        return hangarllm.BasetenConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "xai":
        return hangarllm.XAIChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ai21_chat" or custom_llm_provider == "ai21":
        return hangarllm.AI21ChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "volcengine":
        return hangarllm.VolcEngineConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "groq":
        return hangarllm.GroqChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "bedrock_mantle":
        return bedrock_mantle_chat_config(model).get_supported_openai_params(model=model)
    elif custom_llm_provider == "hosted_vllm":
        return hangarllm.HostedVLLMChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vllm":
        return hangarllm.VLLMConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepseek":
        return hangarllm.DeepSeekChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "tencent":
        return hangarllm.TencentChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "cohere_chat" or custom_llm_provider == "cohere":
        return hangarllm.CohereChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "maritalk":
        return hangarllm.MaritalkConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "openai":
        if request_type == "transcription":
            transcription_provider_config = hangarllm.ProviderConfigManager.get_provider_audio_transcription_config(
                model=model, provider=LlmProviders.OPENAI
            )
            if isinstance(transcription_provider_config, hangarllm.OpenAIGPTAudioTranscriptionConfig):
                return transcription_provider_config.get_supported_openai_params(model=model)
            else:
                raise ValueError(f"Unsupported provider config: {transcription_provider_config} for model: {model}")
        return hangarllm.OpenAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "sap":
        if request_type == "chat_completion":
            return hangarllm.GenAIHubOrchestrationConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return hangarllm.GenAIHubEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "azure":
        _azure_detection_model: Final = base_model or model
        if hangarllm.AzureOpenAIO1Config().is_o_series_model(model=_azure_detection_model):
            return hangarllm.AzureOpenAIO1Config().get_supported_openai_params(model=_azure_detection_model)
        elif hangarllm.AzureOpenAIGPT5Config.is_model_gpt_5_model(model=_azure_detection_model):
            return hangarllm.AzureOpenAIGPT5Config().get_supported_openai_params(model=_azure_detection_model)
        else:
            return hangarllm.AzureOpenAIConfig().get_supported_openai_params(model=_azure_detection_model)
    elif custom_llm_provider == "openrouter":
        return hangarllm.OpenrouterConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vercel_ai_gateway":
        return hangarllm.VercelAIGatewayConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "mistral" or custom_llm_provider == "codestral":
        # mistal and codestral api have the exact same params
        if request_type == "chat_completion":
            return hangarllm.MistralConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return hangarllm.MistralEmbeddingConfig().get_supported_openai_params()
        elif request_type == "transcription":
            from hangarllm.llms.mistral.audio_transcription.transformation import (
                MistralAudioTranscriptionConfig,
            )

            return MistralAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "text-completion-codestral":
        return hangarllm.CodestralTextCompletionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "sambanova":
        if request_type == "embeddings":
            return hangarllm.SambaNovaEmbeddingConfig().get_supported_openai_params(model=model)
        else:
            return hangarllm.SambanovaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nebius":
        if request_type == "chat_completion":
            return hangarllm.NebiusConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "wandb":
        if request_type == "chat_completion":
            return hangarllm.WandbConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "replicate":
        return hangarllm.ReplicateConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "huggingface":
        return hangarllm.HuggingFaceChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "jina_ai":
        if request_type == "embeddings":
            return hangarllm.JinaAIEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "together_ai":
        return hangarllm.TogetherAIChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "databricks":
        if request_type == "chat_completion":
            return hangarllm.DatabricksConfig().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return hangarllm.DatabricksEmbeddingConfig().get_supported_openai_params()
    elif custom_llm_provider == "palm" or custom_llm_provider == "gemini":
        return hangarllm.GoogleAIStudioGeminiConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "novita":
        return hangarllm.NovitaConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "vertex_ai" or custom_llm_provider == "vertex_ai_beta":
        if request_type == "chat_completion":
            if model.startswith("mistral"):
                return hangarllm.VertexAIMistralConfig().get_supported_openai_params(model=model)
            elif model.startswith("codestral"):
                return hangarllm.CodestralTextCompletionConfig().get_supported_openai_params(model=model)
            elif model.startswith("claude"):
                return hangarllm.VertexAIAnthropicConfig().get_supported_openai_params(model=model)
            elif model.startswith("gemini"):
                return hangarllm.VertexGeminiConfig().get_supported_openai_params(model=model)
            else:
                return hangarllm.VertexAILlama3Config().get_supported_openai_params(model=model)
        elif request_type == "embeddings":
            return hangarllm.VertexAITextEmbeddingConfig().get_supported_openai_params()
    elif custom_llm_provider == "sagemaker":
        return hangarllm.SagemakerConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "aleph_alpha":
        return [
            "max_tokens",
            "stream",
            "top_p",
            "temperature",
            "presence_penalty",
            "frequency_penalty",
            "n",
            "stop",
        ]
    elif custom_llm_provider == "cloudflare":
        return hangarllm.CloudflareChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nlp_cloud":
        return hangarllm.NLPCloudConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "petals":
        return hangarllm.PetalsConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepinfra":
        return hangarllm.DeepInfraConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "perplexity":
        return hangarllm.PerplexityChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "nscale":
        return hangarllm.NscaleConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "anyscale":
        return [
            "temperature",
            "top_p",
            "stream",
            "max_tokens",
            "stop",
            "frequency_penalty",
            "presence_penalty",
        ]
    elif custom_llm_provider == "watsonx":
        return hangarllm.IBMWatsonXChatConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "watsonx_text":
        return hangarllm.IBMWatsonXAIConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "custom_openai" or custom_llm_provider == "text-completion-openai":
        return hangarllm.OpenAITextCompletionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "predibase":
        return hangarllm.PredibaseConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "voyage":
        if request_type == "embeddings" and hangarllm.VoyageMultimodalEmbeddingConfig.is_multimodal_embeddings(model):
            return hangarllm.VoyageMultimodalEmbeddingConfig().get_supported_openai_params(model=model)
        return hangarllm.VoyageEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "infinity":
        return hangarllm.InfinityEmbeddingConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "triton":
        if request_type == "embeddings":
            return hangarllm.TritonEmbeddingConfig().get_supported_openai_params(model=model)
        else:
            return hangarllm.TritonConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "deepgram":
        if request_type == "transcription":
            return hangarllm.DeepgramAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "ovhcloud":
        if request_type == "transcription":
            from hangarllm.llms.ovhcloud.audio_transcription.transformation import (
                OVHCloudAudioTranscriptionConfig,
            )

            return OVHCloudAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "scaleway":
        if request_type == "transcription":
            from hangarllm.llms.scaleway.audio_transcription.transformation import (
                ScalewayAudioTranscriptionConfig,
            )

            return ScalewayAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "elevenlabs":
        if request_type == "transcription":
            from hangarllm.llms.elevenlabs.audio_transcription.transformation import (
                ElevenLabsAudioTranscriptionConfig,
            )

            return ElevenLabsAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider == "soniox":
        if request_type == "transcription":
            from hangarllm.llms.soniox.audio_transcription.transformation import (
                SonioxAudioTranscriptionConfig,
            )

            return SonioxAudioTranscriptionConfig().get_supported_openai_params(model=model)
    elif custom_llm_provider in hangarllm._custom_providers:
        if request_type == "chat_completion":
            provider_config = hangarllm.ProviderConfigManager.get_provider_chat_config(
                model=model, provider=LlmProviders.CUSTOM
            )
            if provider_config:
                return provider_config.get_supported_openai_params(model=model)
        elif request_type == "embeddings" or request_type == "transcription":
            return None

    return None
