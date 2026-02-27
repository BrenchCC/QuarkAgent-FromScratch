#!/usr/bin/env python3
"""
Test script to verify the web API functionality.
"""
import os
import sys
import json
import time
import logging

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient

sys.path.append(os.getcwd())

from app.main import create_app

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


class FakeAgentService:
    """Mock service for deterministic API testing."""

    @staticmethod
    def _utc_iso() -> str:
        """
        Build UTC ISO timestamp.

        Args:
            None.

        Returns:
            UTC ISO timestamp string.
        """
        return datetime.now(timezone.utc).isoformat()

    def get_available_tools(self) -> List[str]:
        """
        Return fake tool list.

        Args:
            None.

        Returns:
            List of fake tools.
        """
        return ["read", "write", "bash", "calculator"]

    def run_sync(
        self,
        history: List[Dict[str, str]],
        message: str,
        max_iterations: int = 10,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Return fake synchronous answer and events.

        Args:
            history: Existing history list.
            message: Incoming user message.
            max_iterations: Maximum iterations.

        Returns:
            Tuple of answer and event list.
        """
        del history
        del max_iterations

        answer = f"echo: {message}"
        events = [
            {"type": "status", "timestamp": self._utc_iso(), "data": {"message": "Thinking..."}},
            {"type": "tool_start", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "arguments": {"expression": "2+2"}}},
            {"type": "tool_end", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "result": "4"}},
            {"type": "final", "timestamp": self._utc_iso(), "data": {"answer": answer}},
            {"type": "done", "timestamp": self._utc_iso(), "data": {"message": "stream closed"}},
        ]
        return answer, events

    def run_stream(
        self,
        history: List[Dict[str, str]],
        message: str,
        emit_event,
        max_iterations: int = 10,
    ) -> str:
        """
        Emit fake stream events then return final answer.

        Args:
            history: Existing history list.
            message: Incoming user message.
            emit_event: Event emitter callback.
            max_iterations: Maximum iterations.

        Returns:
            Final answer.
        """
        del history
        del max_iterations

        answer = f"echo: {message}"
        emit_event({"type": "status", "timestamp": self._utc_iso(), "data": {"message": "Thinking..."}})
        emit_event({"type": "tool_start", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "arguments": {"expression": "2+2"}}})
        emit_event({"type": "tool_end", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "result": "4"}})
        emit_event({"type": "final", "timestamp": self._utc_iso(), "data": {"answer": answer}})
        return answer


def build_client() -> Tuple[TestClient, Any]:
    """
    Build a test client with fake service.

    Args:
        None.

    Returns:
        Tuple of client and app.
    """
    app = create_app()
    app.state.agent_service = FakeAgentService()
    return TestClient(app), app


def parse_sse_text(raw_text: str) -> List[Dict[str, Any]]:
    """
    Parse SSE raw text into event dictionaries.

    Args:
        raw_text: Raw SSE text content.

    Returns:
        Parsed event payload list.
    """
    payloads: List[Dict[str, Any]] = []
    frames = [item.strip() for item in raw_text.split("\n\n") if item.strip()]

    for frame in frames:
        lines = [line.strip() for line in frame.split("\n") if line.strip()]
        data_lines = [line[5:].strip() for line in lines if line.startswith("data:")]
        if not data_lines:
            continue
        payloads.append(json.loads("\n".join(data_lines)))

    return payloads


def test_health() -> bool:
    """Test health endpoint."""
    logger.info("=" * 80)
    logger.info("Testing /api/health")
    logger.info("=" * 80)

    client, _ = build_client()
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "app_name" in body
    assert "version" in body
    logger.info("✓ /api/health passed")
    return True


def test_create_and_delete_session() -> bool:
    """Test session creation and deletion endpoints."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing /api/sessions create/delete")
    logger.info("-" * 60)

    client, _ = build_client()

    create_response = client.post("/api/sessions")
    assert create_response.status_code == 200
    session_body = create_response.json()
    assert "session_id" in session_body

    delete_response = client.delete(f"/api/sessions/{session_body['session_id']}")
    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["deleted"] is True
    logger.info("✓ /api/sessions create/delete passed")
    return True


def test_sync_chat() -> bool:
    """Test synchronous chat endpoint."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing /api/chat")
    logger.info("-" * 60)

    client, _ = build_client()
    session_id = client.post("/api/sessions").json()["session_id"]

    response = client.post(
        "/api/chat",
        json = {
            "session_id": session_id,
            "message": "hello api",
            "max_iterations": 10,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "echo: hello api"
    event_types = [event["type"] for event in body["events"]]
    assert "final" in event_types
    assert "done" in event_types
    logger.info("✓ /api/chat passed")
    return True


def test_stream_chat() -> bool:
    """Test streaming chat endpoint."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing /api/chat/stream")
    logger.info("-" * 60)

    client, _ = build_client()
    session_id = client.post("/api/sessions").json()["session_id"]

    with client.stream(
        "POST",
        "/api/chat/stream",
        json = {
            "session_id": session_id,
            "message": "stream this",
            "max_iterations": 10,
        },
    ) as response:
        assert response.status_code == 200
        stream_text = "".join(chunk for chunk in response.iter_text())

    events = parse_sse_text(stream_text)
    event_types = [event["type"] for event in events]

    required_types = ["status", "tool_start", "tool_end", "final", "done"]
    for event_type in required_types:
        assert event_type in event_types

    assert event_types.index("status") < event_types.index("tool_start")
    assert event_types.index("tool_start") < event_types.index("tool_end")
    assert event_types.index("tool_end") < event_types.index("final")
    assert event_types.index("final") < event_types.index("done")
    logger.info("✓ /api/chat/stream passed")
    return True


def test_invalid_session_and_validation() -> bool:
    """Test invalid session and request validation errors."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing invalid session + validation")
    logger.info("-" * 60)

    client, _ = build_client()

    invalid_session_response = client.post(
        "/api/chat",
        json = {
            "session_id": "missing-session",
            "message": "hello",
            "max_iterations": 10,
        },
    )
    assert invalid_session_response.status_code == 404

    session_id = client.post("/api/sessions").json()["session_id"]
    validation_response = client.post(
        "/api/chat",
        json = {
            "session_id": session_id,
            "message": "",
            "max_iterations": 10,
        },
    )
    assert validation_response.status_code == 422
    logger.info("✓ invalid session + validation passed")
    return True


def test_ttl_expiry() -> bool:
    """Test session expiry behavior by TTL."""
    logger.info("\n" + "-" * 60)
    logger.info("Testing session TTL expiry")
    logger.info("-" * 60)

    client, app = build_client()
    app.state.session_manager.ttl_seconds = 1

    session_id = client.post("/api/sessions").json()["session_id"]
    time.sleep(1.2)

    expired_response = client.post(
        "/api/chat",
        json = {
            "session_id": session_id,
            "message": "after expiry",
            "max_iterations": 10,
        },
    )
    assert expired_response.status_code == 404
    logger.info("✓ TTL expiry passed")
    return True


def main() -> int:
    """Run all web API tests."""
    tests = [
        test_health,
        test_create_and_delete_session,
        test_sync_chat,
        test_stream_chat,
        test_invalid_session_and_validation,
        test_ttl_expiry,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error("✗ %s failed: %s", test.__name__, exc)
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info("Web API Test Results: %s passed, %s failed", passed, failed)
    logger.info("=" * 80)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
