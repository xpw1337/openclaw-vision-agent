"""Retry policy helpers for worker-side image analysis failures."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from core.vision import ContentBlockedError

_RETRYABLE_NAMES = {
    "DeadlineExceeded",
    "InternalServerError",
    "ResourceExhausted",
    "ServiceUnavailable",
    "TooManyRequests",
}
_TERMINAL_NAMES = {
    "ValidationError",
    "ValueError",
}


@dataclass(frozen=True)
class RetryDecision:
    retryable: bool
    terminal: bool
    reason: str


def classify_exception(exc: BaseException) -> RetryDecision:
    """Classify an exception without binding to one provider SDK version."""
    name = type(exc).__name__
    text = str(exc).lower()
    if isinstance(exc, ContentBlockedError) or name in _TERMINAL_NAMES:
        return RetryDecision(retryable=False, terminal=True, reason=f"{name}: {exc}")
    if isinstance(exc, (TimeoutError, asyncio.TimeoutError, ConnectionError)):
        return RetryDecision(retryable=True, terminal=False, reason=f"{name}: {exc}")
    if name in _RETRYABLE_NAMES or "rate limit" in text or "429" in text:
        return RetryDecision(retryable=True, terminal=False, reason=f"{name}: {exc}")
    return RetryDecision(retryable=False, terminal=False, reason=f"{name}: {exc}")


def backoff_delay(attempt: int, *, base: float, maximum: float) -> float:
    """Exponential backoff in seconds for a 1-based attempt number."""
    delay = base * (2 ** max(0, attempt - 1))
    return min(delay, maximum)
