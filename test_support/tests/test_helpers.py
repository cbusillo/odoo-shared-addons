import contextlib
import random
import secrets
import time
from collections.abc import Generator
from datetime import datetime
from typing import Any, Protocol
from unittest.mock import MagicMock, patch

from odoo.models import BaseModel


def generate_unique_sku() -> str:
    return str(random.randint(10000000, 99999999))


def generate_unique_name(base_name: str) -> str:
    return f"{base_name} {datetime.now().timestamp()}"


def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


class EnvironmentWithContext(Protocol):
    def with_context(self, **kwargs: object) -> "EnvironmentWithContext": ...


def with_test_context(env: EnvironmentWithContext) -> EnvironmentWithContext:
    from .base_types import DEFAULT_TEST_CONTEXT

    return env.with_context(**DEFAULT_TEST_CONTEXT)


@contextlib.contextmanager
def mock_datetime_now(fixed_datetime: datetime) -> Generator[None]:
    with patch("datetime.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_datetime
        mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)
        yield


def assert_fields_equal(
    record: object,
    expected: dict[str, Any],
    message_prefix: str = "",
) -> None:
    errors = []
    for field, expected_value in expected.items():
        actual_value = getattr(record, field, None)
        if actual_value != expected_value:
            error = f"Field '{field}': expected {expected_value!r}, got {actual_value!r}"
            if message_prefix:
                error = f"{message_prefix} - {error}"
            errors.append(error)

    if errors:
        raise AssertionError("\n".join(errors))


def assert_record_count(
    model: BaseModel,
    domain: list,
    expected_count: int,
    message: str | None = None,
) -> None:
    actual_count = model.search_count(domain)
    if actual_count != expected_count:
        msg = message or f"Expected {expected_count} records, found {actual_count}"
        msg += f"\nDomain: {domain}"
        raise AssertionError(msg)


def assert_in_log(
    log_records: list,
    expected_message: str,
    level: str | None = None,
) -> None:
    for record in log_records:
        if expected_message in record.message and (level is None or record.levelname == level):
            return

    msg = f"Expected log message not found: {expected_message!r}"
    if level:
        msg += f" at level {level}"
    raise AssertionError(msg)


@contextlib.contextmanager
def measure_performance(
    operation_name: str,
    max_duration: float | None = None,
) -> Generator[dict[str, Any]]:
    metrics = {
        "operation": operation_name,
        "start_time": time.perf_counter(),
        "end_time": None,
        "duration": None,
    }

    try:
        yield metrics
    finally:
        metrics["end_time"] = time.perf_counter()
        metrics["duration"] = metrics["end_time"] - metrics["start_time"]

        if max_duration and metrics["duration"] > max_duration:
            raise AssertionError(
                f"Operation '{operation_name}' took {metrics['duration']:.3f}s, exceeding maximum of {max_duration:.3f}s"
            )


__all__ = [
    "generate_unique_sku",
    "generate_unique_name",
    "generate_secure_token",
    "EnvironmentWithContext",
    "with_test_context",
    "mock_datetime_now",
    "assert_fields_equal",
    "assert_record_count",
    "assert_in_log",
    "measure_performance",
]
