"""Base exception classes for the application."""


class AutoResearchException(Exception):
    """Base exception for all application errors."""

    def __init__(self, message: str, code: str = "ERR_GENERIC"):
        self.message = message
        self.code = code
        super().__init__(self.message)

    def to_dict(self) -> dict[str, dict[str, str]]:
        """Convert exception to error response format."""
        return {
            "error": {
                "code": self.code,
                "message": self.message,
            }
        }


# LLM Related Exceptions
class LLMException(AutoResearchException):
    """Base exception for LLM-related errors."""

    def __init__(self, message: str, code: str = "ERR_LLM"):
        super().__init__(message, code)


class LLMAPIKeyError(LLMException):
    """Raised when LLM API key is invalid or missing."""

    def __init__(self, provider: str):
        super().__init__(f"{provider} API key is invalid or missing", "ERR_LLM_001")


class LLMAPIExhaustedError(LLMException):
    """Raised when LLM API quota is exhausted."""

    def __init__(self, provider: str):
        super().__init__(f"{provider} API quota has been exhausted", "ERR_LLM_002")


class LLMResponseError(LLMException):
    """Raised when LLM returns an unexpected response."""

    def __init__(self, message: str):
        super().__init__(message, "ERR_LLM_003")


# Network Related Exceptions
class NetworkException(AutoResearchException):
    """Base exception for network-related errors."""

    def __init__(self, message: str, code: str = "ERR_NET"):
        super().__init__(message, code)


class NetworkUnreachableError(NetworkException):
    """Raised when a network service is unreachable."""

    def __init__(self, service: str):
        super().__init__(f"Network service unreachable: {service}", "ERR_NET_001")


class NetworkTimeoutError(NetworkException):
    """Raised when a network request times out."""

    def __init__(self, operation: str):
        super().__init__(f"Network request timeout: {operation}", "ERR_NET_002")


# Task Related Exceptions
class TaskException(AutoResearchException):
    """Base exception for task-related errors."""

    def __init__(self, message: str, code: str = "ERR_TASK"):
        super().__init__(message, code)


class TaskNotFoundError(TaskException):
    """Raised when a task is not found."""

    def __init__(self, task_id: str):
        super().__init__(f"Task not found: {task_id}", "ERR_TASK_001")


class TaskTimeoutError(TaskException):
    """Raised when a task exceeds its timeout."""

    def __init__(self, task_id: str, node: str):
        super().__init__(
            f"Task {task_id} timed out at node {node}",
            "ERR_TASK_001",
        )


class TaskExecutionError(TaskException):
    """Raised when task execution fails."""

    def __init__(self, task_id: str, reason: str):
        super().__init__(f"Task {task_id} execution failed: {reason}", "ERR_TASK_002")


# Validation Exceptions
class ValidationException(AutoResearchException):
    """Base exception for validation errors."""

    def __init__(self, message: str, code: str = "ERR_VALIDATE"):
        super().__init__(message, code)


class LogicValidationError(ValidationException):
    """Raised when logic validation fails."""

    def __init__(self, message: str):
        super().__init__(message, "ERR_VALIDATE_001")


class PlagiarismThresholdError(ValidationException):
    """Raised when plagiarism check exceeds threshold."""

    def __init__(self, similarity_rate: float):
        super().__init__(
            f"Plagiarism similarity rate {similarity_rate}% exceeds threshold of 15%",
            "ERR_VALIDATE_002",
        )


# Storage Exceptions
class StorageException(AutoResearchException):
    """Base exception for storage-related errors."""

    def __init__(self, message: str, code: str = "ERR_STORAGE"):
        super().__init__(message, code)


class DatabaseError(StorageException):
    """Raised when database operation fails."""

    def __init__(self, operation: str):
        super().__init__(f"Database operation failed: {operation}", "ERR_STORAGE_001")


class CacheError(StorageException):
    """Raised when cache operation fails."""

    def __init__(self, operation: str):
        super().__init__(f"Cache operation failed: {operation}", "ERR_STORAGE_002")


# Workflow Exceptions
class WorkflowException(AutoResearchException):
    """Base exception for workflow-related errors."""

    def __init__(self, message: str, code: str = "ERR_WORKFLOW"):
        super().__init__(message, code)


class InvalidStateTransitionError(WorkflowException):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current_state: str, attempted_state: str):
        super().__init__(
            f"Invalid state transition from {current_state} to {attempted_state}",
            "ERR_WORKFLOW_001",
        )


class NodeExecutionError(WorkflowException):
    """Raised when a workflow node fails to execute."""

    def __init__(self, node: str, reason: str):
        super().__init__(f"Workflow node {node} failed: {reason}", "ERR_WORKFLOW_002")
