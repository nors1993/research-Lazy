"""Workspace directory management for task files and artifacts."""

import shutil
from pathlib import Path

from ..config import settings
from .logger import get_logger

logger = get_logger(__name__)


class WorkspaceManager:
    """Manages workspace directories for task execution."""

    def __init__(
        self,
        temp_dir: str | None = None,
        output_dir: str | None = None,
    ):
        self.temp_dir = Path(temp_dir or settings.workspace_temp_dir)
        self.output_dir = Path(output_dir or settings.workspace_output_dir)

    def initialize(self) -> None:
        """Initialize workspace directories."""
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(
            "workspace_initialized",
            temp_dir=str(self.temp_dir),
            output_dir=str(self.output_dir),
        )

    def get_task_workspace(self, task_id: str) -> Path:
        """Get the workspace directory for a specific task."""
        return self.temp_dir / task_id

    def get_task_output(self, task_id: str, filename: str) -> Path:
        """Get the output file path for a task."""
        return self.output_dir / task_id / filename

    def create_task_workspace(self, task_id: str) -> Path:
        """Create workspace for a task with subdirectories."""
        workspace = self.get_task_workspace(task_id)

        # Create subdirectories
        subdirs = [
            "investigation_results",
            "writer_drafts",
            "reviewer_feedback",
        ]

        for subdir in subdirs:
            (workspace / subdir).mkdir(parents=True, exist_ok=True)

        logger.info("task_workspace_created", task_id=task_id, path=str(workspace))
        return workspace

    def save_file(self, task_id: str, filename: str, content: str) -> Path:
        """Save content to a file in the task workspace."""
        workspace = self.get_task_workspace(task_id)
        file_path = workspace / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(
            "file_saved",
            task_id=task_id,
            filename=filename,
            path=str(file_path),
        )
        return file_path

    def read_file(self, task_id: str, filename: str) -> str | None:
        """Read content from a file in the task workspace."""
        file_path = self.get_task_workspace(task_id) / filename

        if not file_path.exists():
            logger.warning("file_not_found", task_id=task_id, filename=filename)
            return None

        with open(file_path, encoding="utf-8") as f:
            return f.read()

    def delete_task_workspace(self, task_id: str) -> bool:
        """Delete workspace for a task."""
        workspace = self.get_task_workspace(task_id)

        if workspace.exists():
            shutil.rmtree(workspace)
            logger.info("task_workspace_deleted", task_id=task_id)
            return True

        return False

    def cleanup_temp_files(self, task_id: str) -> int:
        """Clean up temporary code files in task workspace."""
        workspace = self.get_task_workspace(task_id)

        if not workspace.exists():
            return 0

        # Patterns for cleanup (from PRD requirements)
        cleanup_patterns = ["*.py", "*.mjs", "*.js", "*.ts"]

        deleted_count = 0
        for pattern in cleanup_patterns:
            for file_path in workspace.rglob(pattern):
                try:
                    file_path.unlink()
                    deleted_count += 1
                except OSError as e:
                    logger.warning(
                        "file_deletion_failed",
                        path=str(file_path),
                        error=str(e),
                    )

        logger.info(
            "temp_files_cleaned",
            task_id=task_id,
            deleted_count=deleted_count,
        )
        return deleted_count

    def move_to_output(
        self,
        task_id: str,
        filename: str,
        final_filename: str | None = None,
        output_dir_prefix: str | None = None,
    ) -> Path:
        """Move a file from temp workspace to output directory.
        
        Args:
            task_id: Unique task identifier
            filename: Source filename in temp workspace
            final_filename: Optional target filename (defaults to filename)
            output_dir_prefix: Optional prefix for output directory (e.g., 'paper', 'patent')
        """
        source = self.get_task_workspace(task_id) / filename

        # Build output directory name: {prefix}_{task_id} if prefix provided, else just task_id
        if output_dir_prefix:
            dir_name = f"{output_dir_prefix.lower()}_{task_id}"
        else:
            dir_name = task_id

        dest_dir = self.output_dir / dir_name
        dest_dir.mkdir(parents=True, exist_ok=True)

        if final_filename:
            dest = dest_dir / final_filename
        else:
            dest = dest_dir / filename

        shutil.move(str(source), str(dest))

        logger.info(
            "file_moved_to_output",
            task_id=task_id,
            source=str(source),
            dest=str(dest),
        )
        return dest


# Global workspace manager instance
workspace_manager = WorkspaceManager()
