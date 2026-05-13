"""SSE (Server-Sent Events) stream for real-time progress updates."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from ..event_storage import get_task_events, get_task_status

router = APIRouter()


async def event_generator(task_id: uuid.UUID) -> AsyncIterator[str]:
    """Generate SSE events from real workflow progress."""
    last_index = 0

    while True:
        task_data = get_task_status(task_id)
        if task_data:
            status_val = task_data.get("status", "")
            if status_val in ["COMPLETED", "FAILED", "CANCELLED", "STOPPED"]:
                if status_val == "COMPLETED":
                    yield f"data: {json.dumps({'event': 'task_complete', 'message': '任务完成', 'output_path': task_data.get('output_path', '')})}\n\n"
                elif status_val == "STOPPED":
                    stop_reason = task_data.get('stop_reason') or task_data.get('error_message') or '任务已停止'
                    yield f"data: {json.dumps({'event': 'task_stopped', 'message': stop_reason, 'reason': stop_reason})}\n\n"
                else:
                    stop_reason = task_data.get('error_message') or ('任务已取消' if status_val == "CANCELLED" else '任务失败')
                    yield f"data: {json.dumps({'event': 'task_failed', 'message': stop_reason, 'reason': stop_reason})}\n\n"
                break

        events = get_task_events(task_id)
        while last_index < len(events):
            event = events[last_index]
            yield f"data: {json.dumps(event)}\n\n"
            last_index += 1

        await asyncio.sleep(1)


@router.get("/{task_id}/stream")
async def stream_task_progress(task_id: uuid.UUID):
    """Stream real-time progress updates for a task via SSE."""
    # Check if task exists in our in-memory storage
    task_status = get_task_status(task_id)
    if task_status is None:
        # Task not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ERR_TASK_001", "message": f"Task not found: {task_id}"},
        )

    async def event_generator_wrapper():
        # Send initial connection event with proper SSE format (manual "data: " prefix)
        yield f"data: {json.dumps({'event': 'connected', 'message': 'Connected to task stream'})}\n\n"

        # Stream events
        async for event in event_generator(task_id):
            yield event

    return StreamingResponse(
        event_generator_wrapper(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
