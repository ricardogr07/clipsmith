"""Tenacity retry builder for LLM provider calls."""

from __future__ import annotations

import logging
from typing import Any

from ..config.models import RetryConfig

log = logging.getLogger(__name__)

__all__ = ["RetryConfig", "build_retry"]


def build_retry(
    cfg: RetryConfig,
    *,
    candidate_id: str,
    provider: str,
) -> Any:
    """Return a configured tenacity Retrying context manager.

    Usage:
        retry = build_retry(cfg, candidate_id="123.4", provider="anthropic")
        for attempt in retry:
            with attempt:
                result = api_call()
    """
    import tenacity

    try:
        import anthropic as _anthropic

        _anthropic_errors: tuple = (
            _anthropic.RateLimitError,
            _anthropic.APIConnectionError,
        )
    except ImportError:
        _anthropic_errors = ()

    try:
        import openai as _openai

        _openai_errors: tuple = (
            _openai.RateLimitError,
            _openai.APIConnectionError,
        )
    except ImportError:
        _openai_errors = ()

    try:
        import httpx

        _httpx_errors: tuple = (httpx.TimeoutException, httpx.ConnectError)
    except ImportError:
        _httpx_errors = ()

    retried = _anthropic_errors + _openai_errors + _httpx_errors

    def _before_sleep(retry_state: tenacity.RetryCallState) -> None:
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        wait = getattr(retry_state.next_action, "sleep", 0.0)
        log.warning(
            "llm_retry — provider=%s candidate=%s attempt=%d wait_s=%.2f error=%s",
            provider,
            candidate_id,
            retry_state.attempt_number,
            wait,
            exc,
        )

    wait_strategy: Any = tenacity.wait_exponential(
        multiplier=cfg.multiplier,
        min=cfg.wait_min_s,
        max=cfg.wait_max_s,
    )
    if cfg.jitter:
        wait_strategy = tenacity.wait_combine(wait_strategy, tenacity.wait_random(0, 1))

    return tenacity.Retrying(
        retry=tenacity.retry_if_exception_type(retried) if retried else tenacity.retry_never,
        stop=tenacity.stop_after_attempt(cfg.max_attempts),
        wait=wait_strategy,
        before_sleep=_before_sleep,
        reraise=True,
    )
