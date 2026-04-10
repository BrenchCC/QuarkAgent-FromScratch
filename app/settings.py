import os
import logging

from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

load_dotenv()


def _parse_csv_items(csv_text: str) -> List[str]:
    """
    Parse comma-separated string into normalized list.

    Args:
        csv_text: Comma-separated input text.

    Returns:
        List of stripped non-empty items.
    """
    return [item.strip() for item in csv_text.split(",") if item.strip()]


def _parse_bool_flag(
    env_name: str,
    default: bool
) -> bool:
    """
    Parse a boolean flag from environment variables.

    Args:
        env_name: Environment variable name.
        default: Default value if the variable is unset.

    Returns:
        Parsed boolean flag.
    """
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


def _resolve_model_name(default: str = "gpt-3.5-turbo") -> str:
    """
    Resolve the web model name from supported environment variables.

    Args:
        default: Fallback model name if no variable is set.

    Returns:
        Resolved model name.
    """
    explicit_model = os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_NAME")
    return explicit_model or default


def _load_model_identifier() -> str:
    """
    Load the optional display identifier for the configured model.

    Args:
        None.

    Returns:
        Display identifier string or an empty string.
    """
    return os.getenv("LLM_IDENTIFIER", "").strip()


@dataclass
class AppSettings:
    """Application settings for the web API service."""

    app_name: str = "QuarkAgent Web API"
    app_version: str = "0.1.0"
    host: str = field(default_factory = lambda: os.getenv("WEB_HOST", "0.0.0.0"))
    port: int = field(default_factory = lambda: int(os.getenv("WEB_PORT", "8000")))
    cors_origins: List[str] = field(
        default_factory = lambda: _parse_csv_items(
            os.getenv("WEB_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
        )
    )
    session_ttl_seconds: int = field(default_factory = lambda: int(os.getenv("WEB_SESSION_TTL_SECONDS", "1800")))
    max_iterations: int = field(default_factory = lambda: int(os.getenv("WEB_MAX_ITERATIONS", "10")))
    llm_model: str = field(default_factory = lambda: _resolve_model_name("gpt-3.5-turbo"))
    llm_identifier: str = field(default_factory = _load_model_identifier)
    llm_api_key: str = field(default_factory = lambda: os.getenv("LLM_API_KEY", ""))
    llm_api_base: str = field(default_factory = lambda: os.getenv("LLM_API_BASE", "https://api.openai.com/v1"))
    llm_temperature: float = field(default_factory = lambda: float(os.getenv("WEB_LLM_TEMPERATURE", "0.3")))
    llm_top_p: float = field(default_factory = lambda: float(os.getenv("WEB_LLM_TOP_P", "0.9")))
    use_reflector: bool = field(default_factory = lambda: os.getenv("WEB_USE_REFLECTOR", "false").lower() == "true")
    default_tools: List[str] = field(default_factory = lambda: _parse_csv_items(os.getenv("WEB_DEFAULT_TOOLS", "")))
    skills_root_dir: str = field(default_factory = lambda: os.getenv("WEB_SKILLS_ROOT_DIR", "skills"))
    system_skills_dir: str = field(default_factory = lambda: os.getenv("WEB_SYSTEM_SKILLS_DIR", "skills/system"))
    custom_skills_dir: str = field(default_factory = lambda: os.getenv("WEB_CUSTOM_SKILLS_DIR", "skills/custom"))
    default_system_skills: List[str] = field(default_factory = lambda: _parse_csv_items(os.getenv("WEB_DEFAULT_SYSTEM_SKILLS", "")))
    enable_system_skills: bool = field(default_factory = lambda: _parse_bool_flag("WEB_ENABLE_SYSTEM_SKILLS", True))
    enable_custom_skill_tool: bool = field(default_factory = lambda: _parse_bool_flag("WEB_ENABLE_CUSTOM_SKILL_TOOL", True))
    enable_subagent_tool: bool = field(default_factory = lambda: _parse_bool_flag("WEB_ENABLE_SUBAGENT_TOOL", True))
    subagent_max_iterations: int = field(default_factory = lambda: int(os.getenv("WEB_SUBAGENT_MAX_ITERATIONS", "5")))


def load_settings() -> AppSettings:
    """
    Load application settings from environment variables.

    Args:
        None.

    Returns:
        Loaded AppSettings instance.
    """
    settings = AppSettings()
    logger.info(
        "Loaded web settings: host=%s port=%s ttl=%s",
        settings.host,
        settings.port,
        settings.session_ttl_seconds,
    )
    return settings
