"""Event publisher for workflow events (SSE)."""

import enum
from uuid import UUID

from ..utils.logger import get_logger

logger = get_logger(__name__)


class WorkflowEventType(str, enum.Enum):
    """Types of workflow events."""

    TASK_START = "task_start"
    NODE_START = "node_start"
    NODE_COMPLETE = "node_complete"
    NODE_ERROR = "node_error"
    REVIEW_ITERATION = "review_iteration"
    TASK_COMPLETE = "task_complete"
    TASK_FAILED = "task_failed"
    TASK_CANCELLED = "task_cancelled"


class EventPublisher:
    """Publishes workflow events for SSE."""

    def __init__(self):
        # Lazy import to avoid circular dependency
        self._redis = None

    @property
    def redis(self):
        if self._redis is None:
            from ..storage.cache import redis_client
            self._redis = redis_client
        return self._redis

    async def publish(
        self,
        task_id: UUID | str,
        event_type: WorkflowEventType,
        message: str,
        data: dict | None = None,
    ) -> None:
        """Publish an event for a task."""
        event = {
            "event": event_type.value,
            "message": message,
            "data": data or {},
        }

        try:
            # Publish to Redis channel (with fallback to memory)
            channel = f"task_events:{task_id}"
            await self.redis.publish_event(channel, event)
        except Exception as e:
            logger.warning("event_publish_failed", error=str(e))
            # Fallback already handled in redis.publish_event

        logger.info(
            "event_published",
            task_id=str(task_id),
            event_type=event_type.value,
            message=message,
        )

    async def publish_task_start(self, task_id: UUID | str, topic: str) -> None:
        """Publish task start event."""
        await self.publish(
            task_id,
            WorkflowEventType.TASK_START,
            f"Task started for topic: {topic}",
        )

    async def publish_node_start(
        self, task_id: UUID | str, node: str, message: str
    ) -> None:
        """Publish node start event."""
        await self.publish(
            task_id,
            WorkflowEventType.NODE_START,
            message,
            {"node": node},
        )

    async def publish_node_complete(
        self,
        task_id: UUID | str,
        node: str,
        message: str,
        duration_ms: int | None = None,
    ) -> None:
        """Publish node complete event."""
        await self.publish(
            task_id,
            WorkflowEventType.NODE_COMPLETE,
            message,
            {"node": node, "duration_ms": duration_ms},
        )

    async def publish_node_error(
        self, task_id: UUID | str, node: str, error: str
    ) -> None:
        """Publish node error event."""
        await self.publish(
            task_id,
            WorkflowEventType.NODE_ERROR,
            f"Error in {node}: {error}",
            {"node": node, "error": error},
        )

    async def publish_task_complete(
        self, task_id: UUID | str, output_path: str
    ) -> None:
        """Publish task complete event."""
        await self.publish(
            task_id,
            WorkflowEventType.TASK_COMPLETE,
            f"Task completed. Output: {output_path}",
            {"output_path": output_path},
        )

    async def publish_task_failed(
        self, task_id: UUID | str, reason: str
    ) -> None:
        """Publish task failed event."""
        await self.publish(
            task_id,
            WorkflowEventType.TASK_FAILED,
            f"Task failed: {reason}",
            {"reason": reason},
        )

    async def publish_review_iteration(
        self,
        task_id: UUID | str,
        version: int,
        status: str,
    ) -> None:
        """Publish review iteration event."""
        await self.publish(
            task_id,
            WorkflowEventType.REVIEW_ITERATION,
            f"Review iteration {version}: {status}",
            {"version": version, "status": status},
        )


# Global event publisher
event_publisher = EventPublisher()
