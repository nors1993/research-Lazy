"""API request and response schemas."""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """Task status enumeration."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class Domain(str, Enum):
    """Supported academic domains."""

    CS = "CS"
    GEO = "GEO"
    RS = "RS"
    GEOL = "GEOL"
    PHYS = "PHYS"
    MATH = "MATH"
    CHEM = "CHEM"
    BIO = "BIO"
    MED = "MED"
    ECON = "ECON"


class DocType(str, Enum):
    """Supported document types."""

    PAPER = "PAPER"
    PATENT = "PATENT"
    ABSTRACT = "ABSTRACT"
    SURVEY = "SURVEY"
    PROPOSAL = "PROPOSAL"
    THESIS = "THESIS"


# Request Schemas


class CreateTaskRequest(BaseModel):
    """Request schema for creating a research task."""

    topic: str = Field(..., min_length=1, max_length=5000, description="Research topic")
    domain: Domain = Field(..., description="Academic domain")
    doc_type: DocType = Field(..., alias="docType", description="Document type")
    requirements: str | None = Field(None, description="Special requirements")
    template_path: str | None = Field(
        None, max_length=500, alias="templatePath", description="Custom template path"
    )
    template_content: str | None = Field(
        None, description="Template content as markdown text"
    )
    temp_prompt: str | None = Field(
        None, alias="tempPrompt", description="Temporary prompt for this task (will be destroyed after completion)"
    )
    attachment_content: str | None = Field(
        None, alias="attachmentContent", description="Attachment content parsed from uploaded file (will be destroyed after completion)"
    )

    model_config = {"populate_by_name": True}


class ResumeTaskRequest(BaseModel):
    """Request schema for resuming a paused task."""

    resume_token: str = Field(..., alias="resumeToken", description="Resume token")


# Response Schemas


class CreateTaskResponse(BaseModel):
    """Response schema for created task."""

    task_id: UUID = Field(..., alias="taskId")
    status: TaskStatus
    message: str


class TaskStatusResponse(BaseModel):
    """Response schema for task status."""

    task_id: UUID = Field(..., alias="taskId")
    status: TaskStatus
    current_node: str | None = Field(None, alias="currentNode")
    progress: int = Field(ge=0, le=100)
    created_at: datetime = Field(..., alias="createdAt")
    started_at: datetime | None = Field(None, alias="startedAt")
    updated_at: datetime | None = Field(None, alias="updatedAt")
    completed_at: datetime | None = Field(None, alias="completedAt")
    output_path: str | None = Field(None, alias="outputPath")
    error_message: str | None = Field(None, alias="errorMessage")
    node_detail: str | None = Field(None, alias="nodeDetail")

    model_config = {"populate_by_name": True}


class TaskStatusCompletedResponse(TaskStatusResponse):
    """Extended response for completed tasks."""

    output_path: str | None = Field(None, alias="outputPath")


class TaskStatusFailedResponse(TaskStatusResponse):
    """Extended response for failed tasks."""

    error_message: str | None = Field(None, alias="errorMessage")


class PauseTaskResponse(BaseModel):
    """Response schema for paused task."""

    task_id: UUID = Field(..., alias="taskId")
    status: TaskStatus
    checkpoint_id: str | None = Field(None, alias="checkpointId")
    resume_token: str = Field(..., alias="resumeToken")
    message: str


class ResumeTaskResponse(BaseModel):
    """Response schema for resumed task."""

    task_id: UUID = Field(..., alias="taskId")
    status: TaskStatus
    current_node: str | None = Field(None, alias="currentNode")
    message: str


class CancelTaskResponse(BaseModel):
    """Response schema for cancelled task."""

    task_id: UUID = Field(..., alias="taskId")
    status: TaskStatus
    message: str


class ErrorResponse(BaseModel):
    """Response schema for errors."""

    error: dict[str, Any] = Field(..., description="Error details")


# SSE Event Schema


class SSEEvent(BaseModel):
    """Server-Sent Events event."""

    event: str = Field(..., description="Event type")
    node: str | None = Field(None, description="Workflow node")
    message: str = Field(..., description="Event message")
    data: dict[str, Any] | None = Field(None, description="Additional event data")


class ModelSettingsRequest(BaseModel):
    base_url: str = Field(default="", description="API base URL")
    api_key: str = Field(default="", description="API key")
    model: str = Field(default="", description="Model name")


class WorkspaceSettingsRequest(BaseModel):
    output_path: str = Field(default="", description="Output directory path")
    temp_path: str = Field(default="", description="Temp directory path")
