"""Workflow state machine with retry, checkpoint, and cancellation support."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any, Protocol

from ..utils.logger import get_logger
from .checkpoint import CheckpointManager, checkpoint_manager as _default_checkpoint_manager

logger = get_logger(__name__)


class NodeStatus(StrEnum):
    """Status of a workflow node."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class WorkflowState(StrEnum):
    """Overall workflow state."""

    INITIALIZED = "INITIALIZED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class NodeResult:
    """Result from a workflow node."""

    node_name: str
    status: NodeStatus
    output: dict | None = None
    error: str | None = None
    duration_ms: int = 0


@dataclass
class WorkflowContext:
    """Context passed through the workflow."""

    task_id: str
    topic: str
    domain: str
    doc_type: str
    requirements: str | None = None
    template_path: str | None = None
    state: WorkflowState = WorkflowState.INITIALIZED
    current_node: str | None = None
    node_results: dict[str, NodeResult] = field(default_factory=dict)
    shared_data: dict = field(default_factory=dict)
    language: str = "zh-CN"  # Language for document generation, default to Chinese


class WorkflowNode(Protocol):
    """Base class for workflow nodes."""

    name: str
    timeout_seconds: int = 60
    max_retries: int = 1

    async def execute(self, context: WorkflowContext) -> NodeResult:
        """Execute the node."""
        ...

    async def on_timeout(self, context: WorkflowContext) -> NodeResult:
        """Handle timeout."""
        return NodeResult(
            node_name=self.name,
            status=NodeStatus.FAILED,
            error=f"Node {self.name} timed out after {self.timeout_seconds}s",
        )

    async def on_retry(self, context: WorkflowContext, attempt: int) -> NodeResult:
        """Handle retry."""
        return NodeResult(
            node_name=self.name,
            status=NodeStatus.FAILED,
            error=f"Node {self.name} failed after {attempt} attempts",
        )


class StateMachine:
    """Workflow state machine managing node execution."""

    def __init__(self, checkpoint_manager: CheckpointManager | None = None):
        self.nodes: dict[str, WorkflowNode] = {}
        self.edges: dict[str, list[str]] = {}
        self.context: WorkflowContext | None = None
        self.checkpoint_manager = checkpoint_manager or _default_checkpoint_manager
        self._cancelled = False

    def add_node(self, node: WorkflowNode) -> None:
        """Add a node to the state machine."""
        self.nodes[node.name] = node
        logger.info("node_added", node=node.name)

    def add_edge(self, from_node: str, to_node: str) -> None:
        """Add an edge between nodes."""
        if from_node not in self.edges:
            self.edges[from_node] = []
        self.edges[from_node].append(to_node)

    def set_start(self, node_name: str) -> None:
        """Set the starting node."""
        self.start_node = node_name
        logger.info("start_node_set", node=node_name)

    def cancel(self) -> None:
        """Request cancellation of the workflow."""
        self._cancelled = True
        logger.info("workflow_cancellation_requested", task_id=self.context.task_id if self.context else None)

    async def execute(
        self,
        context: WorkflowContext,
        start_at: str | None = None,
    ) -> dict[str, Any]:
        """Execute the workflow with retry, checkpoint, and cancellation support."""
        self.context = context
        self._cancelled = False
        current = start_at or self.start_node
        context.state = WorkflowState.RUNNING

        logger.info("workflow_started", task_id=context.task_id, start_node=current)

        # Resume from checkpoint: skip completed nodes
        if self.checkpoint_manager:
            try:
                checkpoint = await self.checkpoint_manager.get_checkpoint(context.task_id)
                if checkpoint and await self.checkpoint_manager.is_valid(context.task_id):
                    snapshot = checkpoint.get("context_snapshot", {})
                    completed = snapshot.get("completed_nodes", [])
                    if completed:
                        logger.info("resuming_from_checkpoint", task_id=context.task_id, completed_count=len(completed))
                        if "shared_data" in snapshot:
                            context.shared_data.update(snapshot["shared_data"])
                        while current and current in completed:
                            logger.info("skipping_completed_node", node=current)
                            next_nodes = self.edges.get(current, [])
                            current = next_nodes[0] if next_nodes else None
                        if current is None:
                            context.state = WorkflowState.COMPLETED
                            return {
                                "state": context.state.value,
                                "current_node": context.current_node,
                                "node_results": {k: {"status": v.status.value} for k, v in context.node_results.items()},
                            }
            except Exception:
                logger.exception("checkpoint_resume_failed", task_id=context.task_id)

        while current and current in self.nodes:
            if self._cancelled:
                logger.warning("workflow_cancelled", task_id=context.task_id)
                context.state = WorkflowState.CANCELLED
                break

            context.current_node = current
            node = self.nodes[current]
            max_retries = getattr(node, 'max_retries', 1)

            logger.info("executing_node", node=current, task_id=context.task_id)

            # Retry loop: retry on both FAILED status and exceptions
            result = None
            for attempt in range(max_retries):
                if self._cancelled:
                    break
                try:
                    result = await self._execute_with_timeout(node, context)
                    if result.status == NodeStatus.FAILED and attempt < max_retries - 1:
                        delay = min(2 ** attempt, 30)
                        logger.warning("node_failed_retrying", node=current, attempt=attempt + 1, delay=delay)
                        await asyncio.sleep(delay)
                        continue
                    break
                except Exception:
                    if attempt < max_retries - 1:
                        delay = min(2 ** attempt, 30)
                        logger.warning("node_exception_retrying", node=current, attempt=attempt + 1, delay=delay)
                        await asyncio.sleep(delay)
                        continue
                    logger.exception("node_exception_retries_exhausted", node=current, task_id=context.task_id)
                    context.state = WorkflowState.FAILED
                    break

            if self._cancelled:
                context.state = WorkflowState.CANCELLED
                break

            if result is None:
                result = await node.on_retry(context, max_retries)

            context.node_results[current] = result

            if result.status == NodeStatus.FAILED:
                context.state = WorkflowState.FAILED
                logger.error("node_failed", node=current, task_id=context.task_id, error=result.error)
                break

            # Save checkpoint after successful node
            if self.checkpoint_manager:
                try:
                    snapshot = {
                        "completed_nodes": [
                            n for n, r in context.node_results.items()
                            if r.status == NodeStatus.COMPLETED
                        ],
                        "current_node": current,
                        "shared_data": context.shared_data,
                        "topic": context.topic,
                        "domain": context.domain,
                        "doc_type": context.doc_type,
                        "language": context.language,
                    }
                    await self.checkpoint_manager.create_checkpoint(
                        task_id=context.task_id,
                        node_name=current,
                        context_snapshot=snapshot,
                    )
                except Exception:
                    logger.exception("checkpoint_save_failed", task_id=context.task_id)

            # Determine next node
            next_nodes = self.edges.get(current, [])
            current = next_nodes[0] if next_nodes else None

        if context.state == WorkflowState.RUNNING:
            context.state = WorkflowState.COMPLETED
            if self.checkpoint_manager:
                await self.checkpoint_manager.delete_checkpoint(context.task_id)

        logger.info(
            "workflow_completed",
            task_id=context.task_id,
            final_state=context.state.value,
        )

        return {
            "state": context.state.value,
            "current_node": context.current_node,
            "node_results": {k: {"status": v.status.value} for k, v in context.node_results.items()},
        }

    async def _execute_with_timeout(
        self, node: WorkflowNode, context: WorkflowContext
    ) -> NodeResult:
        """Execute node with timeout handling."""
        import asyncio
        import time

        start_time = time.time()

        try:
            result = await asyncio.wait_for(
                node.execute(context),
                timeout=node.timeout_seconds,
            )
            result.duration_ms = int((time.time() - start_time) * 1000)
            return result

        except TimeoutError:
            return await node.on_timeout(context)

        except Exception as e:
            return NodeResult(
                node_name=node.name,
                status=NodeStatus.FAILED,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000),
            )

    def can_transition(self, from_state: WorkflowState, to_state: WorkflowState) -> bool:
        """Check if state transition is valid."""
        valid_transitions = {
            WorkflowState.INITIALIZED: [WorkflowState.RUNNING, WorkflowState.CANCELLED],
            WorkflowState.RUNNING: [
                WorkflowState.PAUSED,
                WorkflowState.COMPLETED,
                WorkflowState.FAILED,
                WorkflowState.CANCELLED,
            ],
            WorkflowState.PAUSED: [WorkflowState.RUNNING, WorkflowState.CANCELLED],
            WorkflowState.COMPLETED: [],
            WorkflowState.FAILED: [],
            WorkflowState.CANCELLED: [],
        }
        return to_state in valid_transitions.get(from_state, [])
