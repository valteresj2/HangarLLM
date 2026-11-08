"""
Registry data for lazy imports.

This module contains all the name tuples and import maps used by the lazy import system.
Separated from the handler functions for better organization.
"""

from typing import Final

# Cost calculator names that support lazy loading via _lazy_import_cost_calculator
COST_CALCULATOR_NAMES: Final = (
    "completion_cost",
    "cost_per_token",
    "response_cost_calculator",
)

# Hangarllm logging names that support lazy loading via _lazy_import_hangarllm_logging
HANGARLLM_LOGGING_NAMES: Final = (
    "Logging",
    "modify_integration",
)

# Utils names that support lazy loading via _lazy_import_utils
UTILS_NAMES: Final = (
    "run_server",
    "exception_type",
    "get_optional_params",
    "get_response_string",
    "token_counter",
    "create_pretrained_tokenizer",
    "create_tokenizer",
    "supports_function_calling",
    "supports_web_search",
    "supports_tool_search",
    "supports_url_context",
    "supports_continuation",
    "supports_response_schema",
    "supports_parallel_function_calling",
    "supports_vision",
    "supports_audio_input",
    "supports_video_input",
    "supports_box_questions",
    "supports_audio_output",
    "supports_system_messages",
    "supports_reasoning",
    "get_hangarllm_params",
    "acreate",
    "get_max_tokens",
    "get_model_info",
    "register_prompt_template",
    "validate_environment",
    "check_valid_key",
    "register_model",
    "encode",
    "decode",
    "calculate_retry_after",
    "_calculate_retry_after",
    "should_retry",
    "_should_retry",
    "get_supported_openai_params",
    "get_api_base",
    "get_first_chars_messages",
    "ModelResponse",
    "ModelResponseStream",
    "EmbeddingResponse",
    "ImageResponse",
    "TranscriptionResponse",
    "TextCompletionResponse",
    "get_provider_fields",
    "ModelResponseListIterator",
    "get_valid_models",
    "timeout",
    "get_llm_provider",
    "remove_index_from_tool_calls",
)

# Token counter names that support lazy loading via _lazy_import_token_counter
TOKEN_COUNTER_NAMES: Final = ("get_modified_max_tokens",)

# LLM client cache names that support lazy loading via _lazy_import_llm_client_cache
LLM_CLIENT_CACHE_NAMES: Final = (
    "LLMClientCache",
    "in_memory_llm_clients_cache",
)

# Bedrock type names that support lazy loading via _lazy_import_bedrock_types
BEDROCK_TYPES_NAMES: Final = ("COHERE_EMBEDDING_INPUT_TYPES",)

# Common types from hangarllm.types.utils that support lazy loading via
# _lazy_import_types_utils
TYPES_UTILS_NAMES: Final = (
    "ImageObject",
    "BudgetConfig",
    "all_hangarllm_params",
    "_hangarllm_completion_params",
    "CredentialItem",
    "PriorityReservationDict",
    "StandardKeyGenerationConfig",
    "SearchProviders",
    "GenericStreamingChunk",
)

# Caching / cache classes that support lazy loading via _lazy_import_caching
CACHING_NAMES: Final = (
    "Cache",
    "DualCache",
    "RedisCache",
    "InMemoryCache",
)

# HTTP handler names that support lazy loading via _lazy_import_http_handlers
HTTP_HANDLER_NAMES: Final = (
    "module_level_aclient",
    "module_level_client",
)

# Dotprompt integration names that support lazy loading via _lazy_import_dotprompt
DOTPROMPT_NAMES: Final = (
    "global_prompt_manager",
    "global_prompt_directory",
    "set_global_prompt_directory",
)

# LLM config classes that support lazy loading via _lazy_import_llm_configs
LLM_CONFIG_NAMES: Final = (
    "AmazonConverseConfig",
    "OpenAILikeChatConfig",
    "GaladrielChatConfig",
    "GithubChatConfig",
    "AzureAnthropicConfig",
    "BytezChatConfig",
    "CompactifAIChatConfig",
    "EmpowerChatConfig",
    "MinimaxChatConfig",
    "AiohttpOpenAIChatConfig",
    "HuggingFaceChatConfig",
    "HuggingFaceEmbeddingConfig",
    "OobaboogaConfig",
    "MaritalkConfig",
    "OpenrouterConfig",
    "DataRobotConfig",
    "AnthropicConfig",
    "BedrockClaudePlatformConfig",
    "AnthropicTextConfig",
    "GroqSTTConfig",
    "TritonConfig",
    "TritonGenerateConfig",
    "TritonInferConfig",
    "TritonEmbeddingConfig",
    "HuggingFaceRerankConfig",
    "DatabricksConfig",
    "DatabricksEmbeddingConfig",
    "PredibaseConfig",
    "ReplicateConfig",
    "SnowflakeConfig",
    "CohereRerankConfig",
    "CohereRerankV2Config",
    "AzureAIRerankConfig",
    "InfinityRerankConfig",
    "JinaAIRerankConfig",
    "ScalewayRerankConfig",
    "DeepinfraRerankConfig",
    "HostedVLLMRerankConfig",
    "PerplexityDecisionsConfig",
    "TypeSafeDecisionsConfig",
    "ParallelAIDecisionsConfig",
    "NaceDecisionsConfig",
    "OpenRouterDecisionsConfig",
    "FireworksAIDecisionsConfig",
    "CloudflareDecisionsConfig",
    "CloudflareExtractionConfig",
    "StrandsDeciderDecisionsConfig",
    "DatabricksDecisionsConfig",
    "HostedVLLMDecisionsConfig",
    "LMStudioDecisionsConfig",
    "OllamaDecisionsConfig",
    "LayaDecisionsConfig",
    "BespokeDecisionsConfig",
    "EmpirioLabsDecisionsConfig",
    "EuJevDecisionsConfig",
    "OpenAIDecisionsConfig",
    "AzureDecisionsConfig",
    "AzureAIDecisionsConfig",
    "NvidiaNimRerankConfig",
    "NvidiaNimRankingConfig",
    "VertexAIRerankConfig",
    "FireworksAIRerankConfig",
    "VoyageRerankConfig",
    "IBMWatsonXRerankConfig",
    "ClarifaiConfig",
    "AI21ChatConfig",
    "LlamaAPIConfig",
    "TogetherAITextCompletionConfig",
    "CloudflareChatConfig",
    "NovitaConfig",
    "PetalsConfig",
    "OllamaChatConfig",
    "OllamaConfig",
    "SagemakerConfig",
    "SagemakerChatConfig",
    "SagemakerNovaConfig",
    "CohereChatConfig",
    "AnthropicMessagesConfig",
    "BedrockClaudePlatformMessagesConfig",
    "AmazonAnthropicClaudeMessagesConfig",
    "AmazonMantleMessagesConfig",
    "BedrockMantleAnthropicMessagesConfig",
    "TogetherAIConfig",
    "TogetherAIChatConfig",
    "NLPCloudConfig",
    "VertexGeminiConfig",
    "GoogleAIStudioGeminiConfig",
    "VertexAIAnthropicConfig",
    "VertexAILlama3Config",
    "VertexAIAi21Config",
    "VertexAIMistralConfig",
    "AmazonCohereChatConfig",
    "AmazonBedrockGlobalConfig",
    "AmazonAI21Config",
    "AmazonInvokeNovaConfig",
    "AmazonQwen2Config",
    "AmazonQwen3Config",
    # Aliases for backwards compatibility
    "VertexAIConfig",  # Alias for VertexGeminiConfig
    "GeminiConfig",  # Alias for GoogleAIStudioGeminiConfig
    "AmazonAnthropicConfig",
    "AmazonAnthropicClaudeConfig",
    "AmazonCohereConfig",
    "AmazonLlamaConfig",
    "AmazonDeepSeekR1Config",
    "AmazonMistralConfig",
    "AmazonMoonshotConfig",
    "AmazonTitanConfig",
    "AmazonTwelveLabsPegasusConfig",
    "AmazonInvokeConfig",
    "AmazonBedrockOpenAIConfig",
    "AmazonBedrockRuntimeChatCompletionsConfig",
    "AmazonStabilityConfig",
    "AmazonStability3Config",
    "AmazonNovaCanvasConfig",
    "AmazonTitanG1Config",
    "AmazonTitanMultimodalEmbeddingG1Config",
    "CohereV2ChatConfig",
    "BedrockCohereEmbeddingConfig",
    "TwelveLabsMarengoEmbeddingConfig",
    "AmazonNovaEmbeddingConfig",
    "OpenAIConfig",
    "MistralEmbeddingConfig",
    "OpenAIImageVariationConfig",
    "DeepInfraConfig",
    "ClfAiGatewayConfig",
    "DeepgramAudioTranscriptionConfig",
    "TopazImageVariationConfig",
    "OpenAITextCompletionConfig",
    "GroqChatConfig",
    "BedrockMantleChatConfig",
    "A2AConfig",
    "GenAIHubOrchestrationConfig",
    "VoyageEmbeddingConfig",
    "VoyageContextualEmbeddingConfig",
    "VoyageMultimodalEmbeddingConfig",
    "InfinityEmbeddingConfig",
    "PerplexityEmbeddingConfig",
    "AzureAIStudioConfig",
    "MistralConfig",
    "OpenAIResponsesAPIConfig",
    "AzureOpenAIResponsesAPIConfig",
    "AzureOpenAIOSeriesResponsesAPIConfig",
    "AzureAIResponsesAPIConfig",
    "XAIResponsesAPIConfig",
    "HangarLLMProxyResponsesAPIConfig",
    "HostedVLLMResponsesAPIConfig",
    "FireworksAIResponsesAPIConfig",
    "VolcEngineResponsesAPIConfig",
    "PerplexityResponsesConfig",
    "DatabricksResponsesAPIConfig",
    "OpenRouterResponsesAPIConfig",
    "BedrockOpenAIResponsesConfig",
    "BedrockMantleResponsesAPIConfig",
    "GoogleAIStudioInteractionsConfig",
    "VertexAIInteractionsConfig",
    "OpenAIOSeriesConfig",
    "AnthropicSkillsConfig",
    "BaseSkillsAPIConfig",
    "GradientAIConfig",
    # Alias for backwards compatibility
    "OpenAIO1Config",  # Alias for OpenAIOSeriesConfig
    "OpenAIGPTConfig",
    "OpenAIGPT5Config",
    "OpenAIWhisperAudioTranscriptionConfig",
    "OpenAIGPTAudioTranscriptionConfig",
    "OpenAIGPTAudioConfig",
    "NvidiaNimConfig",
    "NvidiaNimEmbeddingConfig",
    "FeatherlessAIConfig",
    "ScaleDownChatConfig",
    "CerebrasConfig",
    "NadirConfig",
    "BasetenConfig",
    "SambanovaConfig",
    "SambaNovaEmbeddingConfig",
    "FireworksAIConfig",
    "FireworksAITextCompletionConfig",
    "FireworksAIEmbeddingConfig",
    "FriendliaiChatConfig",
    "JinaAIEmbeddingConfig",
    "XAIChatConfig",
    "ZAIChatConfig",
    "AIMLChatConfig",
    "VolcEngineChatConfig",
    "CodestralTextCompletionConfig",
    "InceptionTextCompletionConfig",
    "AzureOpenAIAssistantsAPIConfig",
    "HerokuChatConfig",
    "CometAPIConfig",
    "AzureOpenAIConfig",
    "AzureOpenAIGPT5Config",
    "AzureOpenAITextConfig",
    "AzureSpeechAudioTranscriptionConfig",
    "HostedVLLMChatConfig",
    "HostedVLLMEmbeddingConfig",
    # Alias for backwards compatibility
    "VolcEngineConfig",  # Alias for VolcEngineChatConfig
    "LlamafileChatConfig",
    "HangarLLMProxyChatConfig",
    "VLLMConfig",
    "DeepSeekChatConfig",
    "TencentChatConfig",
    "LMStudioChatConfig",
    "LmStudioEmbeddingConfig",
    "NscaleConfig",
    "PerplexityChatConfig",
    "AzureOpenAIO1Config",
    "IBMWatsonXAIConfig",
    "IBMWatsonXChatConfig",
    "IBMWatsonXEmbeddingConfig",
    "GenAIHubEmbeddingConfig",
    "IBMWatsonXAudioTranscriptionConfig",
    "GithubCopilotConfig",
    "GithubCopilotResponsesAPIConfig",
    "ChatGPTConfig",
    "ChatGPTResponsesAPIConfig",
    "ManusResponsesAPIConfig",
    "GithubCopilotEmbeddingConfig",
    "NebiusConfig",
    "WandbConfig",
    "GigaChatConfig",
    "GigaChatEmbeddingConfig",
    "DashScopeChatConfig",
    "QwenCloudChatConfig",
    "QwenAIPlatformChatConfig",
    "ModelScopeChatConfig",
    "MoonshotChatConfig",
    "DockerModelRunnerChatConfig",
    "V0ChatConfig",
    "OCIChatConfig",
    "MorphChatConfig",
    "RAGFlowConfig",
    "LambdaAIChatConfig",
    "InceptionChatConfig",
    "HyperbolicChatConfig",
    "VercelAIGatewayConfig",
    "EdenAIChatConfig",
    "EdenAIResponsesAPIConfig",
    "EdenAIAnthropicMessagesConfig",
    "EdenAIEmbeddingConfig",
    "EdenAIAudioTranscriptionConfig",
    "EdenAITextToSpeechConfig",
    "EdenAIImageGenerationConfig",
    "EdenAIVideoConfig",
    "FalAIChatConfig",
    "FalAIError",
    "OVHCloudChatConfig",
    "OVHCloudEmbeddingConfig",
    "CometAPIEmbeddingConfig",
    "LemonadeChatConfig",
    "SnowflakeEmbeddingConfig",
    "AmazonNovaChatConfig",
    "SonioxAudioTranscriptionConfig",
    "GDCGeminiConfig",
)

# Types that support lazy loading via _lazy_import_types
TYPES_NAMES: Final = (
    "GuardrailItem",
    "DefaultTeamSSOParams",
    "HangarLLM_UpperboundKeyGenerateParams",
    "KeyManagementSystem",
    "PriorityReservationSettings",
    "CustomLogger",
    "LoggingCallbackManager",
    "DatadogLLMObsInitParams",
    # Note: LlmProviders is NOT lazy-loaded because it's imported during import time
    # in multiple places including openai.py (via main import)
    # Note: KeyManagementSettings is NOT lazy-loaded because _key_management_settings
    # is accessed during import time in secret_managers/main.py
)

# LLM provider logic names that support lazy loading via _lazy_import_llm_provider_logic
LLM_PROVIDER_LOGIC_NAMES: Final = (
    "get_llm_provider",
    "remove_index_from_tool_calls",
)

# Utils module names that support lazy loading via _lazy_import_utils_module
# These are attributes accessed from hangarllm.utils module
UTILS_MODULE_NAMES: Final = (
    "encoding",
    "BaseVectorStore",
    "CredentialAccessor",
    "exception_type",
    "get_error_message",
    "_get_response_headers",
    "get_llm_provider",
    "_is_non_openai_azure_model",
    "is_non_openai_azure_model",
    "get_supported_openai_params",
    "HangarLLMResponseObjectHandler",
    "_handle_invalid_parallel_tool_calls",
    "handle_invalid_parallel_tool_calls",
    "convert_to_model_response_object",
    "convert_to_streaming_response",
    "convert_to_streaming_response_async",
    "get_api_base",
    "ResponseMetadata",
    "_parse_content_for_reasoning",
    "parse_content_for_reasoning",
    "HangarLLMLoggingObject",
    "redact_message_input_output_from_logging",
    "CustomStreamWrapper",
    "BaseGoogleGenAIGenerateContentConfig",
    "BaseSearchConfig",
    "BaseTextToSpeechConfig",
    "BedrockModelInfo",
    "CohereModelInfo",
    "Rules",
    "AsyncHTTPHandler",
    "HTTPHandler",
    "get_num_retries_from_retry_policy",
    "reset_retry_policy",
    "get_coroutine_checker",
    "get_hangarllm_logging_class",
    "get_set_callbacks",
    "get_hangarllm_metadata_from_kwargs",
    "map_finish_reason",
    "process_response_headers",
    "delete_nested_value",
    "is_nested_path",
    "_get_base_model_from_hangarllm_call_metadata",
    "get_base_model_from_hangarllm_call_metadata",
    "get_hangarllm_params",
    "_ensure_extra_body_is_safe",
    "ensure_extra_body_is_safe",
    "get_formatted_prompt",
    "get_response_headers",
    "update_response_metadata",
    "executor",
    "BaseAnthropicMessagesConfig",
    "BaseAudioTranscriptionConfig",
    "BaseBatchesConfig",
    "BaseContainerConfig",
    "BaseEmbeddingConfig",
    "BaseImageEditConfig",
    "BaseImageGenerationConfig",
    "BaseImageVariationConfig",
    "BasePassthroughConfig",
    "BaseRealtimeConfig",
    "BaseRerankConfig",
    "BaseVectorStoreConfig",
    "BaseVectorStoreFilesConfig",
    "BaseVideoConfig",
    "ANTHROPIC_API_ONLY_HEADERS",
    "AnthropicThinkingParam",
    "RerankResponse",
    "ChatCompletionDeltaToolCallChunk",
    "ChatCompletionToolCallChunk",
    "ChatCompletionToolCallFunctionChunk",
    "HangarLLM_Params",
)

# Import maps for registry pattern - reduces repetition
_UTILS_IMPORT_MAP: Final = {
    "run_server": ("hangarllm.proxy.proxy_cli", "run_server"),
    "exception_type": (".utils", "exception_type"),
    "get_optional_params": (".utils", "get_optional_params"),
    "get_response_string": (".utils", "get_response_string"),
    "token_counter": (".utils", "token_counter"),
    "create_pretrained_tokenizer": (".utils", "create_pretrained_tokenizer"),
    "create_tokenizer": (".utils", "create_tokenizer"),
    "supports_function_calling": (".utils", "supports_function_calling"),
    "supports_web_search": (".utils", "supports_web_search"),
    "supports_tool_search": (".utils", "supports_tool_search"),
    "supports_url_context": (".utils", "supports_url_context"),
    "supports_continuation": (".utils", "supports_continuation"),
    "supports_response_schema": (".utils", "supports_response_schema"),
    "supports_parallel_function_calling": (
        ".utils",
        "supports_parallel_function_calling",
    ),
    "supports_vision": (".utils", "supports_vision"),
    "supports_audio_input": (".utils", "supports_audio_input"),
    "supports_video_input": (".utils", "supports_video_input"),
    "supports_box_questions": (".utils", "supports_box_questions"),
    "supports_audio_output": (".utils", "supports_audio_output"),
    "supports_system_messages": (".utils", "supports_system_messages"),
    "supports_reasoning": (".utils", "supports_reasoning"),
    "get_hangarllm_params": (".utils", "get_hangarllm_params"),
    "acreate": (".utils", "acreate"),
    "get_max_tokens": (".utils", "get_max_tokens"),
    "get_model_info": (".utils", "get_model_info"),
    "register_prompt_template": (".utils", "register_prompt_template"),
    "validate_environment": (".utils", "validate_environment"),
    "check_valid_key": (".utils", "check_valid_key"),
    "register_model": (".utils", "register_model"),
    "encode": (".utils", "encode"),
    "decode": (".utils", "decode"),
    "calculate_retry_after": (".utils", "calculate_retry_after"),
    "_calculate_retry_after": (".utils", "calculate_retry_after"),
    "should_retry": (".utils", "should_retry"),
    "_should_retry": (".utils", "should_retry"),
    "get_supported_openai_params": (".utils", "get_supported_openai_params"),
    "get_api_base": (".utils", "get_api_base"),
    "get_first_chars_messages": (".utils", "get_first_chars_messages"),
    "ModelResponse": (".utils", "ModelResponse"),
    "ModelResponseStream": (".utils", "ModelResponseStream"),
    "EmbeddingResponse": (".utils", "EmbeddingResponse"),
    "ImageResponse": (".utils", "ImageResponse"),
    "TranscriptionResponse": (".utils", "TranscriptionResponse"),
    "TextCompletionResponse": (".utils", "TextCompletionResponse"),
    "get_provider_fields": (".utils", "get_provider_fields"),
    "ModelResponseListIterator": (".utils", "ModelResponseListIterator"),
    "get_valid_models": (".utils", "get_valid_models"),
    "timeout": (".timeout", "timeout"),
    "get_llm_provider": (
        "hangarllm.hangarllm_core_utils.get_llm_provider_logic",
        "get_llm_provider",
    ),
    "remove_index_from_tool_calls": (
        "hangarllm.hangarllm_core_utils.core_helpers",
        "remove_index_from_tool_calls",
    ),
}

_COST_CALCULATOR_IMPORT_MAP: Final = {
    "completion_cost": (".cost_calculator", "completion_cost"),
    "cost_per_token": (".cost_calculator", "cost_per_token"),
    "response_cost_calculator": (".cost_calculator", "response_cost_calculator"),
}

_TYPES_UTILS_IMPORT_MAP: Final = {
    "ImageObject": (".types.utils", "ImageObject"),
    "BudgetConfig": (".types.utils", "BudgetConfig"),
    "all_hangarllm_params": (".types.utils", "all_hangarllm_params"),
    "_hangarllm_completion_params": (".types.utils", "all_hangarllm_params"),  # Alias
    "CredentialItem": (".types.utils", "CredentialItem"),
    "PriorityReservationDict": (".types.utils", "PriorityReservationDict"),
    "StandardKeyGenerationConfig": (".types.utils", "StandardKeyGenerationConfig"),
    "SearchProviders": (".types.utils", "SearchProviders"),
    "GenericStreamingChunk": (".types.utils", "GenericStreamingChunk"),
}

_TOKEN_COUNTER_IMPORT_MAP: Final = {
    "get_modified_max_tokens": (
        "hangarllm.hangarllm_core_utils.token_counter",
        "get_modified_max_tokens",
    ),
}

_BEDROCK_TYPES_IMPORT_MAP: Final = {
    "COHERE_EMBEDDING_INPUT_TYPES": (
        "hangarllm.types.llms.bedrock",
        "COHERE_EMBEDDING_INPUT_TYPES",
    ),
}

_CACHING_IMPORT_MAP: Final = {
    "Cache": ("hangarllm.caching.caching", "Cache"),
    "DualCache": ("hangarllm.caching.caching", "DualCache"),
    "RedisCache": ("hangarllm.caching.caching", "RedisCache"),
    "InMemoryCache": ("hangarllm.caching.caching", "InMemoryCache"),
}

_HANGARLLM_LOGGING_IMPORT_MAP: Final = {
    "Logging": ("hangarllm.hangarllm_core_utils.hangarllm_logging", "Logging"),
    "modify_integration": (
        "hangarllm.hangarllm_core_utils.hangarllm_logging",
        "modify_integration",
    ),
}

_DOTPROMPT_IMPORT_MAP: Final = {
    "global_prompt_manager": (
        "hangarllm.integrations.dotprompt",
        "global_prompt_manager",
    ),
    "global_prompt_directory": (
        "hangarllm.integrations.dotprompt",
        "global_prompt_directory",
    ),
    "set_global_prompt_directory": (
        "hangarllm.integrations.dotprompt",
        "set_global_prompt_directory",
    ),
}

_TYPES_IMPORT_MAP: Final = {
    "GuardrailItem": ("hangarllm.types.guardrails", "GuardrailItem"),
    "DefaultTeamSSOParams": (
        "hangarllm.types.proxy.management_endpoints.ui_sso",
        "DefaultTeamSSOParams",
    ),
    "HangarLLM_UpperboundKeyGenerateParams": (
        "hangarllm.types.proxy.management_endpoints.ui_sso",
        "HangarLLM_UpperboundKeyGenerateParams",
    ),
    "KeyManagementSystem": (
        "hangarllm.types.secret_managers.main",
        "KeyManagementSystem",
    ),
    "PriorityReservationSettings": (
        "hangarllm.types.utils",
        "PriorityReservationSettings",
    ),
    "CustomLogger": ("hangarllm.integrations.custom_logger", "CustomLogger"),
    "LoggingCallbackManager": (
        "hangarllm.hangarllm_core_utils.logging_callback_manager",
        "LoggingCallbackManager",
    ),
    "DatadogLLMObsInitParams": (
        "hangarllm.types.integrations.datadog_llm_obs",
        "DatadogLLMObsInitParams",
    ),
}

_LLM_PROVIDER_LOGIC_IMPORT_MAP: Final = {
    "get_llm_provider": (
        "hangarllm.hangarllm_core_utils.get_llm_provider_logic",
        "get_llm_provider",
    ),
    "remove_index_from_tool_calls": (
        "hangarllm.hangarllm_core_utils.core_helpers",
        "remove_index_from_tool_calls",
    ),
}

_LLM_CONFIGS_IMPORT_MAP: Final = {
    "AmazonConverseConfig": (
        ".llms.bedrock.chat.converse_transformation",
        "AmazonConverseConfig",
    ),
    "OpenAILikeChatConfig": (".llms.openai_like.chat.handler", "OpenAILikeChatConfig"),
    "GaladrielChatConfig": (
        ".llms.galadriel.chat.transformation",
        "GaladrielChatConfig",
    ),
    "GithubChatConfig": (".llms.github.chat.transformation", "GithubChatConfig"),
    "AzureAnthropicConfig": (
        ".llms.azure_ai.anthropic.transformation",
        "AzureAnthropicConfig",
    ),
    "BytezChatConfig": (".llms.bytez.chat.transformation", "BytezChatConfig"),
    "CompactifAIChatConfig": (
        ".llms.compactifai.chat.transformation",
        "CompactifAIChatConfig",
    ),
    "EmpowerChatConfig": (".llms.empower.chat.transformation", "EmpowerChatConfig"),
    "MinimaxChatConfig": (".llms.minimax.chat.transformation", "MinimaxChatConfig"),
    "AiohttpOpenAIChatConfig": (
        ".llms.aiohttp_openai.chat.transformation",
        "AiohttpOpenAIChatConfig",
    ),
    "HuggingFaceChatConfig": (
        ".llms.huggingface.chat.transformation",
        "HuggingFaceChatConfig",
    ),
    "HuggingFaceEmbeddingConfig": (
        ".llms.huggingface.embedding.transformation",
        "HuggingFaceEmbeddingConfig",
    ),
    "OobaboogaConfig": (".llms.oobabooga.chat.transformation", "OobaboogaConfig"),
    "MaritalkConfig": (".llms.maritalk", "MaritalkConfig"),
    "OpenrouterConfig": (".llms.openrouter.chat.transformation", "OpenrouterConfig"),
    "DataRobotConfig": (".llms.datarobot.chat.transformation", "DataRobotConfig"),
    "AnthropicConfig": (".llms.anthropic.chat.transformation", "AnthropicConfig"),
    "BedrockClaudePlatformConfig": (
        ".llms.bedrock.claude_platform.transformation",
        "BedrockClaudePlatformConfig",
    ),
    "AnthropicTextConfig": (
        ".llms.anthropic.completion.transformation",
        "AnthropicTextConfig",
    ),
    "GroqSTTConfig": (".llms.groq.stt.transformation", "GroqSTTConfig"),
    "TritonConfig": (".llms.triton.completion.transformation", "TritonConfig"),
    "TritonGenerateConfig": (
        ".llms.triton.completion.transformation",
        "TritonGenerateConfig",
    ),
    "TritonInferConfig": (
        ".llms.triton.completion.transformation",
        "TritonInferConfig",
    ),
    "TritonEmbeddingConfig": (
        ".llms.triton.embedding.transformation",
        "TritonEmbeddingConfig",
    ),
    "HuggingFaceRerankConfig": (
        ".llms.huggingface.rerank.transformation",
        "HuggingFaceRerankConfig",
    ),
    "DatabricksConfig": (".llms.databricks.chat.transformation", "DatabricksConfig"),
    "DatabricksEmbeddingConfig": (
        ".llms.databricks.embed.transformation",
        "DatabricksEmbeddingConfig",
    ),
    "PredibaseConfig": (".llms.predibase.chat.transformation", "PredibaseConfig"),
    "ReplicateConfig": (".llms.replicate.chat.transformation", "ReplicateConfig"),
    "SnowflakeConfig": (".llms.snowflake.chat.transformation", "SnowflakeConfig"),
    "CohereRerankConfig": (".llms.cohere.rerank.transformation", "CohereRerankConfig"),
    "CohereRerankV2Config": (
        ".llms.cohere.rerank_v2.transformation",
        "CohereRerankV2Config",
    ),
    "AzureAIRerankConfig": (
        ".llms.azure_ai.rerank.transformation",
        "AzureAIRerankConfig",
    ),
    "InfinityRerankConfig": (
        ".llms.infinity.rerank.transformation",
        "InfinityRerankConfig",
    ),
    "JinaAIRerankConfig": (".llms.jina_ai.rerank.transformation", "JinaAIRerankConfig"),
    "ScalewayRerankConfig": (".llms.scaleway.rerank.transformation", "ScalewayRerankConfig"),
    "DeepinfraRerankConfig": (
        ".llms.deepinfra.rerank.transformation",
        "DeepinfraRerankConfig",
    ),
    "HostedVLLMRerankConfig": (
        ".llms.hosted_vllm.rerank.transformation",
        "HostedVLLMRerankConfig",
    ),
    "PerplexityDecisionsConfig": (".llms.perplexity.decisions.transformation", "PerplexityDecisionsConfig"),
    "NaceDecisionsConfig": (".llms.nace.decisions.transformation", "NaceDecisionsConfig"),
    "TypeSafeDecisionsConfig": (".llms.typesafe.decisions.transformation", "TypeSafeDecisionsConfig"),
    "ParallelAIDecisionsConfig": (".llms.parallel_ai.decisions.transformation", "ParallelAIDecisionsConfig"),
    "OpenRouterDecisionsConfig": (".llms.openrouter.decisions.transformation", "OpenRouterDecisionsConfig"),
    "FireworksAIDecisionsConfig": (".llms.fireworks_ai.decisions.transformation", "FireworksAIDecisionsConfig"),
    "CloudflareDecisionsConfig": (".llms.cloudflare.decisions.transformation", "CloudflareDecisionsConfig"),
    "CloudflareExtractionConfig": (".llms.cloudflare.extraction.transformation", "CloudflareExtractionConfig"),
    "StrandsDeciderDecisionsConfig": (
        ".llms.strands_decider.decisions.transformation",
        "StrandsDeciderDecisionsConfig",
    ),
    "DatabricksDecisionsConfig": (".llms.databricks.decisions.transformation", "DatabricksDecisionsConfig"),
    "HostedVLLMDecisionsConfig": (
        ".llms.hosted_vllm.decisions.transformation",
        "HostedVLLMDecisionsConfig",
    ),
    "LMStudioDecisionsConfig": (".llms.lm_studio.decisions.transformation", "LMStudioDecisionsConfig"),
    "OllamaDecisionsConfig": (".llms.ollama.decisions.transformation", "OllamaDecisionsConfig"),
    "LayaDecisionsConfig": (".llms.laya.decisions.transformation", "LayaDecisionsConfig"),
    "BespokeDecisionsConfig": (".llms.bespoke.decisions.transformation", "BespokeDecisionsConfig"),
    "EmpirioLabsDecisionsConfig": (".llms.empiriolabs.decisions.transformation", "EmpirioLabsDecisionsConfig"),
    "EuJevDecisionsConfig": (".llms.eu_jev.decisions.transformation", "EuJevDecisionsConfig"),
    "OpenAIDecisionsConfig": (".llms.openai.decisions.transformation", "OpenAIDecisionsConfig"),
    "AzureDecisionsConfig": (".llms.azure.decisions.transformation", "AzureDecisionsConfig"),
    "AzureAIDecisionsConfig": (".llms.azure_ai.decisions.transformation", "AzureAIDecisionsConfig"),
    "NvidiaNimRerankConfig": (
        ".llms.nvidia_nim.rerank.transformation",
        "NvidiaNimRerankConfig",
    ),
    "NvidiaNimRankingConfig": (
        ".llms.nvidia_nim.rerank.ranking_transformation",
        "NvidiaNimRankingConfig",
    ),
    "VertexAIRerankConfig": (
        ".llms.vertex_ai.rerank.transformation",
        "VertexAIRerankConfig",
    ),
    "FireworksAIRerankConfig": (
        ".llms.fireworks_ai.rerank.transformation",
        "FireworksAIRerankConfig",
    ),
    "VoyageRerankConfig": (".llms.voyage.rerank.transformation", "VoyageRerankConfig"),
    "IBMWatsonXRerankConfig": (
        ".llms.watsonx.rerank.transformation",
        "IBMWatsonXRerankConfig",
    ),
    "ClarifaiConfig": (".llms.clarifai.chat.transformation", "ClarifaiConfig"),
    "AI21ChatConfig": (".llms.ai21.chat.transformation", "AI21ChatConfig"),
    "LlamaAPIConfig": (".llms.meta_llama.chat.transformation", "LlamaAPIConfig"),
    "TogetherAITextCompletionConfig": (
        ".llms.together_ai.completion.transformation",
        "TogetherAITextCompletionConfig",
    ),
    "CloudflareChatConfig": (
        ".llms.cloudflare.chat.transformation",
        "CloudflareChatConfig",
    ),
    "NovitaConfig": (".llms.novita.chat.transformation", "NovitaConfig"),
    "PetalsConfig": (".llms.petals.completion.transformation", "PetalsConfig"),
    "OllamaChatConfig": (".llms.ollama.chat.transformation", "OllamaChatConfig"),
    "OllamaConfig": (".llms.ollama.completion.transformation", "OllamaConfig"),
    "SagemakerConfig": (".llms.sagemaker.completion.transformation", "SagemakerConfig"),
    "SagemakerChatConfig": (
        ".llms.sagemaker.chat.transformation",
        "SagemakerChatConfig",
    ),
    "SagemakerNovaConfig": (
        ".llms.sagemaker.nova.transformation",
        "SagemakerNovaConfig",
    ),
    "CohereChatConfig": (".llms.cohere.chat.transformation", "CohereChatConfig"),
    "AnthropicMessagesConfig": (
        ".llms.anthropic.messages.native.transformation",
        "AnthropicMessagesConfig",
    ),
    "BedrockClaudePlatformMessagesConfig": (
        ".llms.bedrock.claude_platform.messages_transformation",
        "BedrockClaudePlatformMessagesConfig",
    ),
    "AmazonAnthropicClaudeMessagesConfig": (
        ".llms.bedrock.messages.invoke_transformations.anthropic_claude_transformation",
        "AmazonAnthropicClaudeMessagesConfig",
    ),
    "AmazonMantleMessagesConfig": (
        ".llms.bedrock.messages.mantle_transformation",
        "AmazonMantleMessagesConfig",
    ),
    "BedrockMantleAnthropicMessagesConfig": (
        ".llms.bedrock_mantle.messages.transformation",
        "BedrockMantleAnthropicMessagesConfig",
    ),
    "TogetherAIConfig": (".llms.together_ai.chat", "TogetherAIConfig"),
    "TogetherAIChatConfig": (
        ".llms.together_ai.chat.transformation",
        "TogetherAIChatConfig",
    ),
    "NLPCloudConfig": (".llms.nlp_cloud.chat.handler", "NLPCloudConfig"),
    "VertexGeminiConfig": (
        ".llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini",
        "VertexGeminiConfig",
    ),
    "GoogleAIStudioGeminiConfig": (
        ".llms.gemini.chat.transformation",
        "GoogleAIStudioGeminiConfig",
    ),
    "VertexAIAnthropicConfig": (
        ".llms.vertex_ai.vertex_ai_partner_models.anthropic.transformation",
        "VertexAIAnthropicConfig",
    ),
    "VertexAILlama3Config": (
        ".llms.vertex_ai.vertex_ai_partner_models.llama.transformation",
        "VertexAILlama3Config",
    ),
    "VertexAIAi21Config": (
        ".llms.vertex_ai.vertex_ai_partner_models.ai21.transformation",
        "VertexAIAi21Config",
    ),
    "VertexAIMistralConfig": (
        ".llms.vertex_ai.vertex_ai_partner_models.mistral.transformation",
        "VertexAIMistralConfig",
    ),
    "AmazonCohereChatConfig": (
        ".llms.bedrock.chat.invoke_handler",
        "AmazonCohereChatConfig",
    ),
    "AmazonBedrockGlobalConfig": (
        ".llms.bedrock.common_utils",
        "AmazonBedrockGlobalConfig",
    ),
    "AmazonAI21Config": (
        ".llms.bedrock.chat.invoke_transformations.amazon_ai21_transformation",
        "AmazonAI21Config",
    ),
    "AmazonInvokeNovaConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_nova_transformation",
        "AmazonInvokeNovaConfig",
    ),
    "AmazonQwen2Config": (
        ".llms.bedrock.chat.invoke_transformations.amazon_qwen2_transformation",
        "AmazonQwen2Config",
    ),
    "AmazonQwen3Config": (
        ".llms.bedrock.chat.invoke_transformations.amazon_qwen3_transformation",
        "AmazonQwen3Config",
    ),
    # Aliases for backwards compatibility
    "VertexAIConfig": (
        ".llms.vertex_ai.gemini.vertex_and_google_ai_studio_gemini",
        "VertexGeminiConfig",
    ),  # Alias
    "GeminiConfig": (
        ".llms.gemini.chat.transformation",
        "GoogleAIStudioGeminiConfig",
    ),  # Alias
    "AmazonAnthropicConfig": (
        ".llms.bedrock.chat.invoke_transformations.anthropic_legacy_text_completions_transformation",
        "AmazonAnthropicConfig",
    ),
    "AmazonAnthropicClaudeConfig": (
        ".llms.bedrock.chat.invoke_transformations.anthropic_claude_transformation",
        "AmazonAnthropicClaudeConfig",
    ),
    "AmazonCohereConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_cohere_transformation",
        "AmazonCohereConfig",
    ),
    "AmazonLlamaConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_llama_transformation",
        "AmazonLlamaConfig",
    ),
    "AmazonDeepSeekR1Config": (
        ".llms.bedrock.chat.invoke_transformations.amazon_deepseek_transformation",
        "AmazonDeepSeekR1Config",
    ),
    "AmazonMistralConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_mistral_transformation",
        "AmazonMistralConfig",
    ),
    "AmazonMoonshotConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_moonshot_transformation",
        "AmazonMoonshotConfig",
    ),
    "AmazonTitanConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_titan_transformation",
        "AmazonTitanConfig",
    ),
    "AmazonTwelveLabsPegasusConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_twelvelabs_pegasus_transformation",
        "AmazonTwelveLabsPegasusConfig",
    ),
    "AmazonInvokeConfig": (
        ".llms.bedrock.chat.invoke_transformations.base_invoke_transformation",
        "AmazonInvokeConfig",
    ),
    "AmazonBedrockOpenAIConfig": (
        ".llms.bedrock.chat.invoke_transformations.amazon_openai_transformation",
        "AmazonBedrockOpenAIConfig",
    ),
    "AmazonBedrockRuntimeChatCompletionsConfig": (
        ".llms.bedrock.chat.chat_completions.transformation",
        "AmazonBedrockRuntimeChatCompletionsConfig",
    ),
    "AmazonStabilityConfig": (
        ".llms.bedrock.image_generation.amazon_stability1_transformation",
        "AmazonStabilityConfig",
    ),
    "AmazonStability3Config": (
        ".llms.bedrock.image_generation.amazon_stability3_transformation",
        "AmazonStability3Config",
    ),
    "AmazonNovaCanvasConfig": (
        ".llms.bedrock.image_generation.amazon_nova_canvas_transformation",
        "AmazonNovaCanvasConfig",
    ),
    "AmazonTitanG1Config": (
        ".llms.bedrock.embed.amazon_titan_g1_transformation",
        "AmazonTitanG1Config",
    ),
    "AmazonTitanMultimodalEmbeddingG1Config": (
        ".llms.bedrock.embed.amazon_titan_multimodal_transformation",
        "AmazonTitanMultimodalEmbeddingG1Config",
    ),
    "CohereV2ChatConfig": (".llms.cohere.chat.v2_transformation", "CohereV2ChatConfig"),
    "BedrockCohereEmbeddingConfig": (
        ".llms.bedrock.embed.cohere_transformation",
        "BedrockCohereEmbeddingConfig",
    ),
    "TwelveLabsMarengoEmbeddingConfig": (
        ".llms.bedrock.embed.twelvelabs_marengo_transformation",
        "TwelveLabsMarengoEmbeddingConfig",
    ),
    "AmazonNovaEmbeddingConfig": (
        ".llms.bedrock.embed.amazon_nova_transformation",
        "AmazonNovaEmbeddingConfig",
    ),
    "OpenAIConfig": (".llms.openai.openai", "OpenAIConfig"),
    "MistralEmbeddingConfig": (".llms.openai.openai", "MistralEmbeddingConfig"),
    "OpenAIImageVariationConfig": (
        ".llms.openai.image_variations.transformation",
        "OpenAIImageVariationConfig",
    ),
    "DeepInfraConfig": (".llms.deepinfra.chat.transformation", "DeepInfraConfig"),
    "ClfAiGatewayConfig": (
        ".llms.clf_ai_gateway.chat.transformation",
        "ClfAiGatewayConfig",
    ),
    "DeepgramAudioTranscriptionConfig": (
        ".llms.deepgram.audio_transcription.transformation",
        "DeepgramAudioTranscriptionConfig",
    ),
    "TopazImageVariationConfig": (
        ".llms.topaz.image_variations.transformation",
        "TopazImageVariationConfig",
    ),
    "OpenAITextCompletionConfig": (
        "hangarllm.llms.openai.completion.transformation",
        "OpenAITextCompletionConfig",
    ),
    "GroqChatConfig": (".llms.groq.chat.transformation", "GroqChatConfig"),
    "BedrockOpenAIResponsesConfig": (
        ".llms.bedrock.responses.transformation",
        "BedrockOpenAIResponsesConfig",
    ),
    "BedrockMantleChatConfig": (
        ".llms.bedrock_mantle.chat.transformation",
        "BedrockMantleChatConfig",
    ),
    "A2AConfig": (".llms.a2a.chat.transformation", "A2AConfig"),
    "GenAIHubOrchestrationConfig": (
        ".llms.sap.chat.transformation",
        "GenAIHubOrchestrationConfig",
    ),
    "VoyageEmbeddingConfig": (
        ".llms.voyage.embedding.transformation",
        "VoyageEmbeddingConfig",
    ),
    "VoyageContextualEmbeddingConfig": (
        ".llms.voyage.embedding.transformation_contextual",
        "VoyageContextualEmbeddingConfig",
    ),
    "VoyageMultimodalEmbeddingConfig": (
        ".llms.voyage.embedding.transformation_multimodal",
        "VoyageMultimodalEmbeddingConfig",
    ),
    "InfinityEmbeddingConfig": (
        ".llms.infinity.embedding.transformation",
        "InfinityEmbeddingConfig",
    ),
    "PerplexityEmbeddingConfig": (
        ".llms.perplexity.embedding.transformation",
        "PerplexityEmbeddingConfig",
    ),
    "AzureAIStudioConfig": (
        ".llms.azure_ai.chat.transformation",
        "AzureAIStudioConfig",
    ),
    "MistralConfig": (".llms.mistral.chat.transformation", "MistralConfig"),
    "OpenAIResponsesAPIConfig": (
        ".llms.openai.responses.transformation",
        "OpenAIResponsesAPIConfig",
    ),
    "AzureOpenAIResponsesAPIConfig": (
        ".llms.azure.responses.transformation",
        "AzureOpenAIResponsesAPIConfig",
    ),
    "AzureOpenAIOSeriesResponsesAPIConfig": (
        ".llms.azure.responses.o_series_transformation",
        "AzureOpenAIOSeriesResponsesAPIConfig",
    ),
    "AzureAIResponsesAPIConfig": (
        ".llms.azure_ai.responses.transformation",
        "AzureAIResponsesAPIConfig",
    ),
    "XAIResponsesAPIConfig": (
        ".llms.xai.responses.transformation",
        "XAIResponsesAPIConfig",
    ),
    "HangarLLMProxyResponsesAPIConfig": (
        ".llms.hangarllm_proxy.responses.transformation",
        "HangarLLMProxyResponsesAPIConfig",
    ),
    "HostedVLLMResponsesAPIConfig": (
        ".llms.hosted_vllm.responses.transformation",
        "HostedVLLMResponsesAPIConfig",
    ),
    "FireworksAIResponsesAPIConfig": (
        ".llms.fireworks_ai.responses.transformation",
        "FireworksAIResponsesAPIConfig",
    ),
    "VolcEngineResponsesAPIConfig": (
        ".llms.volcengine.responses.transformation",
        "VolcEngineResponsesAPIConfig",
    ),
    "ManusResponsesAPIConfig": (
        ".llms.manus.responses.transformation",
        "ManusResponsesAPIConfig",
    ),
    "PerplexityResponsesConfig": (
        ".llms.perplexity.responses.transformation",
        "PerplexityResponsesConfig",
    ),
    "DatabricksResponsesAPIConfig": (
        ".llms.databricks.responses.transformation",
        "DatabricksResponsesAPIConfig",
    ),
    "OpenRouterResponsesAPIConfig": (
        ".llms.openrouter.responses.transformation",
        "OpenRouterResponsesAPIConfig",
    ),
    "BedrockMantleResponsesAPIConfig": (
        ".llms.bedrock_mantle.responses.transformation",
        "BedrockMantleResponsesAPIConfig",
    ),
    "GoogleAIStudioInteractionsConfig": (
        ".llms.gemini.interactions.transformation",
        "GoogleAIStudioInteractionsConfig",
    ),
    "VertexAIInteractionsConfig": (
        ".llms.vertex_ai.interactions.transformation",
        "VertexAIInteractionsConfig",
    ),
    "OpenAIOSeriesConfig": (
        ".llms.openai.chat.o_series_transformation",
        "OpenAIOSeriesConfig",
    ),
    "AnthropicSkillsConfig": (
        ".llms.anthropic.skills.transformation",
        "AnthropicSkillsConfig",
    ),
    "BaseSkillsAPIConfig": (
        ".llms.base_llm.skills.transformation",
        "BaseSkillsAPIConfig",
    ),
    "GradientAIConfig": (".llms.gradient_ai.chat.transformation", "GradientAIConfig"),
    # Alias for backwards compatibility
    "OpenAIO1Config": (
        ".llms.openai.chat.o_series_transformation",
        "OpenAIOSeriesConfig",
    ),  # Alias
    "OpenAIGPTConfig": (".llms.openai.chat.gpt_transformation", "OpenAIGPTConfig"),
    "OpenAIGPT5Config": (".llms.openai.chat.gpt_reasoning_transformation", "OpenAIGPT5Config"),
    "OpenAIWhisperAudioTranscriptionConfig": (
        ".llms.openai.transcriptions.whisper_transformation",
        "OpenAIWhisperAudioTranscriptionConfig",
    ),
    "OpenAIGPTAudioTranscriptionConfig": (
        ".llms.openai.transcriptions.gpt_transformation",
        "OpenAIGPTAudioTranscriptionConfig",
    ),
    "OpenAIGPTAudioConfig": (
        ".llms.openai.chat.gpt_audio_transformation",
        "OpenAIGPTAudioConfig",
    ),
    "NvidiaNimConfig": (".llms.nvidia_nim.chat.transformation", "NvidiaNimConfig"),
    "NvidiaNimEmbeddingConfig": (".llms.nvidia_nim.embed", "NvidiaNimEmbeddingConfig"),
    "FeatherlessAIConfig": (
        ".llms.featherless_ai.chat.transformation",
        "FeatherlessAIConfig",
    ),
    "ScaleDownChatConfig": (
        ".llms.scaledown.chat.transformation",
        "ScaleDownChatConfig",
    ),
    "CerebrasConfig": (".llms.cerebras.chat", "CerebrasConfig"),
    "NadirConfig": (".llms.nadir.chat.transformation", "NadirConfig"),
    "BasetenConfig": (".llms.baseten.chat", "BasetenConfig"),
    "SambanovaConfig": (".llms.sambanova.chat", "SambanovaConfig"),
    "SambaNovaEmbeddingConfig": (
        ".llms.sambanova.embedding.transformation",
        "SambaNovaEmbeddingConfig",
    ),
    "FireworksAIConfig": (
        ".llms.fireworks_ai.chat.transformation",
        "FireworksAIConfig",
    ),
    "FireworksAITextCompletionConfig": (
        ".llms.fireworks_ai.completion.transformation",
        "FireworksAITextCompletionConfig",
    ),
    "FireworksAIEmbeddingConfig": (
        ".llms.fireworks_ai.embed.fireworks_ai_transformation",
        "FireworksAIEmbeddingConfig",
    ),
    "FriendliaiChatConfig": (
        ".llms.friendliai.chat.transformation",
        "FriendliaiChatConfig",
    ),
    "JinaAIEmbeddingConfig": (
        ".llms.jina_ai.embedding.transformation",
        "JinaAIEmbeddingConfig",
    ),
    "XAIChatConfig": (".llms.xai.chat.transformation", "XAIChatConfig"),
    "ZAIChatConfig": (".llms.zai.chat.transformation", "ZAIChatConfig"),
    "AIMLChatConfig": (".llms.aiml.chat.transformation", "AIMLChatConfig"),
    "VolcEngineChatConfig": (
        ".llms.volcengine.chat.transformation",
        "VolcEngineChatConfig",
    ),
    "CodestralTextCompletionConfig": (
        ".llms.codestral.completion.transformation",
        "CodestralTextCompletionConfig",
    ),
    "InceptionTextCompletionConfig": (
        ".llms.inception.completion.transformation",
        "InceptionTextCompletionConfig",
    ),
    "AzureOpenAIAssistantsAPIConfig": (
        ".llms.azure.azure",
        "AzureOpenAIAssistantsAPIConfig",
    ),
    "HerokuChatConfig": (".llms.heroku.chat.transformation", "HerokuChatConfig"),
    "CometAPIConfig": (".llms.cometapi.chat.transformation", "CometAPIConfig"),
    "AzureOpenAIConfig": (".llms.azure.chat.gpt_transformation", "AzureOpenAIConfig"),
    "AzureOpenAIGPT5Config": (
        ".llms.azure.chat.gpt_reasoning_transformation",
        "AzureOpenAIGPT5Config",
    ),
    "AzureOpenAITextConfig": (
        ".llms.azure.completion.transformation",
        "AzureOpenAITextConfig",
    ),
    "AzureSpeechAudioTranscriptionConfig": (
        ".llms.azure.audio_transcription.transformation",
        "AzureSpeechAudioTranscriptionConfig",
    ),
    "HostedVLLMChatConfig": (
        ".llms.hosted_vllm.chat.transformation",
        "HostedVLLMChatConfig",
    ),
    "HostedVLLMEmbeddingConfig": (
        ".llms.hosted_vllm.embedding.transformation",
        "HostedVLLMEmbeddingConfig",
    ),
    # Alias for backwards compatibility
    "VolcEngineConfig": (
        ".llms.volcengine.chat.transformation",
        "VolcEngineChatConfig",
    ),  # Alias
    "LlamafileChatConfig": (
        ".llms.llamafile.chat.transformation",
        "LlamafileChatConfig",
    ),
    "HangarLLMProxyChatConfig": (
        ".llms.hangarllm_proxy.chat.transformation",
        "HangarLLMProxyChatConfig",
    ),
    "VLLMConfig": (".llms.vllm.completion.transformation", "VLLMConfig"),
    "DeepSeekChatConfig": (".llms.deepseek.chat.transformation", "DeepSeekChatConfig"),
    "TencentChatConfig": (".llms.tencent.chat.transformation", "TencentChatConfig"),
    "LMStudioChatConfig": (".llms.lm_studio.chat.transformation", "LMStudioChatConfig"),
    "LmStudioEmbeddingConfig": (
        ".llms.lm_studio.embed.transformation",
        "LmStudioEmbeddingConfig",
    ),
    "NscaleConfig": (".llms.nscale.chat.transformation", "NscaleConfig"),
    "PerplexityChatConfig": (
        ".llms.perplexity.chat.transformation",
        "PerplexityChatConfig",
    ),
    "AzureOpenAIO1Config": (
        ".llms.azure.chat.o_series_transformation",
        "AzureOpenAIO1Config",
    ),
    "IBMWatsonXAIConfig": (
        ".llms.watsonx.completion.transformation",
        "IBMWatsonXAIConfig",
    ),
    "IBMWatsonXChatConfig": (
        ".llms.watsonx.chat.transformation",
        "IBMWatsonXChatConfig",
    ),
    "IBMWatsonXEmbeddingConfig": (
        ".llms.watsonx.embed.transformation",
        "IBMWatsonXEmbeddingConfig",
    ),
    "GenAIHubEmbeddingConfig": (
        ".llms.sap.embed.transformation",
        "GenAIHubEmbeddingConfig",
    ),
    "IBMWatsonXAudioTranscriptionConfig": (
        ".llms.watsonx.audio_transcription.transformation",
        "IBMWatsonXAudioTranscriptionConfig",
    ),
    "GithubCopilotConfig": (
        ".llms.github_copilot.chat.transformation",
        "GithubCopilotConfig",
    ),
    "GithubCopilotResponsesAPIConfig": (
        ".llms.github_copilot.responses.transformation",
        "GithubCopilotResponsesAPIConfig",
    ),
    "GithubCopilotEmbeddingConfig": (
        ".llms.github_copilot.embedding.transformation",
        "GithubCopilotEmbeddingConfig",
    ),
    "ChatGPTConfig": (".llms.chatgpt.chat.transformation", "ChatGPTConfig"),
    "ChatGPTResponsesAPIConfig": (
        ".llms.chatgpt.responses.transformation",
        "ChatGPTResponsesAPIConfig",
    ),
    "NebiusConfig": (".llms.nebius.chat.transformation", "NebiusConfig"),
    "WandbConfig": (".llms.wandb.chat.transformation", "WandbConfig"),
    "GigaChatConfig": (".llms.gigachat.chat.transformation", "GigaChatConfig"),
    "GigaChatEmbeddingConfig": (
        ".llms.gigachat.embedding.transformation",
        "GigaChatEmbeddingConfig",
    ),
    "DashScopeChatConfig": (
        ".llms.dashscope.chat.transformation",
        "DashScopeChatConfig",
    ),
    "QwenCloudChatConfig": (
        ".llms.dashscope.qwencloud",
        "QwenCloudChatConfig",
    ),
    "QwenAIPlatformChatConfig": (
        ".llms.dashscope.qwen_ai_platform",
        "QwenAIPlatformChatConfig",
    ),
    "GDCGeminiConfig": (
        ".llms.gdc.chat.transformation",
        "GDCGeminiConfig",
    ),
    "ModelScopeChatConfig": (
        ".llms.modelscope.chat.transformation",
        "ModelScopeChatConfig",
    ),
    "MoonshotChatConfig": (".llms.moonshot.chat.transformation", "MoonshotChatConfig"),
    "DockerModelRunnerChatConfig": (
        ".llms.docker_model_runner.chat.transformation",
        "DockerModelRunnerChatConfig",
    ),
    "V0ChatConfig": (".llms.v0.chat.transformation", "V0ChatConfig"),
    "OCIChatConfig": (".llms.oci.chat.transformation", "OCIChatConfig"),
    "MorphChatConfig": (".llms.morph.chat.transformation", "MorphChatConfig"),
    "RAGFlowConfig": (".llms.ragflow.chat.transformation", "RAGFlowConfig"),
    "LambdaAIChatConfig": (".llms.lambda_ai.chat.transformation", "LambdaAIChatConfig"),
    "InceptionChatConfig": (
        ".llms.inception.chat.transformation",
        "InceptionChatConfig",
    ),
    "HyperbolicChatConfig": (
        ".llms.hyperbolic.chat.transformation",
        "HyperbolicChatConfig",
    ),
    "VercelAIGatewayConfig": (
        ".llms.vercel_ai_gateway.chat.transformation",
        "VercelAIGatewayConfig",
    ),
    "EdenAIChatConfig": (".llms.edenai.chat.transformation", "EdenAIChatConfig"),
    "EdenAIResponsesAPIConfig": (".llms.edenai.responses.transformation", "EdenAIResponsesAPIConfig"),
    "EdenAIAnthropicMessagesConfig": (".llms.edenai.messages.transformation", "EdenAIAnthropicMessagesConfig"),
    "EdenAIEmbeddingConfig": (".llms.edenai.embedding.transformation", "EdenAIEmbeddingConfig"),
    "EdenAIAudioTranscriptionConfig": (
        ".llms.edenai.audio_transcription.transformation",
        "EdenAIAudioTranscriptionConfig",
    ),
    "EdenAITextToSpeechConfig": (".llms.edenai.text_to_speech.transformation", "EdenAITextToSpeechConfig"),
    "EdenAIImageGenerationConfig": (".llms.edenai.image_generation.transformation", "EdenAIImageGenerationConfig"),
    "EdenAIVideoConfig": (".llms.edenai.videos.transformation", "EdenAIVideoConfig"),
    "FalAIChatConfig": (".llms.fal_ai.chat.transformation", "FalAIChatConfig"),
    "FalAIError": (".llms.fal_ai.chat.transformation", "FalAIError"),
    "OVHCloudChatConfig": (".llms.ovhcloud.chat.transformation", "OVHCloudChatConfig"),
    "OVHCloudEmbeddingConfig": (
        ".llms.ovhcloud.embedding.transformation",
        "OVHCloudEmbeddingConfig",
    ),
    "CometAPIEmbeddingConfig": (
        ".llms.cometapi.embed.transformation",
        "CometAPIEmbeddingConfig",
    ),
    "LemonadeChatConfig": (".llms.lemonade.chat.transformation", "LemonadeChatConfig"),
    "SnowflakeEmbeddingConfig": (
        ".llms.snowflake.embedding.transformation",
        "SnowflakeEmbeddingConfig",
    ),
    "AmazonNovaChatConfig": (
        ".llms.amazon_nova.chat.transformation",
        "AmazonNovaChatConfig",
    ),
    "SonioxAudioTranscriptionConfig": (
        ".llms.soniox.audio_transcription.transformation",
        "SonioxAudioTranscriptionConfig",
    ),
}

# Import map for utils module lazy imports
_UTILS_MODULE_IMPORT_MAP: Final = {
    "encoding": ("hangarllm.main", "encoding"),
    "BaseVectorStore": (
        "hangarllm.integrations.vector_store_integrations.base_vector_store",
        "BaseVectorStore",
    ),
    "CredentialAccessor": (
        "hangarllm.hangarllm_core_utils.credential_accessor",
        "CredentialAccessor",
    ),
    "exception_type": (
        "hangarllm.hangarllm_core_utils.exception_mapping_utils",
        "exception_type",
    ),
    "get_error_message": (
        "hangarllm.hangarllm_core_utils.exception_mapping_utils",
        "get_error_message",
    ),
    "_get_response_headers": (
        "hangarllm.hangarllm_core_utils.exception_mapping_utils",
        "_get_response_headers",
    ),
    "get_llm_provider": (
        "hangarllm.hangarllm_core_utils.get_llm_provider_logic",
        "get_llm_provider",
    ),
    "_is_non_openai_azure_model": (
        "hangarllm.hangarllm_core_utils.get_llm_provider_logic",
        "is_non_openai_azure_model",
    ),
    "is_non_openai_azure_model": (
        "hangarllm.hangarllm_core_utils.get_llm_provider_logic",
        "is_non_openai_azure_model",
    ),
    "get_supported_openai_params": (
        "hangarllm.hangarllm_core_utils.get_supported_openai_params",
        "get_supported_openai_params",
    ),
    "HangarLLMResponseObjectHandler": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "HangarLLMResponseObjectHandler",
    ),
    "_handle_invalid_parallel_tool_calls": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "handle_invalid_parallel_tool_calls",
    ),
    "handle_invalid_parallel_tool_calls": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "handle_invalid_parallel_tool_calls",
    ),
    "convert_to_model_response_object": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "convert_to_model_response_object",
    ),
    "convert_to_streaming_response": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "convert_to_streaming_response",
    ),
    "convert_to_streaming_response_async": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.convert_dict_to_response",
        "convert_to_streaming_response_async",
    ),
    "get_api_base": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.get_api_base",
        "get_api_base",
    ),
    "ResponseMetadata": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.response_metadata",
        "ResponseMetadata",
    ),
    "_parse_content_for_reasoning": (
        "hangarllm.hangarllm_core_utils.prompt_templates.common_utils",
        "parse_content_for_reasoning",
    ),
    "parse_content_for_reasoning": (
        "hangarllm.hangarllm_core_utils.prompt_templates.common_utils",
        "parse_content_for_reasoning",
    ),
    "HangarLLMLoggingObject": (
        "hangarllm.hangarllm_core_utils.redact_messages",
        "HangarLLMLoggingObject",
    ),
    "redact_message_input_output_from_logging": (
        "hangarllm.hangarllm_core_utils.redact_messages",
        "redact_message_input_output_from_logging",
    ),
    "CustomStreamWrapper": (
        "hangarllm.hangarllm_core_utils.streaming_handler",
        "CustomStreamWrapper",
    ),
    "BaseGoogleGenAIGenerateContentConfig": (
        "hangarllm.llms.base_llm.google_genai.transformation",
        "BaseGoogleGenAIGenerateContentConfig",
    ),
    "BaseSearchConfig": (
        "hangarllm.llms.base_llm.search.transformation",
        "BaseSearchConfig",
    ),
    "BaseTextToSpeechConfig": (
        "hangarllm.llms.base_llm.text_to_speech.transformation",
        "BaseTextToSpeechConfig",
    ),
    "BedrockModelInfo": ("hangarllm.llms.bedrock.common_utils", "BedrockModelInfo"),
    "CohereModelInfo": ("hangarllm.llms.cohere.common_utils", "CohereModelInfo"),
    "Rules": ("hangarllm.hangarllm_core_utils.rules", "Rules"),
    "AsyncHTTPHandler": ("hangarllm.llms.custom_httpx.http_handler", "AsyncHTTPHandler"),
    "HTTPHandler": ("hangarllm.llms.custom_httpx.http_handler", "HTTPHandler"),
    "get_num_retries_from_retry_policy": (
        "hangarllm.hangarllm_core_utils.get_retry_from_policy",
        "get_num_retries_from_retry_policy",
    ),
    "reset_retry_policy": (
        "hangarllm.hangarllm_core_utils.get_retry_from_policy",
        "reset_retry_policy",
    ),
    "get_coroutine_checker": (
        "hangarllm.hangarllm_core_utils.cached_imports",
        "get_coroutine_checker",
    ),
    "get_hangarllm_logging_class": (
        "hangarllm.hangarllm_core_utils.cached_imports",
        "get_hangarllm_logging_class",
    ),
    "get_set_callbacks": (
        "hangarllm.hangarllm_core_utils.cached_imports",
        "get_set_callbacks",
    ),
    "get_hangarllm_metadata_from_kwargs": (
        "hangarllm.hangarllm_core_utils.core_helpers",
        "get_hangarllm_metadata_from_kwargs",
    ),
    "map_finish_reason": (
        "hangarllm.hangarllm_core_utils.core_helpers",
        "map_finish_reason",
    ),
    "process_response_headers": (
        "hangarllm.hangarllm_core_utils.core_helpers",
        "process_response_headers",
    ),
    "delete_nested_value": (
        "hangarllm.hangarllm_core_utils.dot_notation_indexing",
        "delete_nested_value",
    ),
    "is_nested_path": (
        "hangarllm.hangarllm_core_utils.dot_notation_indexing",
        "is_nested_path",
    ),
    "_get_base_model_from_hangarllm_call_metadata": (
        "hangarllm.hangarllm_core_utils.get_hangarllm_params",
        "get_base_model_from_hangarllm_call_metadata",
    ),
    "get_base_model_from_hangarllm_call_metadata": (
        "hangarllm.hangarllm_core_utils.get_hangarllm_params",
        "get_base_model_from_hangarllm_call_metadata",
    ),
    "get_hangarllm_params": (
        "hangarllm.hangarllm_core_utils.get_hangarllm_params",
        "get_hangarllm_params",
    ),
    "_ensure_extra_body_is_safe": (
        "hangarllm.hangarllm_core_utils.llm_request_utils",
        "ensure_extra_body_is_safe",
    ),
    "ensure_extra_body_is_safe": (
        "hangarllm.hangarllm_core_utils.llm_request_utils",
        "ensure_extra_body_is_safe",
    ),
    "get_formatted_prompt": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.get_formatted_prompt",
        "get_formatted_prompt",
    ),
    "get_response_headers": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.get_headers",
        "get_response_headers",
    ),
    "update_response_metadata": (
        "hangarllm.hangarllm_core_utils.llm_response_utils.response_metadata",
        "update_response_metadata",
    ),
    "executor": ("hangarllm.hangarllm_core_utils.thread_pool_executor", "executor"),
    "BaseAnthropicMessagesConfig": (
        "hangarllm.llms.base_llm.anthropic_messages.transformation",
        "BaseAnthropicMessagesConfig",
    ),
    "BaseAudioTranscriptionConfig": (
        "hangarllm.llms.base_llm.audio_transcription.transformation",
        "BaseAudioTranscriptionConfig",
    ),
    "BaseBatchesConfig": (
        "hangarllm.llms.base_llm.batches.transformation",
        "BaseBatchesConfig",
    ),
    "BaseContainerConfig": (
        "hangarllm.llms.base_llm.containers.transformation",
        "BaseContainerConfig",
    ),
    "BaseEmbeddingConfig": (
        "hangarllm.llms.base_llm.embedding.transformation",
        "BaseEmbeddingConfig",
    ),
    "BaseImageEditConfig": (
        "hangarllm.llms.base_llm.image_edit.transformation",
        "BaseImageEditConfig",
    ),
    "BaseImageGenerationConfig": (
        "hangarllm.llms.base_llm.image_generation.transformation",
        "BaseImageGenerationConfig",
    ),
    "BaseImageVariationConfig": (
        "hangarllm.llms.base_llm.image_variations.transformation",
        "BaseImageVariationConfig",
    ),
    "BasePassthroughConfig": (
        "hangarllm.llms.base_llm.passthrough.transformation",
        "BasePassthroughConfig",
    ),
    "BaseRealtimeConfig": (
        "hangarllm.llms.base_llm.realtime.transformation",
        "BaseRealtimeConfig",
    ),
    "BaseRerankConfig": (
        "hangarllm.llms.base_llm.rerank.transformation",
        "BaseRerankConfig",
    ),
    "BaseVectorStoreConfig": (
        "hangarllm.llms.base_llm.vector_store.transformation",
        "BaseVectorStoreConfig",
    ),
    "BaseVectorStoreFilesConfig": (
        "hangarllm.llms.base_llm.vector_store_files.transformation",
        "BaseVectorStoreFilesConfig",
    ),
    "BaseVideoConfig": (
        "hangarllm.llms.base_llm.videos.transformation",
        "BaseVideoConfig",
    ),
    "ANTHROPIC_API_ONLY_HEADERS": (
        "hangarllm.types.llms.anthropic",
        "ANTHROPIC_API_ONLY_HEADERS",
    ),
    "AnthropicThinkingParam": (
        "hangarllm.types.llms.anthropic",
        "AnthropicThinkingParam",
    ),
    "RerankResponse": ("hangarllm.types.rerank", "RerankResponse"),
    "ChatCompletionDeltaToolCallChunk": (
        "hangarllm.types.llms.openai",
        "ChatCompletionDeltaToolCallChunk",
    ),
    "ChatCompletionToolCallChunk": (
        "hangarllm.types.llms.openai",
        "ChatCompletionToolCallChunk",
    ),
    "ChatCompletionToolCallFunctionChunk": (
        "hangarllm.types.llms.openai",
        "ChatCompletionToolCallFunctionChunk",
    ),
    "HangarLLM_Params": ("hangarllm.types.router", "HangarLLM_Params"),
}

# Export all name tuples and import maps for use in _lazy_imports.py
__all__ = [
    "BEDROCK_TYPES_NAMES",
    "CACHING_NAMES",
    "COST_CALCULATOR_NAMES",
    "DOTPROMPT_NAMES",
    "HTTP_HANDLER_NAMES",
    "HANGARLLM_LOGGING_NAMES",
    "LLM_CLIENT_CACHE_NAMES",
    "LLM_CONFIG_NAMES",
    "LLM_PROVIDER_LOGIC_NAMES",
    "TOKEN_COUNTER_NAMES",
    "TYPES_NAMES",
    "TYPES_UTILS_NAMES",
    "UTILS_MODULE_NAMES",
    "UTILS_NAMES",
    "_BEDROCK_TYPES_IMPORT_MAP",
    "_CACHING_IMPORT_MAP",
    "_COST_CALCULATOR_IMPORT_MAP",
    "_DOTPROMPT_IMPORT_MAP",
    "_HANGARLLM_LOGGING_IMPORT_MAP",
    "_LLM_CONFIGS_IMPORT_MAP",
    "_LLM_PROVIDER_LOGIC_IMPORT_MAP",
    "_TOKEN_COUNTER_IMPORT_MAP",
    "_TYPES_IMPORT_MAP",
    "_TYPES_UTILS_IMPORT_MAP",
    "_UTILS_IMPORT_MAP",
    "_UTILS_MODULE_IMPORT_MAP",
]
