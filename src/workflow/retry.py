"""Retry mechanism with backoff."""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from ..utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        exponential_base: float = 2.0,
        max_delay: float = 60.0,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.exponential_base = exponential_base
        self.max_delay = max_delay


async def retry_with_backoff(
    func: Callable[..., Any],
    config: RetryConfig | None = None,
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute a function with exponential backoff retry."""
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            logger.info("retry_attempt", attempt=attempt + 1, max=config.max_attempts)
            result = await func(*args, **kwargs)
            if attempt > 0:
                logger.info("retry_succeeded", attempt=attempt + 1)
            return result

        except Exception as e:
            last_exception = e
            logger.warning(
                "retry_failed",
                attempt=attempt + 1,
                error=str(e),
            )

            if attempt < config.max_attempts - 1:
                delay = min(
                    config.base_delay * (config.exponential_base**attempt),
                    config.max_delay,
                )
                logger.info("retry_delay", delay_seconds=delay)
                await asyncio.sleep(delay)

    logger.error("retry_exhausted", attempts=config.max_attempts)
    if last_exception is None:
        raise RuntimeError("All retry attempts failed with no exception recorded")
    raise last_exception


class RetryStrategy:
    """Predefined retry strategies for different error types."""

    NETWORK_ERRORS = RetryConfig(max_attempts=3, base_delay=1.0, exponential_base=2.0)
    LLM_ERRORS = RetryConfig(max_attempts=2, base_delay=2.0, exponential_base=2.0)
    VALIDATION_ERRORS = RetryConfig(max_attempts=1, base_delay=0, exponential_base=1.0)
    TIMEOUT_ERRORS = RetryConfig(max_attempts=2, base_delay=1.0, exponential_base=1.5)
