"""Checkpoint management for task recovery."""

import uuid
from datetime import UTC, datetime, timedelta

from ..storage.cache import redis_client
from ..utils.logger import get_logger

logger = get_logger(__name__)


class CheckpointManager:
    """Manages task checkpoints for pause/resume functionality."""

    def __init__(self, expiration_hours: int = 24):
        self.expiration_hours = expiration_hours

    async def create_checkpoint(
        self,
        task_id: str,
        node_name: str,
        context_snapshot: dict,
    ) -> dict[str, str]:
        """Create a checkpoint for a task."""
        checkpoint_id = f"chkp-{uuid.uuid4().hex[:8]}"
        resume_token = f"resume-{uuid.uuid4().hex[:12]}"

        checkpoint_data = {
            "checkpoint_id": checkpoint_id,
            "resume_token": resume_token,
            "task_id": task_id,
            "node_name": node_name,
            "context_snapshot": context_snapshot,
            "created_at": datetime.now(UTC).isoformat(),
            "expires_at": (
                datetime.now(UTC) + timedelta(hours=self.expiration_hours)
            ).isoformat(),
        }

        # Store in Redis
        await redis_client.set(
            f"checkpoint:{task_id}",
            checkpoint_data,
            expire_seconds=self.expiration_hours * 3600,
        )

        logger.info(
            "checkpoint_created",
            task_id=task_id,
            checkpoint_id=checkpoint_id,
            resume_token=resume_token,
        )

        return {
            "checkpoint_id": checkpoint_id,
            "resume_token": resume_token,
        }

    async def get_checkpoint(self, task_id: str) -> dict | None:
        """Get checkpoint for a task from Redis."""
        raw = await redis_client.get(f"checkpoint:{task_id}")
        if raw is None:
            return None
        if isinstance(raw, str):
            import json
            return json.loads(raw)
        return raw

    async def get_by_token(self, resume_token: str) -> dict | None:
        """Get checkpoint by resume token."""
        # Search through all checkpoints
        # In production, use a separate index
        return None

    async def delete_checkpoint(self, task_id: str) -> bool:
        """Delete checkpoint for a task from Redis."""
        result = await redis_client.delete(f"checkpoint:{task_id}")
        logger.info("checkpoint_deleted", task_id=task_id)
        return result > 0

    async def is_valid(self, task_id: str) -> bool:
        """Check if checkpoint exists and is valid."""
        checkpoint = await self.get_checkpoint(task_id)
        if not checkpoint:
            return False

        # Check expiration
        expires_at = checkpoint.get("expires_at")
        if expires_at:
            from datetime import datetime

            expiration = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
            if datetime.now(UTC) > expiration:
                logger.warning("checkpoint_expired", task_id=task_id)
                await self.delete_checkpoint(task_id)
                return False

        return True


# Global checkpoint manager
checkpoint_manager = CheckpointManager()
