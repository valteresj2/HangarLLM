from typing import Literal

from hangarllm.types.llms.base import HangarLLMBaseModel

ModelInsightsMetric = Literal["requests", "spend", "tokens"]


class ModelInsightMetric(HangarLLMBaseModel):
    model_group: str
    model: str
    provider: str
    spend: float
    prompt_tokens: int
    completion_tokens: int
    requests: int
    successful_requests: int
    failed_requests: int


class ModelInsightDailyMetric(ModelInsightMetric):
    date: str


class ModelInsightDailyTotal(HangarLLMBaseModel):
    date: str
    spend: float
    prompt_tokens: int
    completion_tokens: int
    requests: int


class ModelInsightTask(HangarLLMBaseModel):
    task_type: str
    label: str
    category: str


class ModelInsightTaskSummary(ModelInsightTask):
    value: float
    share: float
    leader: str
    provider: str


class ModelInsightsResponse(HangarLLMBaseModel):
    start_date: str
    end_date: str
    daily: list[ModelInsightDailyMetric]
    daily_totals: tuple[ModelInsightDailyTotal, ...]
    top_models: list[ModelInsightMetric]


class ModelInsightTasksResponse(HangarLLMBaseModel):
    start_date: str
    end_date: str
    tasks: list[ModelInsightTaskSummary]
