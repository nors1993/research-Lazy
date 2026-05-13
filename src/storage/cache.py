"""Redis cache client for caching and session management."""

import json
from typing import Any

import redis.asyncio as redis

from ..config import settings
from ..utils.logger import get_logger

logger = get_logger(__name__)


class RedisClient:
    """Async Redis client for caching and state management."""

    def __init__(self, url: str | None = None):
        self.url = url or settings.redis_url
        self._client: redis.Redis | None = None

    async def connect(self) -> None:
        """Connect to Redis."""
        if self._client is not None:
            return
        try:
            self._client = redis.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
            )
            self._client.ping()
            logger.info("redis_connected", url=self.url)
        except Exception as e:
            logger.warning("redis_connection_failed", url=self.url, error=str(e))
            self._client = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("redis_disconnected")

    async def get(self, key: str) -> str | None:
        """Get a value by key."""
        if not self._client:
            await self.connect()
        return await self._client.get(key)

    async def set(
        self,
        key: str,
        value: Any,
        expire_seconds: int | None = None,
    ) -> bool:
        """Set a value with optional expiration."""
        if not self._client:
            await self.connect()

        if isinstance(value, (dict, list)):
            value = json.dumps(value)

        if expire_seconds:
            return await self._client.setex(key, expire_seconds, value)
        return await self._client.set(key, value)

    async def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not self._client:
            await self.connect()
        return await self._client.delete(*keys)

    async def exists(self, key: str) -> bool:
        """Check if a key exists."""
        if not self._client:
            await self.connect()
        return await self._client.exists(key) > 0

    async def expire(self, key: str, seconds: int) -> bool:
        """Set expiration on a key."""
        if not self._client:
            await self.connect()
        return await self._client.expire(key, seconds)

    async def ttl(self, key: str) -> int:
        """Get time to live for a key."""
        if not self._client:
            await self.connect()
        return await self._client.ttl(key)

    # Specialized methods for task management

    async def set_task_state(
        self,
        task_id: str,
        state: dict,
        expire_seconds: int = 3600,
    ) -> bool:
        """Store task state."""
        return await self.set(f"task:{task_id}:state", state, expire_seconds)

    async def get_task_state(self, task_id: str) -> dict | None:
        """Get task state."""
        value = await self.get(f"task:{task_id}:state")
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return None
        return None

    async def delete_task_state(self, task_id: str) -> int:
        """Delete task state."""
        return await self.delete(f"task:{task_id}:state")

    async def set_sse_client(
        self,
        task_id: str,
        client_id: str,
    ) -> bool:
        """Register an SSE client for a task."""
        return await self.set(
            f"sse:{task_id}:clients",
            {"client_id": client_id},
            expire_seconds=3600,
        )

    async def publish_event(self, channel: str, event: dict) -> int:
        """Publish an event to a channel. Falls back to memory on Redis failure."""
        # 先保存到内存（作为备份和降级方案）
        try:
            from ..api.event_storage import publish_step_event
            task_id_str = channel.replace("task_events:", "")
            # 从event中提取node和message
            node = event.get("data", {}).get("node", "") if event.get("data") else ""
            message = event.get("message", "")
            # 尝试转换为UUID，如果失败则跳过内存存储
            try:
                import uuid
                task_uuid = uuid.UUID(task_id_str)
                publish_step_event(task_uuid, event.get("event", ""), node, message)
            except (ValueError, AttributeError):
                pass  # 无效的UUID格式则跳过
        except Exception:
            pass  # 内存存储失败则静默跳过

        # 然后尝试Redis发布
        if not self._client:
            try:
                await self.connect()
            except Exception:
                return 0  # Redis连接失败，内存已备份

        try:
            return await self._client.publish(channel, json.dumps(event))
        except Exception:
            return 0  # Redis发布失败，但内存已备份


# Global client instance
redis_client = RedisClient()
