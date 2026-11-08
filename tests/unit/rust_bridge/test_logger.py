import logging
from typing import Final

import pytest

import hangarllm
from hangarllm._logging import (
    DiagnosticProcessingFilter,
    _python_process_diagnostic,
    redact_secrets,
    session_id_var,
    trace_id_var,
    verbose_logger,
)
from hangarllm.constants import MINIMUM_CUSTOM_KEY_LENGTH
from hangarllm.hangarllm_core_utils.secret_redaction import (
    _python_redact_internal_details,
    python_redact_string,
    python_redact_structured_value,
)
from hangarllm.rust_bridge import diagnostics, logger


def test_native_records_preserve_metadata_and_redact_before_custom_handlers(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(verbose_logger, "handlers", [])
    secret: Final = "sk-" + "a" * 48
    message: Final = f"Authorization: Bearer {secret}"
    with caplog.at_level(logging.WARNING, logger="HangarLLM"):
        logger.emit(
            logging.WARNING, message, "native.rs", 42, "hangarllm_http", {"retry": True, "api_key": secret}, ("", "")
        )

    record: Final = caplog.records[0]
    assert len(caplog.records) == 1
    assert record.getMessage() == redact_secrets(message)
    assert secret not in record.getMessage()
    assert (record.pathname, record.lineno, record.funcName) == ("native.rs", 42, "hangarllm_http")
    assert record.__dict__["rust_fields"]["retry"] is True
    assert secret not in str(record.__dict__["rust_fields"])


def test_native_context_is_scoped_and_respects_correlation_setting(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(hangarllm, "request_correlation_in_logs", True)
    context_before: Final = logger.context()
    with caplog.at_level(logging.WARNING, logger="HangarLLM"):
        logger.emit(logging.WARNING, "native", "native.rs", 1, "hangarllm_http", {}, ("session", "trace"))
        monkeypatch.setattr(hangarllm, "request_correlation_in_logs", False)
        logger.emit(logging.WARNING, "disabled", "native.rs", 2, "hangarllm_http", {}, ("hidden", "hidden"))

    first, second = caplog.records
    assert (first.__dict__["session_id"], first.__dict__["trace_id"]) == ("session", "trace")
    assert "session_id" not in second.__dict__
    assert "trace_id" not in second.__dict__
    assert (session_id_var.get(), trace_id_var.get()) == context_before


def test_native_logging_observes_level_changes(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.ERROR, logger="HangarLLM"):
        assert not logger.enabled(logging.WARNING)
        logger.emit(logging.WARNING, "filtered", "native.rs", 1, "hangarllm_http", {}, ("", ""))
    with caplog.at_level(logging.WARNING, logger="HangarLLM"):
        assert logger.enabled(logging.WARNING)
        logger.emit(logging.WARNING, "visible", "native.rs", 1, "hangarllm_http", {}, ("", ""))

    assert [record.getMessage() for record in caplog.records] == ["visible"]


def test_native_redis_timeouts_share_the_redis_py_timeout_throttle(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from redis.exceptions import TimeoutError as RedisTimeoutError

    from hangarllm.caching import redis_cache as redis_cache_module
    from hangarllm.caching.redis_cache import RedisTimeoutLogThrottle, log_redis_failure

    monkeypatch.setattr(
        redis_cache_module, "redis_timeout_log_throttle", RedisTimeoutLogThrottle(interval=5.0, clock=lambda: 1_000.0)
    )
    store: Final = "hangarllm_redis_store::rate_limits"
    with caplog.at_level(logging.DEBUG, logger="HangarLLM"):
        logger.emit(logging.WARNING, "native timeout", "mod.rs", 1, store, {"redis.failure": "timeout"}, ("", ""))
        log_redis_failure(verbose_logger, logging.WARNING, "redis-py timeout", RedisTimeoutError("timed out"))
        logger.emit(logging.WARNING, "native timeout again", "mod.rs", 2, store, {"redis.failure": "timeout"}, ("", ""))
        logger.emit(logging.WARNING, "native refused", "mod.rs", 3, store, {"redis.failure": "transport"}, ("", ""))

    assert [(record.getMessage(), record.levelno) for record in caplog.records] == [
        ("native timeout", logging.WARNING),
        ("redis-py timeout: timed out", logging.DEBUG),
        ("native timeout again", logging.DEBUG),
        ("native refused", logging.WARNING),
    ]


@pytest.mark.parametrize(
    "text",
    (
        "Authorization: Bearer abcdefghijklmnop",
        "s3_secret_access_key=secret123",
        "postgres://user:pass@database.internal/name",
        '{"type":"service_account","private_key":"secret123"}',
        "GET /v1?key=abcdefghij&page=2",
    ),
)
def test_native_credential_patterns_match_python(text: str) -> None:
    from hangarllm.rust_bridge._native import NativeDiagnosticProcessor

    processor: Final = NativeDiagnosticProcessor(MINIMUM_CUSTOM_KEY_LENGTH)
    assert processor.redact_text(text) == python_redact_string(text)
    assert processor.redact_structured_text("api_key", "secret123") == python_redact_structured_value(
        "api_key", "secret123"
    )


def test_native_client_redaction_matches_python() -> None:
    from hangarllm.rust_bridge._native import NativeDiagnosticProcessor

    text: Final = "error at /etc/secrets/config on db.internal\nTraceback (most recent call last):\nsecret"
    processor: Final = NativeDiagnosticProcessor(MINIMUM_CUSTOM_KEY_LENGTH)
    assert processor.redact_client_message(text) == _python_redact_internal_details(text)


def test_native_diagnostic_batch_matches_python() -> None:
    from hangarllm.rust_bridge._native import NativeDiagnosticProcessor

    message: Final = "é" * 110 + "sk-" + "q" * 48 + "界" * 1000
    exception: Final = "document=" + "Q" * 200
    stack: Final = "api_key=secret123"
    leaves: Final = (("api_key", "secret123"), (None, "safe"))
    processor: Final = NativeDiagnosticProcessor(MINIMUM_CUSTOM_KEY_LENGTH)
    rust: Final = processor.process_diagnostic(message, exception, stack, leaves, (True, 20, 500))
    python: Final = _python_process_diagnostic(message, exception, stack, leaves, True, 20, 500)

    assert rust[:3] == python[:3]
    assert tuple(rust[3]) == python[3]
    assert rust[4] == python[4]
    assert "sk-qq" not in rust[0]
    assert len(rust[0]) <= 500
    assert rust[3] == ["REDACTED", "safe"]


def test_missing_native_diagnostic_processor_falls_back_before_record_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HANGARLLM_RUST", "1")
    diagnostics.PROCESSOR.override(None)
    try:
        record: Final = logging.makeLogRecord({"name": "HangarLLM", "levelno": logging.INFO, "msg": "api_key=secret123"})
        assert DiagnosticProcessingFilter().filter(record) is True
        assert record.getMessage() == "REDACTED"
    finally:
        diagnostics.PROCESSOR.reset()


def test_unsupported_unicode_uses_safe_python_redaction(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HANGARLLM_RUST", "1")
    assert redact_secrets("broken\ud800 api_key=secret123") == "broken\ud800 REDACTED"
