"""Context manager for shared workflow data."""

from typing import Any

from ..utils.logger import get_logger

logger = get_logger(__name__)


class SharedContext:
    """Manages shared context between agents."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._data: dict[str, Any] = {}

    def set(self, key: str, value: Any) -> None:
        """Set a value in the context."""
        self._data[key] = value
        logger.debug("context_set", task_id=self.task_id, key=key)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the context."""
        return self._data.get(key, default)

    def has(self, key: str) -> bool:
        """Check if a key exists."""
        return key in self._data

    def delete(self, key: str) -> None:
        """Delete a value."""
        if key in self._data:
            del self._data[key]
            logger.debug("context_deleted", task_id=self.task_id, key=key)

    def update(self, data: dict[str, Any]) -> None:
        """Update multiple values."""
        self._data.update(data)
        logger.debug("context_updated", task_id=self.task_id, keys=list(data.keys()))

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()
        logger.debug("context_cleared", task_id=self.task_id)

    def to_dict(self) -> dict[str, Any]:
        """Get all data as dict."""
        return self._data.copy()

    # Convenience methods for specific data

    def set_investigation_results(self, feasibility: dict, literature_review: str) -> None:
        """Store investigation results."""
        self.set("feasibility", feasibility)
        self.set("literature_review", literature_review)

    def get_investigation_results(self) -> tuple[dict | None, str | None]:
        """Retrieve investigation results."""
        return self.get("feasibility"), self.get("literature_review")

    def set_draft(self, draft: str, version: int) -> None:
        """Store draft document."""
        self.set("current_draft", draft)
        self.set("draft_version", version)

    def get_draft(self) -> tuple[str | None, int | None]:
        """Retrieve draft document."""
        return self.get("current_draft"), self.get("draft_version")

    def add_review_result(self, result: dict) -> None:
        """Add a review result."""
        reviews = self.get("review_results", [])
        reviews.append(result)
        self.set("review_results", reviews)

    def get_latest_review(self) -> dict | None:
        """Get latest review result."""
        reviews = self.get("review_results", [])
        return reviews[-1] if reviews else None

    def __repr__(self) -> str:
        return f"<SharedContext(task_id={self.task_id}, keys={list(self._data.keys())})>"
