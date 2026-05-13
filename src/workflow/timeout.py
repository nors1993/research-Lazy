"""Timeout handling with soft restart strategies."""

import asyncio
import builtins
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SoftRestartStrategy(str, Enum):
    """Strategies for soft restart on timeout."""

    REFINE_PROMPT = "refine_prompt"
    MODEL_DOWNGRADE = "model_downgrade"
    SPLIT_TASK = "split_task"


@dataclass
class TimeoutConfig:
    """Configuration for timeout handling."""

    soft_restart_timeout: float = 60.0  # Trigger soft restart at this threshold
    hard_stop_timeout: float = 120.0  # Force stop after this
    max_soft_restarts: int = 2


class TimeoutHandler:
    """Handles timeouts with soft restart strategies."""

    def __init__(self, config: TimeoutConfig | None = None):
        self.config = config or TimeoutConfig()

    async def execute_with_timeout(
        self,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute function with timeout and soft restart support."""
        try:
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.hard_stop_timeout,
            )
            return result

        except builtins.TimeoutError:
            logger.warning("timeout_occurred", hard_stop=self.config.hard_stop_timeout)
            raise TimeoutError(f"Operation timed out after {self.config.hard_stop_timeout}s")

    async def execute_with_soft_restart(
        self,
        func: Callable[..., Any],
        strategy: SoftRestartStrategy,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute with soft restart capability."""
        soft_restarts = 0

        while soft_restarts < self.config.max_soft_restarts:
            try:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.soft_restart_timeout,
                )
                return result

            except builtins.TimeoutError:
                logger.warning(
                    "soft_restart_triggered",
                    strategy=strategy.value,
                    attempt=soft_restarts + 1,
                )

                # Apply strategy
                if strategy == SoftRestartStrategy.REFINE_PROMPT:
                    kwargs = await self._refine_prompt(kwargs)
                elif strategy == SoftRestartStrategy.MODEL_DOWNGRADE:
                    kwargs = await self._downgrade_model(kwargs)
                elif strategy == SoftRestartStrategy.SPLIT_TASK:
                    return await self._split_task(func, args, kwargs)

                soft_restarts += 1

        # All soft restarts failed
        logger.error("soft_restart_exhausted", attempts=soft_restarts)
        raise TimeoutError("Soft restart attempts exhausted")

    async def _refine_prompt(self, kwargs: dict) -> dict:
        """Refine prompt to be simpler."""
        if "prompt" in kwargs:
            original = kwargs["prompt"]
            # Simplify by reducing constraints
            simplified = original[: len(original) // 2] if len(original) > 200 else original
            kwargs["prompt"] = simplified
            logger.info("prompt_refined", original_length=len(original), new_length=len(simplified))
        return kwargs

    async def _downgrade_model(self, kwargs: dict) -> dict:
        """Downgrade model for faster execution."""
        if "model" in kwargs:
            # gpt-4o -> gpt-4o-mini
            model = kwargs["model"]
            if "gpt-4o" in model:
                kwargs["model"] = model.replace("gpt-4o", "gpt-4o-mini")
            elif "claude-3-5" in model:
                kwargs["model"] = model.replace("claude-3-5", "claude-3-haiku")
            logger.info("model_downgraded", from_model=model, to_model=kwargs["model"])
        return kwargs

    async def _split_task(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        """Split large task into smaller parts."""
        # This is a placeholder - actual implementation would split the task
        logger.info("task_split_attempted")
        raise TimeoutError("Task too large to split")


class TimeoutError(Exception):
    """Custom timeout error."""

    pass
