"""Research task API routes."""

import asyncio
import concurrent.futures
import json
import os
import threading
import uuid
from datetime import UTC, datetime
from typing import Final

from fastapi import APIRouter, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

from ...storage.cache import redis_client
from ...utils.document_parser import DocumentParser
from ...utils.logger import get_logger
from ..event_storage import publish_step_event, register_task, update_task_status
from ..schemas import (
    CancelTaskResponse,
    CreateTaskRequest,
    CreateTaskResponse,
    PauseTaskResponse,
    ResumeTaskResponse,
    TaskStatus,
    TaskStatusResponse,
)

logger = get_logger(__name__)

router = APIRouter()

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
_task_cancel_events: dict[uuid.UUID, threading.Event] = {}


class TaskCancelledError(Exception):
    """Exception to signal that a task was cancelled."""


def _raise_if_cancelled(task_id: uuid.UUID) -> None:
    """Raise TaskCancelledError if a cancel event is set for this task."""
    event = _task_cancel_events.get(task_id)
    if event and event.is_set():
        raise TaskCancelledError(f"Task {task_id} was cancelled")

ALLOWED_EXTENSIONS: Final[set[str]] = {".docx", ".pdf", ".md", ".doc"}
ALLOWED_CONTENT_TYPES: Final[dict[str, set[str]]] = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".doc": {"application/msword"},
    ".md": {"text/markdown", "text/plain"},
}

MAGIC_NUMBERS: Final[dict[str, bytes]] = {
    ".pdf": b"%PDF",
    ".docx": b"PK\x03\x04",
    ".doc": b"\xd0\xcf\x11\xe0",
    ".md": b"",
}


def _validate_magic_number(content: bytes, ext: str) -> bool:
    magic = MAGIC_NUMBERS.get(ext)
    if magic is None or magic == b"":
        return True
    return content[: len(magic)] == magic


@router.post("/upload-template")
async def upload_template(file: UploadFile):
    filename = file.filename or "unknown"
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    content = await file.read()

    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5MB limit"
        )

    if not _validate_magic_number(content, ext):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content does not match declared file type"
        )

    try:
        markdown_content = DocumentParser.parse_from_bytes(content, filename, ext)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("template_parse_failed", filename=filename, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse document: {str(e)}"
        )

    return JSONResponse({
        "success": True,
        "filename": filename,
        "template_content": markdown_content,
        "size": len(content)
    })


class TaskStorage:
    """Task storage with Redis primary and in-memory fallback."""

    def __init__(self):
        self._memory: dict[uuid.UUID, dict] = {}
        self._use_redis = True

    async def set(self, task_id: uuid.UUID, data: dict) -> bool:
        """Store task data."""
        self._memory[task_id] = data
        try:
            return await redis_client.set(f"task:{task_id}", data, expire_seconds=86400)
        except Exception as e:
            logger.warning("redis_task_storage_failed", task_id=str(task_id), error=str(e))
            self._use_redis = False
            return True

    async def get(self, task_id: uuid.UUID) -> dict | None:
        """Get task data."""
        if task_id in self._memory:
            return self._memory[task_id]
        try:
            result = await redis_client.get(f"task:{task_id}")
            if result:
                data = json.loads(result) if isinstance(result, str) else result
                self._memory[task_id] = data
                return data
        except Exception as e:
            logger.warning("redis_task_get_failed", task_id=str(task_id), error=str(e))
        return None

    async def delete(self, task_id: uuid.UUID) -> bool:
        """Delete task data."""
        self._memory.pop(task_id, None)
        try:
            await redis_client.delete(f"task:{task_id}")
        except Exception:
            pass
        return True

    def get_sync(self, task_id: uuid.UUID) -> dict | None:
        """Get task data synchronously (for background tasks)."""
        return self._memory.get(task_id)

    def set_sync(self, task_id: uuid.UUID, data: dict) -> None:
        """Store task data synchronously (for background tasks)."""
        self._memory[task_id] = data


task_storage = TaskStorage()


def publish_workflow_event(task_id: uuid.UUID, event_type: str, node: str, message: str) -> None:
    """Publish workflow step event for SSE."""
    publish_step_event(task_id, event_type, node, message)


def publish_workflow_complete(task_id: uuid.UUID, status: str, output_path: str | None = None, error_message: str | None = None) -> None:
    """Publish workflow completion event for SSE."""
    update_task_status(task_id, status, output_path, error_message)


async def run_workflow_async(task_id: uuid.UUID, task_data: dict):
    """Background task to run the workflow, checking cancellation before and after execution."""
    from ...utils.logger import get_logger

    logger = get_logger(__name__)

    logger.info(f"=== STARTING WORKFLOW for task {task_id} ===")

    # Check if cancelled before starting
    try:
        _raise_if_cancelled(task_id)
    except TaskCancelledError:
        logger.warning("workflow_cancelled_before_start", task_id=str(task_id))
        task = task_storage.get_sync(task_id)
        if task:
            task["status"] = TaskStatus.CANCELLED
            task["error_message"] = "用户手动停止任务"
            task_storage.set_sync(task_id, task)
        update_task_status(task_id, "CANCELLED", error_message="用户手动停止任务")
        from ..event_storage import publish_task_stopped_event
        publish_task_stopped_event(task_id, "任务已取消", "workflow")
        return

    def update_node(node_name: str):
        task = task_storage.get_sync(task_id)
        if task:
            task["current_node"] = node_name
            logger.info(f"Updated current_node to: {node_name}")

    # 导入工作流执行器
    from ...workflow.executor import get_workflow_executor

    try:
        logger.info("getting_executor", task_id=str(task_id))
        executor = get_workflow_executor()
        logger.info("executor_ready", task_id=str(task_id), executor=executor)
        logger.info("starting_workflow", task_id=str(task_id))

        # Publish task start event
        publish_workflow_event(task_id, "node_start", "intent_analysis", "Starting workflow...")

        # 更新当前节点
        update_node("intent_analysis")

        result = await executor.execute_task(
            task_id=str(task_id),
            topic=task_data["topic"],
            domain=task_data["domain"],
            doc_type=task_data["doc_type"],
            requirements=task_data.get("requirements"),
            template_path=task_data.get("template_path"),
            template_content=task_data.get("template_content"),
            temp_prompt=task_data.get("temp_prompt"),
            attachment_content=task_data.get("attachment_content"),
        )

        task = task_storage.get_sync(task_id)
        if task:
            task_status_str = result.get("status", "")
            output_path = result.get("output", {}).get("results", {}).get("outputs", {}).get("publish", {}).get("output_path")

            if task_status_str.upper() == "COMPLETED":
                task["status"] = TaskStatus.COMPLETED
            else:
                task["status"] = TaskStatus.FAILED

            task["completed_at"] = datetime.now(UTC)
            task["current_node"] = "publishing"
            task["output_path"] = output_path
            task_storage.set_sync(task_id, task)

            from ..event_storage import _task_status as es_status
            if task_id in es_status:
                es_status[task_id]["status"] = task["status"].value
                es_status[task_id]["current_node"] = "publishing"
                es_status[task_id]["output_path"] = output_path

            status_for_sse = "COMPLETED" if task["status"] == TaskStatus.COMPLETED else "FAILED"
            publish_workflow_complete(task_id, status_for_sse, output_path)

            if task["status"] == TaskStatus.FAILED:
                error_msg = (
                    result.get("error") or
                    result.get("output", {}).get("reason") or
                    result.get("output", {}).get("error") or
                    "任务执行失败"
                )
                task["error_message"] = error_msg
                task_storage.set_sync(task_id, task)
                if task_id in es_status:
                    es_status[task_id]["error_message"] = error_msg

                reason_lower = error_msg.lower()
                if "too broad" in reason_lower or "太宽泛" in reason_lower or "not feasible" in reason_lower or "不可行" in reason_lower:
                    stop_reason = "课题太宽泛，请重新输入更具体的研究主题"
                    es_status[task_id]["stop_reason"] = stop_reason
                    es_status[task_id]["status"] = "STOPPED"
                    task["error_message"] = stop_reason
                    task_storage.set_sync(task_id, task)
                    from ..event_storage import publish_task_stopped_event
                    publish_task_stopped_event(task_id, stop_reason, task.get("current_node", "workflow"))
                logger.info("workflow_done", task_id=str(task_id), status="FAILED", error=error_msg)
            else:
                logger.info("workflow_done", task_id=str(task_id), status="COMPLETED")

    except TaskCancelledError:
        logger.info("workflow_cancelled_during_execution", task_id=str(task_id))
        task = task_storage.get_sync(task_id)
        if task:
            task["status"] = TaskStatus.CANCELLED
            task["error_message"] = "用户手动停止任务"
            task["completed_at"] = datetime.now(UTC)
            task_storage.set_sync(task_id, task)
        update_task_status(task_id, "CANCELLED", error_message="用户手动停止任务")
        from ..event_storage import publish_task_stopped_event
        publish_task_stopped_event(task_id, "任务已取消", task.get("current_node", "workflow") if task else "workflow")
    except Exception as e:
        logger.error("workflow_error", task_id=str(task_id), error=str(e))
        task = task_storage.get_sync(task_id)
        if task:
            task["status"] = TaskStatus.FAILED
            task["error_message"] = str(e)
            task_storage.set_sync(task_id, task)
        from ..event_storage import publish_task_stopped_event
        error_str = str(e)
        if "timeout" in error_str.lower():
            stop_reason = "任务执行超时，请重试或尝试更简单的课题"
        else:
            stop_reason = f"任务意外停止: {error_str[:100]}"
        publish_workflow_complete(task_id, "FAILED", error_message=stop_reason)
        publish_task_stopped_event(task_id, stop_reason, task.get("current_node", "workflow") if task else "workflow")
    finally:
        _task_cancel_events.pop(task_id, None)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_task(request: CreateTaskRequest):
    """Create a new research task."""
    task_id = uuid.uuid4()
    now = datetime.now(UTC)

    task = {
        "id": task_id,
        "topic": request.topic,
        "domain": request.domain.value,
        "doc_type": request.doc_type.value,
        "requirements": request.requirements,
        "template_path": request.template_path,
        "template_content": request.template_content,
        "temp_prompt": request.temp_prompt,
        "attachment_content": request.attachment_content,
        "status": TaskStatus.PENDING,
        "current_node": None,
        "progress": 0,
        "created_at": now,
        "started_at": None,
        "updated_at": None,
        "completed_at": None,
        "output_path": None,
        "error_message": None,
    }

    await task_storage.set(task_id, task)

    register_task(task_id)

    # Set up cancellation event
    cancel_event = threading.Event()
    _task_cancel_events[task_id] = cancel_event
    from ..event_storage import register_cancellation_callback
    register_cancellation_callback(task_id, lambda: cancel_event.set())

    def async_runner():
        import time
        time.sleep(0.5)
        # Use configurable log file path from environment or default to workspace
        log_dir = os.getenv("WORKFLOW_LOG_DIR", os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        log_file = os.path.join(log_dir, "workflow_log.txt")

        # Ensure log directory exists
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)

        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"=== Starting task {task_id} ===\n")

            # Run workflow in new event loop with proper cleanup
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(run_workflow_async(task_id, task))
            finally:
                loop.close()

            with open(log_file, "a", encoding="utf-8") as f:
                f.write(f"=== Completed task {task_id} ===\n")
        except Exception as e:
            try:
                with open(log_file, "a", encoding="utf-8") as f:
                    import traceback
                    f.write(f"=== Error in task {task_id}: {e} ===\n")
                    f.write(traceback.format_exc())
            except Exception:
                pass  # If logging also fails, continue

    t = threading.Thread(target=async_runner)
    t.daemon = True
    t.start()

    task["status"] = TaskStatus.RUNNING
    task["current_node"] = "intent_analysis"
    task["started_at"] = now
    task["updated_at"] = now

    # Update stream status
    update_task_status(task_id, "RUNNING")
    publish_step_event(task_id, "node_start", "intent_analysis", f"Starting research: {request.topic}")

    # Publish start event
    publish_workflow_event(task_id, "node_start", "intent_analysis", f"Starting research: {request.topic}")

    return CreateTaskResponse(
        taskId=task_id,
        status=task["status"],
        message="Task created, workflow starting..."
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: uuid.UUID) -> TaskStatusResponse:
    """Get task status and details."""
    task = await task_storage.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_TASK_001", "message": f"Task not found: {task_id}"},
        )

    # 从event_storage获取最新的current_node（实时更新）
    from ..event_storage import get_task_status as get_event_status
    event_status = get_event_status(task_id)
    current_node = task["current_node"]
    if event_status and event_status.get("current_node"):
        current_node = event_status["current_node"]

    # 获取实时状态
    status_value = task["status"]
    if event_status and event_status.get("status"):
        status_value = event_status["status"]

    # 获取当前节点的详细输出（优先用complete事件的detail，回退用start事件的detail）
    node_detail = None
    if event_status and current_node:
        # 优先获取 node_complete 事件的详细输出（模型实际返回的内容）
        if event_status.get("node_details") and current_node in event_status["node_details"]:
            node_detail = event_status["node_details"].get(current_node)
        # 回退：获取 node_start 事件的详细输出（开始参数）
        elif event_status.get("node_start_details") and current_node in event_status["node_start_details"]:
            node_detail = event_status["node_start_details"].get(current_node)

    # 动态构建返回数据，包含node_detail
    response_data = {
        "taskId": task["id"],
        "status": status_value,
        "currentNode": current_node,
        "progress": task["progress"],
        "createdAt": task["created_at"],
        "startedAt": task["started_at"],
        "updatedAt": task["updated_at"],
        "completedAt": task["completed_at"],
        "outputPath": task["output_path"],
        "errorMessage": task["error_message"],
        "nodeDetail": node_detail,
    }

    return TaskStatusResponse(**response_data)


@router.post("/{task_id}/pause", response_model=PauseTaskResponse)
async def pause_task(task_id: uuid.UUID) -> PauseTaskResponse:
    """Pause a running task."""
    task = await task_storage.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_TASK_001", "message": f"Task not found: {task_id}"},
        )

    if task["status"] != TaskStatus.RUNNING:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_TASK_003",
                "message": f"Cannot pause task in status: {task['status']}",
            },
        )

    # Update task status
    task["status"] = TaskStatus.PAUSED
    task["updated_at"] = datetime.now(UTC)
    await task_storage.set(task_id, task)

    # Update SSE status
    update_task_status(task_id, "PAUSED")

    resume_token = f"resume-{uuid.uuid4().hex[:12]}"

    return PauseTaskResponse(
        taskId=task_id,
        status=TaskStatus.PAUSED,
        checkpointId=f"chkp-{task_id.hex[:8]}",
        resumeToken=resume_token,
        message="Task paused. Resume within 24 hours.",
    )


@router.post("/{task_id}/resume", response_model=ResumeTaskResponse)
async def resume_task(task_id: uuid.UUID, request: dict) -> ResumeTaskResponse:
    """Resume a paused task."""
    task = await task_storage.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_TASK_001", "message": f"Task not found: {task_id}"},
        )

    if task["status"] != TaskStatus.PAUSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_TASK_003",
                "message": f"Cannot resume task in status: {task['status']}",
            },
        )

    # Update task status
    task["status"] = TaskStatus.RUNNING
    task["current_node"] = "drafting"
    task["updated_at"] = datetime.now(UTC)
    await task_storage.set(task_id, task)

    return ResumeTaskResponse(
        taskId=task_id,
        status=TaskStatus.RUNNING,
        currentNode="drafting",
        message="Task resumed from checkpoint",
    )


@router.delete("/{task_id}", response_model=CancelTaskResponse)
async def cancel_task(task_id: uuid.UUID) -> CancelTaskResponse:
    """Cancel a task."""
    task = await task_storage.get(task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_TASK_001", "message": f"Task not found: {task_id}"},
        )

    if task["status"] in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "ERR_TASK_003",
                "message": f"Cannot cancel task in status: {task['status']}",
            },
        )

    task["status"] = TaskStatus.CANCELLED
    task["updated_at"] = datetime.now(UTC)
    task["completed_at"] = datetime.now(UTC)
    task["error_message"] = "用户手动停止任务"
    await task_storage.set(task_id, task)

    update_task_status(task_id, "CANCELLED", error_message="用户手动停止任务")

    from ..event_storage import publish_task_stopped_event, cancel_task as cancel_event_storage
    cancel_event_storage(task_id)
    publish_task_stopped_event(task_id, "用户手动停止任务", task.get("current_node", "workflow"))

    # Also set the threading.Event for the background worker
    event = _task_cancel_events.get(task_id)
    if event:
        event.set()

    return CancelTaskResponse(
        taskId=task_id,
        status=TaskStatus.CANCELLED,
        message="用户手动停止任务",
    )


# Debug endpoint - remove in production
@router.get("/_debug/event_storage")
async def debug_event_storage():
    """Debug endpoint to view event storage state."""
    from ..event_storage import _task_status
    return {"_task_status": {str(k): v for k, v in _task_status.items()}}

@router.get("/_debug/event_storage/{task_id}")
async def debug_task_events(task_id: uuid.UUID):
    """Debug endpoint to view specific task events."""
    from ..event_storage import _task_events, _task_status

    # Convert UUID to string for dict key lookup
    task_id_str = str(task_id)

    # Try to find in both dicts
    events = _task_events.get(task_id, [])
    status = _task_status.get(task_id, {})

    # Also try string key
    if task_id_str not in _task_events:
        for key in _task_events:
            if str(key) == task_id_str:
                events = _task_events[key]
                break
    if task_id_str not in _task_status:
        for key in _task_status:
            if str(key) == task_id_str:
                status = _task_status[key]
                break

    return {
        "task_id": task_id_str,
        "events": events,
        "status": status,
        "node_details": status.get("node_details", {})
    }
