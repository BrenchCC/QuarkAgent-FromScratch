#!/usr/bin/env python3
"""
Test script to verify the web API functionality.
"""
import os
import sys
import json
import time
import logging
import shutil
import tempfile

from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

from fastapi.testclient import TestClient

sys.path.append(os.getcwd())

from app.settings import AppSettings
from app.agent_service import AgentService
from app.main import create_app

logging.basicConfig(
    level = logging.INFO,
    format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


class FakeAgentService:
    """Mock service for deterministic API testing."""

    def __init__(self):
        """
        Initialize fake service state.

        Args:
            None.
        """
        self.stop_requests: List[str] = []

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
        return ["read", "write", "bash", "calculator", "skills", "subagent"]

    def get_available_skills(self) -> List[Dict[str, Any]]:
        """
        Return fake skill metadata list.

        Args:
            None.

        Returns:
            List of fake skills.
        """
        return [
            {
                "name": "docx",
                "description": "Default docx skill",
                "namespace": "system",
                "path": "skills/system/docx",
                "enabled": True,
            },
            {
                "name": "demo-skill",
                "description": "Custom demo skill",
                "namespace": "custom",
                "path": "skills/custom/demo-skill",
                "enabled": False,
            },
        ]

    def run_sync(
        self,
        history: List[Dict[str, str]],
        message: str,
        max_iterations: int = 10,
        session_id: str = "",
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        Return fake synchronous answer and events.

        Args:
            history: Existing history list.
            message: Incoming user message.
            max_iterations: Maximum iterations.
            session_id: Session identifier.

        Returns:
            Tuple of answer and event list.
        """
        del history
        del max_iterations
        del session_id

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
        session_id: str = "",
    ) -> str:
        """
        Emit fake stream events then return final answer.

        Args:
            history: Existing history list.
            message: Incoming user message.
            emit_event: Event emitter callback.
            max_iterations: Maximum iterations.
            session_id: Session identifier.

        Returns:
            Final answer.
        """
        del history
        del max_iterations
        del session_id

        answer = f"echo: {message}"
        emit_event({"type": "status", "timestamp": self._utc_iso(), "data": {"message": "Thinking..."}})
        emit_event({"type": "tool_start", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "arguments": {"expression": "2+2"}}})
        emit_event({"type": "tool_end", "timestamp": self._utc_iso(), "data": {"tool": "calculator", "result": "4"}})
        emit_event({"type": "final", "timestamp": self._utc_iso(), "data": {"answer": answer}})
        return answer

    def request_stop(self, session_id: str) -> bool:
        """
        Record a stop request for the fake service.

        Args:
            session_id: Session identifier.

        Returns:
            Always returns `True`.
        """
        self.stop_requests.append(session_id)
        return True


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


def write_skill_file(
    root_dir: str,
    namespace: str,
    directory_name: str,
    display_name: str,
    description: str,
    body: str
) -> None:
    """
    Create one temporary skill file on disk.

    Args:
        root_dir: Temporary root directory.
        namespace: Skill namespace directory name.
        directory_name: Directory name used on disk.
        display_name: Skill display name.
        description: Skill description.
        body: Skill markdown content.

    Returns:
        None.
    """
    skill_dir = os.path.join(root_dir, namespace, directory_name)
    os.makedirs(skill_dir, exist_ok = True)

    skill_text = "\n".join(
        [
            "---",
            f"name: {display_name}",
            f"description: {description}",
            "---",
            "",
            body.strip(),
            "",
        ]
    )

    with open(os.path.join(skill_dir, "SKILL.md"), "w", encoding = "utf-8") as file_obj:
        file_obj.write(skill_text)


def build_real_skills_client() -> Tuple[TestClient, Any, str]:
    """
    Build a client backed by the real AgentService for local skill commands.

    Args:
        None.

    Returns:
        Tuple of client, app, and temporary skill root.
    """
    temp_root = tempfile.mkdtemp(prefix = "quarkagent-web-skills-")
    write_skill_file(
        temp_root,
        "system",
        "docx",
        "docx",
        "Default docx skill",
        "# DOCX\nAlways loaded.",
    )
    write_skill_file(
        temp_root,
        "custom",
        "demo-skill",
        "demo-skill",
        "Custom demo skill",
        "# Demo\nLoaded on demand.",
    )

    settings = AppSettings(
        llm_api_key = "",
        system_skills_dir = os.path.join(temp_root, "system"),
        custom_skills_dir = os.path.join(temp_root, "custom"),
        enable_system_skills = True,
        enable_custom_skill_tool = True,
    )

    app = create_app()
    app.state.settings = settings
    app.state.agent_service = AgentService(settings = settings)
    return TestClient(app), app, temp_root


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


def test_stop_session() -> bool:
    """
    Test explicit session stop endpoint.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing /api/sessions/{id}/stop")
    logger.info("-" * 60)

    client, app = build_client()
    session_id = client.post("/api/sessions").json()["session_id"]

    response = client.post(f"/api/sessions/{session_id}/stop")
    assert response.status_code == 200
    body = response.json()
    assert body["stop_requested"] is True
    assert session_id in app.state.agent_service.stop_requests

    logger.info("✓ /api/sessions/{id}/stop passed")
    return True


def test_system_metadata_endpoints() -> bool:
    """
    Test tool and skill metadata endpoints.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing /api/tools and /api/skills")
    logger.info("-" * 60)

    client, _ = build_client()

    tools_response = client.get("/api/tools")
    assert tools_response.status_code == 200
    tools_body = tools_response.json()
    assert "skills" in tools_body["tools"], "Dynamic skills tool missing from /api/tools"
    assert "subagent" in tools_body["tools"], "Dynamic subagent tool missing from /api/tools"

    skills_response = client.get("/api/skills")
    assert skills_response.status_code == 200
    skills_body = skills_response.json()
    assert len(skills_body["skills"]) == 2, f"Unexpected skill count: {skills_body}"
    assert any(item["namespace"] == "system" for item in skills_body["skills"]), "System skill missing"
    assert any(item["namespace"] == "custom" for item in skills_body["skills"]), "Custom skill missing"

    logger.info("✓ /api/tools and /api/skills passed")
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


def test_local_skill_commands_over_http() -> bool:
    """
    Test `/skills` local command handling over the web API.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing local /skills commands over HTTP")
    logger.info("-" * 60)

    client, _, temp_root = build_real_skills_client()

    try:
        session_id = client.post("/api/sessions").json()["session_id"]

        overview_response = client.post(
            "/api/chat",
            json = {
                "session_id": session_id,
                "message": "/skills",
                "max_iterations": 10,
            },
        )
        assert overview_response.status_code == 200
        overview_body = overview_response.json()
        assert "System Skills" in overview_body["answer"]
        assert "Custom Skills" in overview_body["answer"]

        detail_response = client.post(
            "/api/chat",
            json = {
                "session_id": session_id,
                "message": "/skills demo-skill",
                "max_iterations": 10,
            },
        )
        assert detail_response.status_code == 200
        detail_body = detail_response.json()
        assert "Load on demand" in detail_body["answer"]
        assert "demo-skill" in detail_body["answer"]

        logger.info("✓ local /skills commands over HTTP passed")
        return True
    finally:
        shutil.rmtree(temp_root)


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
        test_stop_session,
        test_system_metadata_endpoints,
        test_sync_chat,
        test_stream_chat,
        test_local_skill_commands_over_http,
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
