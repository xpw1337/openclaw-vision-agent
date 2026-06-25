"""Tests for worker retry classification."""

import asyncio

from agent.retry import backoff_delay, classify_exception
from core.vision import ContentBlockedError


def test_content_block_is_terminal():
    decision = classify_exception(ContentBlockedError("SAFETY"))

    assert decision.terminal is True
    assert decision.retryable is False


def test_timeout_is_retryable():
    decision = classify_exception(asyncio.TimeoutError("slow"))

    assert decision.retryable is True
    assert decision.terminal is False


def test_rate_limit_text_is_retryable():
    decision = classify_exception(RuntimeError("429 rate limit exceeded"))

    assert decision.retryable is True


def test_backoff_delay_is_capped():
    assert backoff_delay(1, base=2, maximum=10) == 2
    assert backoff_delay(4, base=2, maximum=10) == 10
