"""Shared event storage for SSE and task tracking."""

import threading
import time
import uuid
from collections.abc import Callable
from typing import Any

_task_events: dict[uuid.UUID, list[dict[str, Any]]] = {}
_task_status: dict[uuid.UUID, dict[str, Any]] = {}
_task_timestamps: dict[uuid.UUID, float] = {}
_task_cancellations: dict[uuid.UUID, Callable[[], None]] = {}

CLEANUP_INTERVAL = 300
ENTRY_TTL = 3600
_cleanup_lock = threading.Lock()
_cleanup_thread: threading.Thread | None = None


def _start_cleanup_thread() -> None:
    global _cleanup_thread
    if _cleanup_thread is None or not _cleanup_thread.is_alive():
        _cleanup_thread = threading.Thread(target=_cleanup_loop, daemon=True)
        _cleanup_thread.start()


def _cleanup_loop() -> None:
    while True:
        time.sleep(CLEANUP_INTERVAL)
        _cleanup_expired_entries()


def _cleanup_expired_entries() -> None:
    with _cleanup_lock:
        now = time.time()
        expired = [tid for tid, ts in _task_timestamps.items() if now - ts > ENTRY_TTL]
        for tid in expired:
            _task_events.pop(tid, None)
            _task_status.pop(tid, None)
            _task_timestamps.pop(tid, None)
            _task_cancellations.pop(tid, None)


def register_cancellation_callback(task_id: uuid.UUID, callback: Callable[[], None]) -> None:
    _task_cancellations[task_id] = callback


def cancel_task(task_id: uuid.UUID) -> bool:
    if task_id in _task_cancellations:
        callback = _task_cancellations.pop(task_id)
        callback()
        return True
    return False


def publish_step_event(task_id: uuid.UUID, event_type: str, node: str, message: str, detail: str | None = None) -> None:
    if task_id not in _task_events:
        _task_events[task_id] = []
    _task_timestamps[task_id] = time.time()

    event = {"event": event_type, "node": node, "message": message}
    if detail is not None:
        event["detail"] = detail
    _task_events[task_id].append(event)

    if task_id not in _task_status:
        _task_status[task_id] = {"status": "RUNNING", "current_node": node, "output_path": None, "error_message": None, "node_details": {}, "node_start_details": {}}
    else:
        _task_status[task_id]["current_node"] = node
        if detail is not None:
            if "node_details" not in _task_status[task_id]:
                _task_status[task_id]["node_details"] = {}
            if "node_start_details" not in _task_status[task_id]:
                _task_status[task_id]["node_start_details"] = {}
            if event_type == "node_complete":
                _task_status[task_id]["node_details"][node] = detail
            elif event_type == "node_start":
                _task_status[task_id]["node_start_details"][node] = detail


def update_task_status(task_id: uuid.UUID, status: str, output_path: str | None = None, error_message: str | None = None, stop_reason: str | None = None) -> None:
    if task_id not in _task_status:
        _task_status[task_id] = {}
    _task_status[task_id]["status"] = status
    if output_path:
        _task_status[task_id]["output_path"] = output_path
    if error_message:
        _task_status[task_id]["error_message"] = error_message
    if stop_reason:
        _task_status[task_id]["stop_reason"] = stop_reason


def publish_task_stopped_event(task_id: uuid.UUID, reason: str, node: str) -> None:
    publish_step_event(task_id, "task_stopped", node, reason)


def register_task(task_id: uuid.UUID) -> None:
    _task_events[task_id] = []
    _task_status[task_id] = {"status": "INITIALIZED", "current_node": None, "output_path": None, "error_message": None, "node_details": {}, "node_start_details": {}}
    _task_timestamps[task_id] = time.time()
    _start_cleanup_thread()


def get_task_status(task_id: uuid.UUID) -> dict | None:
    return _task_status.get(task_id)


def get_task_events(task_id: uuid.UUID) -> list[dict[str, Any]]:
    return _task_events.get(task_id, [])
