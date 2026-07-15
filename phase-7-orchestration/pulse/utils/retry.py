"""Tiny retry-with-backoff helper used by ingestion fetchers (edge cases X1.2/X1.3/X1.15)."""

from __future__ import annotations

import logging
import time
from typing import Callable, TypeVar

logger = logging.getLogger("pulse.ingestion")

T = TypeVar("T")


def _is_non_retryable(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(tok in text for tok in ("403", "401", "blocked", "forbidden", "unauthorized"))


def with_retries(
    fn: Callable[[], T],
    *,
    max_retries: int = 3,
    backoff_seconds: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
    label: str = "operation",
) -> T:
    """Call ``fn`` with up to ``max_retries`` retries on exception (exponential backoff)."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 - transient source/network errors
            if _is_non_retryable(exc):
                logger.warning("%s failed without retry (client error): %s", label, exc)
                raise
            attempt += 1
            if attempt > max_retries:
                logger.warning("%s failed after %d attempts: %s", label, attempt, exc)
                raise
            delay = backoff_seconds * (2 ** (attempt - 1))
            logger.info("%s failed (attempt %d), retrying in %.1fs: %s", label, attempt, delay, exc)
            sleep(delay)
