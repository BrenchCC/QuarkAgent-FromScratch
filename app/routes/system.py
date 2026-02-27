import os
import sys

from datetime import datetime, timezone

from fastapi import APIRouter, Request

sys.path.append(os.getcwd())

from app.schemas import HealthResponse, ToolListResponse

router = APIRouter()


@router.get("/health", response_model = HealthResponse)
def health(request: Request) -> HealthResponse:
    """
    Return API health status.

    Args:
        request: FastAPI request object.

    Returns:
        Health response payload.
    """
    settings = request.app.state.settings
    return HealthResponse(
        status = "ok",
        app_name = settings.app_name,
        version = settings.app_version,
        timestamp = datetime.now(timezone.utc).isoformat(),
    )


@router.get("/tools", response_model = ToolListResponse)
def tools(request: Request) -> ToolListResponse:
    """
    Return registered tool names.

    Args:
        request: FastAPI request object.

    Returns:
        Tool list payload.
    """
    service = request.app.state.agent_service
    return ToolListResponse(tools = service.get_available_tools())
