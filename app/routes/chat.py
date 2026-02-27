import os
import sys
import json
import asyncio

from contextlib import suppress
from datetime import datetime, timezone
from typing import AsyncGenerator, Dict, Any

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse

sys.path.append(os.getcwd())

from app.schemas import (
    ChatRequest,
    ChatResponse,
    SessionCreateResponse,
    SessionDeleteResponse,
    StreamEvent,
)

router = APIRouter()


def _utc_iso() -> str:
    """
    Build UTC ISO timestamp.

    Args:
        None.

    Returns:
        ISO 8601 UTC timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


def _build_error_event(message: str) -> Dict[str, Any]:
    """
    Build a normalized error event payload.

    Args:
        message: Error message text.

    Returns:
        Event dictionary.
    """
    return {
        "type": "error",
        "timestamp": _utc_iso(),
        "data": {"message": message},
    }


def _to_sse(event: Dict[str, Any]) -> str:
    """
    Serialize event dictionary to SSE frame.

    Args:
        event: Event dictionary.

    Returns:
        SSE frame text.
    """
    event_name = event.get("type", "status")
    payload = json.dumps(event, ensure_ascii = False)
    return f"event: {event_name}\ndata: {payload}\n\n"


@router.post("/sessions", response_model = SessionCreateResponse)
def create_session(request: Request) -> SessionCreateResponse:
    """
    Create a new chat session.

    Args:
        request: FastAPI request object.

    Returns:
        Created session payload.
    """
    manager = request.app.state.session_manager
    session = manager.create_session()
    return SessionCreateResponse(
        session_id = session.session_id,
        created_at = session.created_at.isoformat(),
        expires_at = session.expires_at.isoformat(),
    )


@router.delete("/sessions/{session_id}", response_model = SessionDeleteResponse)
def delete_session(session_id: str, request: Request) -> SessionDeleteResponse:
    """
    Delete a chat session.

    Args:
        session_id: Target session ID.
        request: FastAPI request object.

    Returns:
        Session delete response.
    """
    manager = request.app.state.session_manager
    deleted = manager.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code = 404, detail = "Session not found.")

    return SessionDeleteResponse(session_id = session_id, deleted = True)


@router.post("/chat", response_model = ChatResponse)
def chat(payload: ChatRequest, request: Request) -> ChatResponse:
    """
    Execute synchronous chat interaction.

    Args:
        payload: Chat request payload.
        request: FastAPI request object.

    Returns:
        Full chat response with events.
    """
    manager = request.app.state.session_manager
    service = request.app.state.agent_service

    session = manager.get_session(payload.session_id, touch = True)
    if not session:
        raise HTTPException(status_code = 404, detail = "Session not found or expired.")

    history = manager.get_history(payload.session_id) or []
    manager.append_message(payload.session_id, "user", payload.message)

    try:
        answer, events = service.run_sync(
            history = history,
            message = payload.message,
            max_iterations = payload.max_iterations,
        )
    except Exception as exc:
        manager.append_message(payload.session_id, "assistant", f"Error: {exc}")
        raise HTTPException(status_code = 500, detail = str(exc)) from exc

    manager.append_message(payload.session_id, "assistant", answer)

    return ChatResponse(
        session_id = payload.session_id,
        answer = answer,
        events = [StreamEvent(**event) for event in events],
        timestamp = _utc_iso(),
    )


@router.post("/chat/stream")
async def chat_stream(payload: ChatRequest, request: Request) -> StreamingResponse:
    """
    Execute streaming chat interaction over SSE.

    Args:
        payload: Chat request payload.
        request: FastAPI request object.

    Returns:
        StreamingResponse for SSE frames.
    """
    manager = request.app.state.session_manager
    service = request.app.state.agent_service

    session = manager.get_session(payload.session_id, touch = True)
    if not session:
        raise HTTPException(status_code = 404, detail = "Session not found or expired.")

    history = manager.get_history(payload.session_id) or []
    manager.append_message(payload.session_id, "user", payload.message)

    event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def emit_event(event: Dict[str, Any]) -> None:
        loop.call_soon_threadsafe(event_queue.put_nowait, event)

    async def produce_events() -> None:
        final_answer = ""
        try:
            final_answer = await asyncio.to_thread(
                service.run_stream,
                history,
                payload.message,
                emit_event,
                payload.max_iterations,
            )
        except Exception as exc:
            await event_queue.put(_build_error_event(str(exc)))
        finally:
            if final_answer:
                manager.append_message(payload.session_id, "assistant", final_answer)
            await event_queue.put(
                {
                    "type": "done",
                    "timestamp": _utc_iso(),
                    "data": {"message": "stream closed"},
                }
            )

    async def event_generator() -> AsyncGenerator[str, None]:
        producer_task = asyncio.create_task(produce_events())
        try:
            while True:
                event = await event_queue.get()
                yield _to_sse(event)
                if event.get("type") == "done":
                    break
                if await request.is_disconnected():
                    break
        finally:
            if not producer_task.done():
                producer_task.cancel()
                with suppress(asyncio.CancelledError):
                    await producer_task

    return StreamingResponse(
        event_generator(),
        media_type = "text/event-stream",
        headers = {
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
