import os
import sys
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.getcwd())

from app.settings import load_settings
from app.agent_service import AgentService
from app.session_manager import SessionManager
from app.routes.chat import router as chat_router
from app.routes.system import router as system_router

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        None.

    Returns:
        Configured FastAPI application.
    """
    settings = load_settings()

    app = FastAPI(
        title = settings.app_name,
        version = settings.app_version,
        description = "Web API for QuarkAgent with REST + SSE chat interfaces.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins = settings.cors_origins,
        allow_credentials = True,
        allow_methods = ["*"],
        allow_headers = ["*"],
    )

    app.state.settings = settings
    app.state.session_manager = SessionManager(ttl_seconds = settings.session_ttl_seconds)
    app.state.agent_service = AgentService(settings = settings)

    app.include_router(system_router, prefix = "/api", tags = ["system"])
    app.include_router(chat_router, prefix = "/api", tags = ["chat"])

    logger.info("FastAPI app initialized")
    return app


app = create_app()
