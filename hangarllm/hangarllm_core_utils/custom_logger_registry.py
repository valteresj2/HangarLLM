"""
Registry mapping the callback class string to the class type.

This is used to get the class type from the callback class string.

Example:
    "datadog" -> DataDogLogger
    "prometheus" -> PrometheusLogger
"""

from typing import Final

from hangarllm import _custom_logger_compatible_callbacks_literal
from hangarllm.integrations.agentops import AgentOps
from hangarllm.integrations.anthropic_cache_control_hook import AnthropicCacheControlHook
from hangarllm.integrations.argilla import ArgillaLogger
from hangarllm.integrations.azure_sentinel.azure_sentinel import AzureSentinelLogger
from hangarllm.integrations.azure_storage.azure_storage import AzureBlobStorageLogger
from hangarllm.integrations.bitbucket import BitBucketPromptManager
from hangarllm.integrations.braintrust_logging import BraintrustLogger
from hangarllm.integrations.cloudzero.cloudzero import CloudZeroLogger
from hangarllm.integrations.datadog.datadog import DataDogLogger
from hangarllm.integrations.datadog.datadog_llm_obs import DataDogLLMObsLogger
from hangarllm.integrations.datadog.datadog_metrics import DatadogMetricsLogger
from hangarllm.integrations.deepeval import DeepEvalLogger
from hangarllm.integrations.dotprompt import DotpromptManager
from hangarllm.integrations.focus.focus_logger import FocusLogger
from hangarllm.integrations.galileo import GalileoObserve
from hangarllm.integrations.gcs_bucket.gcs_bucket import GCSBucketLogger
from hangarllm.integrations.gcs_pubsub.pub_sub import GcsPubSubLogger
from hangarllm.integrations.gitlab import GitLabPromptManager
from hangarllm.integrations.hangarllm_agent import HangarLLMAgentModelResolver
from hangarllm.integrations.humanloop import HumanloopLogger
from hangarllm.integrations.lago import LagoLogger
from hangarllm.integrations.langfuse.langfuse_prompt_management import (
    LangfusePromptManagement,
)
from hangarllm.integrations.langsmith import LangsmithLogger
from hangarllm.integrations.literal_ai import LiteralAILogger
from hangarllm.integrations.mavvrik_focus.mavvrik_focus_logger import MavvrikFocusLogger
from hangarllm.integrations.mlflow import MlflowLogger
from hangarllm.integrations.newrelic import NewRelicLogger
from hangarllm.integrations.openmeter import OpenMeterLogger
from hangarllm.integrations.opentelemetry import OpenTelemetry
from hangarllm.integrations.opik.opik import OpikLogger
from hangarllm.integrations.pointfive import PointFiveLogger
from hangarllm.integrations.posthog import PostHogLogger
from hangarllm.integrations.prometheus import PrometheusLogger
from hangarllm.integrations.s3_v2 import S3Logger
from hangarllm.integrations.sqs import SQSLogger
from hangarllm.integrations.ternary.ternary_logger import TernaryLogger
from hangarllm.integrations.vantage.vantage_logger import VantageLogger
from hangarllm.integrations.vector_store_integrations.vector_store_pre_call_hook import (
    VectorStorePreCallHook,
)
from hangarllm.integrations.zerobus import ZerobusLogger
from hangarllm.proxy.hooks.dynamic_rate_limiter import (  # noqa: F401  # legacy module exports
    PROXY_DynamicRateLimitHandler,
    _PROXY_DynamicRateLimitHandler,  # pyright: ignore[reportPrivateUsage,reportUnusedImport]  # backwards-compatible package export
)
from hangarllm.proxy.hooks.dynamic_rate_limiter_v3 import (  # noqa: F401  # legacy module exports
    PROXY_DynamicRateLimitHandlerV3,
    _PROXY_DynamicRateLimitHandlerV3,  # pyright: ignore[reportPrivateUsage,reportUnusedImport]  # backwards-compatible package export
)


class CustomLoggerRegistry:
    """
    Registry mapping the callback class string to the class type.
    """

    CALLBACK_CLASS_STR_TO_CLASS_TYPE = {
        "lago": LagoLogger,
        "openmeter": OpenMeterLogger,
        "braintrust": BraintrustLogger,
        "galileo": GalileoObserve,
        "langsmith": LangsmithLogger,
        "literalai": LiteralAILogger,
        "hangarllm_agent": HangarLLMAgentModelResolver,
        "prometheus": PrometheusLogger,
        "datadog": DataDogLogger,
        "datadog_llm_observability": DataDogLLMObsLogger,
        "datadog_metrics": DatadogMetricsLogger,
        "gcs_bucket": GCSBucketLogger,
        "opik": OpikLogger,
        "argilla": ArgillaLogger,
        "opentelemetry": OpenTelemetry,
        "azure_sentinel": AzureSentinelLogger,
        "azure_storage": AzureBlobStorageLogger,
        "humanloop": HumanloopLogger,
        # OTEL compatible loggers
        "logfire": OpenTelemetry,
        "arize": OpenTelemetry,
        "langfuse_otel": OpenTelemetry,
        "arize_phoenix": OpenTelemetry,
        "langtrace": OpenTelemetry,
        "weave_otel": OpenTelemetry,
        "levo": OpenTelemetry,
        "signoz": OpenTelemetry,
        "mlflow": MlflowLogger,
        "langfuse": LangfusePromptManagement,
        "otel": OpenTelemetry,
        "gcs_pubsub": GcsPubSubLogger,
        "anthropic_cache_control_hook": AnthropicCacheControlHook,
        "agentops": AgentOps,
        "deepeval": DeepEvalLogger,
        "s3_v2": S3Logger,
        "pointfive": PointFiveLogger,
        "zerobus": ZerobusLogger,
        "aws_sqs": SQSLogger,
        "dynamic_rate_limiter": PROXY_DynamicRateLimitHandler,
        "dynamic_rate_limiter_v3": PROXY_DynamicRateLimitHandlerV3,
        "vector_store_pre_call_hook": VectorStorePreCallHook,
        "dotprompt": DotpromptManager,
        "bitbucket": BitBucketPromptManager,
        "gitlab": GitLabPromptManager,
        "cloudzero": CloudZeroLogger,
        "focus": FocusLogger,
        "mavvrik": MavvrikFocusLogger,
        "vantage": VantageLogger,
        "ternary": TernaryLogger,
        "posthog": PostHogLogger,
        "newrelic": NewRelicLogger,
    }

    try:
        from hangarllm.hangar.callbacks.pagerduty import (
            PagerDutyAlerting,
        )
        from hangarllm.hangar.emails.resend_email import (
            ResendEmailLogger,
        )
        from hangarllm.hangar.emails.sendgrid_email import (
            SendGridEmailLogger,
        )
        from hangarllm.hangar.emails.smtp_email import (
            SMTPEmailLogger,
        )
        from hangarllm.integrations.generic_api.generic_api_callback import (
            GenericAPILogger,
        )

        enterprise_loggers = {
            "pagerduty": PagerDutyAlerting,
            "generic_api": GenericAPILogger,
            "resend_email": ResendEmailLogger,
            "sendgrid_email": SendGridEmailLogger,
            "smtp_email": SMTPEmailLogger,
        }
        CALLBACK_CLASS_STR_TO_CLASS_TYPE.update(enterprise_loggers)
    except ImportError:
        pass  # enterprise not installed

    @classmethod
    def get_callback_str_from_class_type(cls, class_type: type) -> str | None:
        """
        Get the callback string from the class type.

        Args:
            class_type: The class type to find the string for

        Returns:
            str: The callback string, or None if not found
        """
        for (
            callback_str,
            callback_class,
        ) in cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE.items():
            if callback_class == class_type:
                return callback_str
        return None

    @classmethod
    def get_all_callback_strs_from_class_type(cls, class_type: type) -> list[str]:
        """
        Get all callback strings that map to the same class type.
        Some class types (like OpenTelemetry) have multiple string mappings.

        Args:
            class_type: The class type to find all strings for

        Returns:
            list: List of callback strings that map to the class type
        """
        callback_strs: Final[list[str]] = []
        for (
            callback_str,
            callback_class,
        ) in cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE.items():
            if callback_class == class_type:
                callback_strs.append(callback_str)
        return callback_strs

    @classmethod
    def get_class_type_for_custom_logger_name(
        cls,
        custom_logger_name: _custom_logger_compatible_callbacks_literal,
    ) -> type:
        """
        Get the class type for a given custom logger name
        """
        return cls.CALLBACK_CLASS_STR_TO_CLASS_TYPE[custom_logger_name]
