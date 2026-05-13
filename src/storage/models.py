"""Database models for the AutoResearch Agent System."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all database models."""

    pass


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentRole(str, enum.Enum):
    """Agent role enumeration."""

    EDITOR = "EDITOR"
    INVESTIGATOR = "INVESTIGATOR"
    WRITER = "WRITER"
    REVIEWER = "REVIEWER"


class ReviewStatus(str, enum.Enum):
    """Review status enumeration."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MAJOR_REVISION = "MAJOR_REVISION"
    MINOR_REVISION = "MINOR_REVISION"


class ResearchTask(Base):
    """Research task model representing a user's research request."""

    __tablename__ = "research_tasks"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Task fields
    topic: Mapped[str] = mapped_column(String(500), nullable=False)
    domain: Mapped[str] = mapped_column(String(10), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(20), nullable=False)
    requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    template_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Status fields
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING
    )
    current_node: Mapped[str | None] = mapped_column(String(50), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Indexes
    __table_args__ = (
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_domain", "domain"),
        Index("ix_tasks_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ResearchTask(id={self.id}, topic='{self.topic}', status={self.status})>"


class Agent(Base):
    """Agent model representing an AI agent instance."""

    __tablename__ = "agents"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Agent fields
    role: Mapped[AgentRole] = mapped_column(Enum(AgentRole), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    model_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    max_tokens: Mapped[int] = mapped_column(Integer, default=4096)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    capabilities: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<Agent(id={self.id}, role={self.role}, name='{self.name}')>"


class WorkflowNode(Base):
    """Workflow node model defining each stage in the workflow."""

    __tablename__ = "workflow_nodes"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Node fields
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Configuration
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60)
    retry_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    soft_restart_config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    next_nodes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_review_node: Mapped[bool] = mapped_column(default=False)
    max_iterations: Mapped[int] = mapped_column(Integer, default=3)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return f"<WorkflowNode(name='{self.name}', timeout={self.timeout_seconds}s)>"


class Checkpoint(Base):
    """Checkpoint model for task recovery."""

    __tablename__ = "checkpoints"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    # Checkpoint fields
    node_name: Mapped[str] = mapped_column(String(50), nullable=False)
    sub_task_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    context_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    resume_token: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Indexes
    __table_args__ = (
        Index("ix_checkpoints_task_id", "task_id"),
        Index("ix_checkpoints_resume_token", "resume_token", unique=True),
    )

    def __repr__(self) -> str:
        return f"<Checkpoint(id={self.id}, task_id={self.task_id}, node='{self.node_name}')>"


class ReviewResult(Base):
    """Review result model from Reviewer agent."""

    __tablename__ = "review_results"

    # Primary key
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Foreign key
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False
    )

    # Review fields
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReviewStatus] = mapped_column(Enum(ReviewStatus), nullable=False)
    overall_assessment: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Validation results
    logic_validation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    plagiarism_check: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    innovation_validation: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    recommendations: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Indexes
    __table_args__ = (
        Index("ix_review_results_task_id", "task_id"),
        Index("ix_review_results_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ReviewResult(id={self.id}, task_id={self.task_id}, status={self.status})>"
