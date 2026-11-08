import importlib
import logging
from collections.abc import Iterator

import pytest

import hangarllm_proxy_extras._logging as extras_logging


@pytest.fixture
def fresh_extras_logger() -> Iterator[logging.Logger]:
    logger = logging.getLogger("hangarllm_proxy_extras")
    saved_handlers = logger.handlers[:]
    saved_level = logger.level
    logger.handlers[:] = []
    try:
        yield logger
    finally:
        logger.handlers[:] = saved_handlers
        logger.setLevel(saved_level)


def test_hangarllm_log_error_silences_extras_info_lines(monkeypatch, fresh_extras_logger):
    monkeypatch.setenv("HANGARLLM_LOG", "ERROR")
    reloaded = importlib.reload(extras_logging).logger
    assert reloaded is fresh_extras_logger
    assert reloaded.isEnabledFor(logging.INFO) is False
    assert reloaded.isEnabledFor(logging.ERROR) is True


@pytest.mark.parametrize("hangarllm_log", [None, "info", "DEBUG"])
def test_unset_or_verbose_hangarllm_log_keeps_extras_info_lines(monkeypatch, fresh_extras_logger, hangarllm_log):
    if hangarllm_log is None:
        monkeypatch.delenv("HANGARLLM_LOG", raising=False)
    else:
        monkeypatch.setenv("HANGARLLM_LOG", hangarllm_log)
    assert importlib.reload(extras_logging).logger.isEnabledFor(logging.INFO) is True
