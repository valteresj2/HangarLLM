"""
Test that max_budget from environment variable (string) is correctly
converted to float.
GitHub Issue: #23843
"""

from unittest.mock import patch

import pytest

import hangarllm


@pytest.mark.asyncio
async def test_max_budget_string_converted_to_float():
    """
    When max_budget is set via os.environ/MAX_BUDGET, it arrives as a
    string. initialize() should convert it to float so the comparison
    `hangarllm.max_budget > 0` doesn't raise TypeError.
    """
    with patch("hangarllm.proxy.proxy_server.generate_feedback_box"):
        from hangarllm.proxy.proxy_server import initialize

        original = hangarllm.max_budget
        try:
            await initialize(max_budget="100.5")
            assert isinstance(hangarllm.max_budget, float)
            assert hangarllm.max_budget == 100.5
        finally:
            hangarllm.max_budget = original


@pytest.mark.asyncio
async def test_max_budget_float_stays_float():
    """max_budget as float should still work."""
    with patch("hangarllm.proxy.proxy_server.generate_feedback_box"):
        from hangarllm.proxy.proxy_server import initialize

        original = hangarllm.max_budget
        try:
            await initialize(max_budget=200.0)
            assert isinstance(hangarllm.max_budget, float)
            assert hangarllm.max_budget == 200.0
        finally:
            hangarllm.max_budget = original
