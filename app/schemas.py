from typing import Any, Dict, List, Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    app_name: str
    version: str
    timestamp: str


class SessionCreateResponse(BaseModel):
    """Session creation response schema."""

    session_id: str
    created_at: str
    expires_at: str


class SessionDeleteResponse(BaseModel):
    """Session deletion response schema."""

    session_id: str
    deleted: bool


class SessionStopResponse(BaseModel):
    """Session stop response schema."""

    session_id: str
    stop_requested: bool


class ToolListResponse(BaseModel):
    """Tool list response schema."""

    tools: List[str]


class SkillInfo(BaseModel):
    """Skill metadata response schema."""

    name: str
    description: str
    namespace: str
    path: str
    enabled: bool


class SkillListResponse(BaseModel):
    """Skill list response schema."""

    skills: List[SkillInfo]


class ChatRequest(BaseModel):
    """Chat request schema."""

    session_id: str = Field(min_length = 1)
    message: str = Field(min_length = 1)
    max_iterations: int = Field(default = 10, ge = 1, le = 30)


class StreamEvent(BaseModel):
    """Streaming event payload schema."""

    type: Literal["status", "tool_start", "tool_end", "final", "error", "done"]
    timestamp: str
    data: Dict[str, Any] = Field(default_factory = dict)


class ChatResponse(BaseModel):
    """Synchronous chat response schema."""

    session_id: str
    answer: str
    events: List[StreamEvent]
    timestamp: str
