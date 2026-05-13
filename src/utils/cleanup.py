"""Workspace cleanup utility."""

from pathlib import Path

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CleanupManager:
    """Manages workspace cleanup operations."""

    # File patterns to cleanup (per PRD requirements)
    CLEANUP_PATTERNS = ["*.py", "*.mjs", "*.js", "*.ts"]

    def __init__(self, workspace_path: str = "workspace/temp"):
        self.workspace_path = Path(workspace_path)

    def cleanup_task(self, task_id: str) -> int:
        """Clean up temporary files for a specific task."""
        task_dir = self.workspace_path / task_id

        if not task_dir.exists():
            logger.warning("task_workspace_not_found", task_id=task_id)
            return 0

        deleted_count = 0

        for pattern in self.CLEANUP_PATTERNS:
            for file_path in task_dir.rglob(pattern):
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.debug("file_deleted", path=str(file_path))
                except OSError as e:
                    logger.warning("file_deletion_failed", path=str(file_path), error=str(e))

        logger.info(
            "task_cleanup_complete",
            task_id=task_id,
            deleted_count=deleted_count,
        )

        return deleted_count

    def cleanup_all_tasks(self) -> int:
        """Clean up all task workspaces."""
        if not self.workspace_path.exists():
            return 0

        total_deleted = 0

        for task_dir in self.workspace_path.iterdir():
            if task_dir.is_dir():
                task_id = task_dir.name
                count = self.cleanup_task(task_id)
                total_deleted += count

        logger.info("full_cleanup_complete", total_deleted=total_deleted)
        return total_deleted

    def get_workspace_size(self, task_id: str) -> int:
        """Get total size of task workspace in bytes."""
        task_dir = self.workspace_path / task_id

        if not task_dir.exists():
            return 0

        total_size = 0
        for file_path in task_dir.rglob("*"):
            if file_path.is_file():
                total_size += file_path.stat().st_size

        return total_size

    def list_temp_files(self, task_id: str) -> list[str]:
        """List temporary files in task workspace."""
        task_dir = self.workspace_path / task_id

        if not task_dir.exists():
            return []

        temp_files = []
        for pattern in self.CLEANUP_PATTERNS:
            for file_path in task_dir.rglob(pattern):
                temp_files.append(str(file_path.relative_to(task_dir)))

        return temp_files


# Global cleanup manager
cleanup_manager = CleanupManager()
