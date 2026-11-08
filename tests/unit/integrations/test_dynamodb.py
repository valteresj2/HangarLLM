from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Final
from unittest.mock import MagicMock

import pytest

import hangarllm
from hangarllm.constants import INTERNAL_CALL_ORIGIN_METADATA_KEY
from hangarllm.integrations.dynamodb import DyanmoDBLogger
from hangarllm.hangarllm_core_utils.internal_call_metadata import BACKGROUND_RESPONSE_COST_REQUEST_ID_SUFFIX
from hangarllm.types.passthrough_endpoints.pass_through_endpoints import (
    SETTLES_BACKGROUND_RESPONSE_KWARG,
    BackgroundResponseSettlement,
)
from hangarllm.types.utils import BACKGROUND_RESPONSE_COST_POLL_CALL_ORIGIN

BACKGROUND_COST_POLL_KWARGS: Final[Mapping[str, object]] = {
    "call_type": "aget_responses",
    "hangarllm_params": {"metadata": {INTERNAL_CALL_ORIGIN_METADATA_KEY: BACKGROUND_RESPONSE_COST_POLL_CALL_ORIGIN}},
}
PASSTHROUGH_SETTLEMENT_KWARGS: Final[Mapping[str, object]] = {
    "call_type": "pass_through_endpoint",
    "hangarllm_params": {"metadata": {}},
    SETTLES_BACKGROUND_RESPONSE_KWARG: BackgroundResponseSettlement.SETTLES,
}


@pytest.mark.parametrize(
    "cost_kwargs",
    (
        pytest.param(BACKGROUND_COST_POLL_KWARGS, id="cost-poll"),
        pytest.param(PASSTHROUGH_SETTLEMENT_KWARGS, id="passthrough-settlement"),
    ),
)
@pytest.mark.usefixtures("sdk_only_install")
def test_background_cost_event_keeps_its_own_item_beside_its_create(
    monkeypatch: pytest.MonkeyPatch, cost_kwargs: Mapping[str, object]
) -> None:
    monkeypatch.setattr(hangarllm, "dynamodb_table_name", "hangarllm-logs")
    dynamodb: Final = MagicMock()
    logger: Final = DyanmoDBLogger(dynamodb=dynamodb)
    response_obj: Final = {"id": "resp_YWJjZA", "usage": {"total_tokens": 3}}
    now: Final = datetime.now(timezone.utc)
    create_kwargs: Final[Mapping[str, object]] = {"call_type": "aresponses", "hangarllm_params": {"metadata": {}}}

    for kwargs in (create_kwargs, cost_kwargs):
        logger.log_event(kwargs, response_obj, now, now, print_verbose=print)

    dynamodb.Table.assert_called_with("hangarllm-logs")
    written_ids: Final = [call.kwargs["Item"]["id"] for call in dynamodb.Table.return_value.put_item.call_args_list]
    assert written_ids == ["resp_YWJjZA", f"resp_YWJjZA{BACKGROUND_RESPONSE_COST_REQUEST_ID_SUFFIX}"]
