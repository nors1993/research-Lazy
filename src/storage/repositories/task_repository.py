"""Database repositories for data access."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Checkpoint, ResearchTask, ReviewResult, ReviewStatus, TaskStatus


class TaskRepository:
    """Repository for ResearchTask operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        topic: str,
        domain: str,
        doc_type: str,
        requirements: str | None = None,
        template_path: str | None = None,
    ) -> ResearchTask:
        """Create a new research task."""
        task = ResearchTask(
            topic=topic,
            domain=domain,
            doc_type=doc_type,
            requirements=requirements,
            template_path=template_path,
            status=TaskStatus.PENDING,
            created_at=datetime.now(UTC),
        )
        self.session.add(task)
        await self.session.commit()
        await self.session.refresh(task)
        return task

    async def get_by_id(self, task_id: uuid.UUID) -> ResearchTask | None:
        """Get task by ID."""
        result = await self.session.execute(
            select(ResearchTask).where(ResearchTask.id == task_id)
        )
        return result.scalar_one_or_none()

    async def get_by_status(self, status: TaskStatus) -> list[ResearchTask]:
        """Get all tasks with a specific status."""
        result = await self.session.execute(
            select(ResearchTask).where(ResearchTask.status == status)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        task_id: uuid.UUID,
        status: TaskStatus,
        current_node: str | None = None,
        progress: int | None = None,
    ) -> bool:
        """Update task status."""
        values = {
            "status": status,
            "updated_at": datetime.now(UTC),
        }
        if current_node is not None:
            values["current_node"] = current_node
        if progress is not None:
            values["progress"] = progress
        if status == TaskStatus.RUNNING:
            values["started_at"] = datetime.now(UTC)
        if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            values["completed_at"] = datetime.now(UTC)

        result = await self.session.execute(
            update(ResearchTask).where(ResearchTask.id == task_id).values(**values)
        )
        await self.session.commit()
        return result.rowcount > 0

    async def set_error(self, task_id: uuid.UUID, error_message: str) -> bool:
        """Set task error."""
        result = await self.session.execute(
            update(ResearchTask)
            .where(ResearchTask.id == task_id)
            .values(
                status=TaskStatus.FAILED,
                error_message=error_message,
                updated_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def set_output_path(self, task_id: uuid.UUID, output_path: str) -> bool:
        """Set task output path."""
        result = await self.session.execute(
            update(ResearchTask)
            .where(ResearchTask.id == task_id)
            .values(
                output_path=output_path,
                updated_at=datetime.now(UTC),
            )
        )
        await self.session.commit()
        return result.rowcount > 0

    async def list_recent(self, limit: int = 100) -> list[ResearchTask]:
        """List recent tasks."""
        result = await self.session.execute(
            select(ResearchTask)
            .order_by(ResearchTask.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class CheckpointRepository:
    """Repository for Checkpoint operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: uuid.UUID,
        node_name: str,
        context_snapshot: dict,
        expires_hours: int = 24,
    ) -> Checkpoint:
        """Create a checkpoint."""
        from datetime import timedelta

        checkpoint = Checkpoint(
            task_id=task_id,
            node_name=node_name,
            context_snapshot=context_snapshot,
            resume_token=f"resume-{uuid.uuid4().hex[:12]}",
            created_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=expires_hours),
        )
        self.session.add(checkpoint)
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint

    async def get_by_task_id(self, task_id: uuid.UUID) -> Checkpoint | None:
        """Get checkpoint by task ID."""
        result = await self.session.execute(
            select(Checkpoint)
            .where(Checkpoint.task_id == task_id)
            .order_by(Checkpoint.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_token(self, resume_token: str) -> Checkpoint | None:
        """Get checkpoint by resume token."""
        result = await self.session.execute(
            select(Checkpoint).where(Checkpoint.resume_token == resume_token)
        )
        return result.scalar_one_or_none()

    async def delete_by_task_id(self, task_id: uuid.UUID) -> int:
        """Delete checkpoint by task ID."""
        result = await self.session.execute(
            delete(Checkpoint).where(Checkpoint.task_id == task_id)
        )
        await self.session.commit()
        return result.rowcount


class ReviewResultRepository:
    """Repository for ReviewResult operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        task_id: uuid.UUID,
        version: int,
        status: ReviewStatus,
        logic_validation: dict,
        plagiarism_check: dict,
        innovation_validation: dict | None = None,
        recommendations: list | None = None,
        overall_assessment: str | None = None,
    ) -> ReviewResult:
        """Create a review result."""
        result = ReviewResult(
            task_id=task_id,
            version=version,
            status=status,
            logic_validation=logic_validation,
            plagiarism_check=plagiarism_check,
            innovation_validation=innovation_validation or {},
            recommendations=recommendations or [],
            overall_assessment=overall_assessment,
            created_at=datetime.now(UTC),
        )
        self.session.add(result)
        await self.session.commit()
        await self.session.refresh(result)
        return result

    async def get_latest_by_task(self, task_id: uuid.UUID) -> ReviewResult | None:
        """Get latest review result for a task."""
        result = await self.session.execute(
            select(ReviewResult)
            .where(ReviewResult.task_id == task_id)
            .order_by(ReviewResult.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_task_and_version(
        self, task_id: uuid.UUID, version: int
    ) -> ReviewResult | None:
        """Get review result by task and version."""
        result = await self.session.execute(
            select(ReviewResult).where(
                ReviewResult.task_id == task_id,
                ReviewResult.version == version,
            )
        )
        return result.scalar_one_or_none()
