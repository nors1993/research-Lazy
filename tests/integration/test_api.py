"""Integration tests for API endpoints."""

import pytest
from datetime import datetime
from uuid import uuid4


class TestSchemas:
    """Tests for API schemas."""

    def test_create_task_request_valid(self):
        """Test valid request creation."""
        from src.api.schemas import CreateTaskRequest, Domain, DocType

        request = CreateTaskRequest(
            topic="Test research topic",
            docType="PAPER",
            domain="CS",
        )

        assert request.topic == "Test research topic"
        assert request.doc_type == DocType.PAPER
        assert request.domain == Domain.CS

    def test_create_task_request_validation(self):
        """Test request validation - missing required fields."""
        from pydantic import ValidationError as PydanticValidationError
        from src.api.schemas import CreateTaskRequest

        with pytest.raises(Exception):  # Pydantic validation error
            CreateTaskRequest()

    def test_doc_type_enum(self):
        """Test document type enum values."""
        from src.api.schemas import DocType

        assert DocType.PAPER.value == "PAPER"
        assert DocType.PATENT.value == "PATENT"
        assert DocType.ABSTRACT.value == "ABSTRACT"
        assert DocType.SURVEY.value == "SURVEY"
        assert DocType.PROPOSAL.value == "PROPOSAL"
        assert DocType.THESIS.value == "THESIS"

    def test_domain_enum(self):
        """Test domain enum values."""
        from src.api.schemas import Domain

        assert Domain.CS.value == "CS"
        assert Domain.RS.value == "RS"
        assert Domain.GEO.value == "GEO"

    def test_task_status_enum(self):
        """Test task status enum values."""
        from src.api.schemas import TaskStatus

        assert TaskStatus.PENDING.value == "PENDING"
        assert TaskStatus.RUNNING.value == "RUNNING"
        assert TaskStatus.PAUSED.value == "PAUSED"
        assert TaskStatus.COMPLETED.value == "COMPLETED"
        assert TaskStatus.FAILED.value == "FAILED"
        assert TaskStatus.CANCELLED.value == "CANCELLED"

    def test_task_status_response_model(self):
        """Test response model structure."""
        from src.api.schemas import TaskStatusResponse, TaskStatus

        task_id = uuid4()
        response = TaskStatusResponse(
            task_id=task_id,
            status=TaskStatus.PENDING,
            progress=0,
            created_at=datetime.now(),
        )

        assert response.task_id == task_id
        assert response.status == TaskStatus.PENDING
        assert response.progress == 0


class TestWorkflowStateMachine:
    """Tests for workflow state machine."""

    def test_workflow_states(self):
        """Test workflow state definitions."""
        from src.workflow.state_machine import WorkflowState

        # Verify all states exist
        states = [
            WorkflowState.INITIALIZED,
            WorkflowState.RUNNING,
            WorkflowState.PAUSED,
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        ]

        for state in states:
            assert state is not None
            assert isinstance(state.value, str)

    def test_node_status(self):
        """Test node status enum."""
        from src.workflow.state_machine import NodeStatus

        assert NodeStatus.PENDING.value == "PENDING"
        assert NodeStatus.RUNNING.value == "RUNNING"
        assert NodeStatus.COMPLETED.value == "COMPLETED"
        assert NodeStatus.FAILED.value == "FAILED"
        assert NodeStatus.SKIPPED.value == "SKIPPED"

    def test_state_transitions(self):
        """Test state transition validation."""
        from src.workflow.state_machine import StateMachine, WorkflowState

        sm = StateMachine()

        # Can transition from INITIALIZED to RUNNING
        assert sm.can_transition(WorkflowState.INITIALIZED, WorkflowState.RUNNING)
        # Can transition from INITIALIZED to CANCELLED
        assert sm.can_transition(WorkflowState.INITIALIZED, WorkflowState.CANCELLED)
        # Cannot transition from COMPLETED to anything
        assert not sm.can_transition(WorkflowState.COMPLETED, WorkflowState.RUNNING)


class TestSharedContext:
    """Tests for shared context."""

    def test_workflow_context_creation(self):
        """Test workflow context creation."""
        from src.workflow.state_machine import WorkflowContext, WorkflowState

        context = WorkflowContext(
            task_id="test-001",
            topic="Test topic",
            domain="CS",
            doc_type="PAPER",
        )

        assert context.task_id == "test-001"
        assert context.topic == "Test topic"
        assert context.state == WorkflowState.INITIALIZED

    def test_context_shared_data(self):
        """Test context shared data storage."""
        from src.workflow.state_machine import WorkflowContext

        context = WorkflowContext(
            task_id="test-001",
            topic="Test",
            domain="CS",
            doc_type="PAPER",
        )

        context.shared_data["key1"] = "value1"
        assert context.shared_data["key1"] == "value1"


class TestRetryMechanism:
    """Tests for retry mechanism."""

    @pytest.mark.asyncio
    async def test_retry_success(self):
        """Test successful retry."""
        from src.workflow.retry import retry_with_backoff

        async def success_func():
            return "success"

        result = await retry_with_backoff(success_func)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_failure(self):
        """Test retry with failures."""
        from src.workflow.retry import retry_with_backoff, RetryConfig

        async def fail_func():
            raise ValueError("test error")

        config = RetryConfig(max_attempts=2)

        with pytest.raises(ValueError):
            await retry_with_backoff(fail_func, config)

    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test retry succeeds after some failures."""
        from src.workflow.retry import retry_with_backoff, RetryConfig

        call_count = 0

        async def succeed_after_1():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("temp error")
            return "success"

        config = RetryConfig(max_attempts=3)
        result = await retry_with_backoff(succeed_after_1, config)

        assert result == "success"
        assert call_count == 2


class TestTemplateLoader:
    """Tests for template loader."""

    def test_template_loader_init(self):
        """Test template loader initialization."""
        from src.utils.template import TemplateLoader

        loader = TemplateLoader("templates")

        assert loader.template_dir.name == "templates"

    def test_supported_extensions(self):
        """Test supported file extensions."""
        from src.utils.template import TemplateLoader

        loader = TemplateLoader()
        expected = {".md", ".txt", ".html", ".tex"}

        assert loader.SUPPORTED_EXTENSIONS == expected


class TestCleanupManager:
    """Tests for cleanup manager."""

    def test_cleanup_manager_init(self):
        """Test cleanup manager initialization."""
        from src.utils.cleanup import CleanupManager

        manager = CleanupManager("workspace/temp")

        assert manager.workspace_path.name == "temp"

    def test_cleanup_patterns(self):
        """Test cleanup file patterns."""
        from src.utils.cleanup import CleanupManager

        manager = CleanupManager()

        expected = ["*.py", "*.mjs", "*.js", "*.ts"]
        assert manager.CLEANUP_PATTERNS == expected