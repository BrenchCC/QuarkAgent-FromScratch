import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from dataclasses import dataclass, field

logger = logging.getLogger("QuarkAgent_Config")

load_dotenv()


def _parse_csv_items(csv_text: str) -> List[str]:
    """
    Parse a comma-separated string into a normalized list.

    Args:
        csv_text: Comma-separated string value.

    Returns:
        List of stripped non-empty items.
    """
    return [item.strip() for item in csv_text.split(",") if item.strip()]


def _parse_bool_env(
    env_name: str,
    default: bool
) -> bool:
    """
    Parse a boolean environment variable with a default fallback.

    Args:
        env_name: Environment variable name.
        default: Default value when the variable is not set.

    Returns:
        Parsed boolean value.
    """
    raw_value = os.getenv(env_name)
    if raw_value is None:
        return default
    return raw_value.lower() in {"1", "true", "yes", "on"}


def _resolve_model_name(default: Optional[str] = "gpt-3.5-turbo") -> Optional[str]:
    """
    Resolve model name from supported environment variables.

    Args:
        default: Fallback model name if no environment variable is set.

    Returns:
        Resolved model name or the provided default.
    """
    explicit_model = os.getenv("LLM_MODEL") or os.getenv("LLM_MODEL_NAME")
    return explicit_model or default


def _load_model_identifier() -> Optional[str]:
    """
    Load the optional display identifier for the configured model.

    Args:
        None.

    Returns:
        Model identifier if configured, otherwise `None`.
    """
    identifier = os.getenv("LLM_IDENTIFIER", "").strip()
    return identifier or None


@dataclass
class LLMConfig:
    """LLM Configuration"""
    model_name: str = field(default_factory = lambda: _resolve_model_name("gpt-3.5-turbo"))
    model_identifier: Optional[str] = field(default_factory = _load_model_identifier)
    api_key: str = field(default_factory = lambda: os.getenv("LLM_API_KEY", ""))
    api_base: str = field(default_factory = lambda: os.getenv("LLM_API_BASE", "https://api.openai.com/v1"))
    organization: Optional[str] = None
    timeout: Optional[int] = 60
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    top_p: Optional[float] = 0.9
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None


@dataclass
class AgentConfig:
    """Agent configuration"""

    llm: LLMConfig = field(default_factory = LLMConfig)
    system_prompt: str = field(default_factory = lambda: _load_default_system_prompt())
    default_tools: List[str] = field(default_factory = list)
    skills_root_dir: str = field(default_factory = lambda: os.getenv("SKILLS_ROOT_DIR", "skills"))
    system_skills_dir: str = field(default_factory = lambda: os.getenv("SYSTEM_SKILLS_DIR", "skills/system"))
    custom_skills_dir: str = field(default_factory = lambda: os.getenv("CUSTOM_SKILLS_DIR", "skills/custom"))
    default_system_skills: List[str] = field(default_factory = lambda: _parse_csv_items(os.getenv("DEFAULT_SYSTEM_SKILLS", "")))
    enable_system_skills: bool = field(default_factory = lambda: _parse_bool_env("ENABLE_SYSTEM_SKILLS", True))
    enable_custom_skill_tool: bool = field(default_factory = lambda: _parse_bool_env("ENABLE_CUSTOM_SKILL_TOOL", True))
    enable_subagent_tool: bool = field(default_factory = lambda: _parse_bool_env("ENABLE_SUBAGENT_TOOL", True))
    subagent_max_iterations: int = field(default_factory = lambda: int(os.getenv("SUBAGENT_MAX_ITERATIONS", "5")))
    enable_reflection: bool = False
    reflection_system_prompt: Optional[str] = None
    reflection_max_iterations: int = 5


def _load_default_system_prompt() -> str:
    """Load default system prompt from prompts/system_prompt.md"""
    prompt_path = Path(__file__).parent.parent / "prompts" / "system_prompt.md"
    try:
        if prompt_path.exists():
            with open(prompt_path, "r", encoding = "utf-8") as f:
                return f.read().strip()
        logger.warning(f"System prompt file not found at {prompt_path}, using default")
    except Exception as e:
        logger.error(f"Failed to load system prompt from {prompt_path}: {e}")

    # Fallback to default if file not found or error
    return "You are a helpful AI assistant call QuarkAgent, created by Brench."


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    Load agent configuration from a JSON file or use default values.

    Args:
        config_path (Optional[str]): Path to the configuration file. If None,
            looks for 'config.json' in the current directory.

    Returns:
        AgentConfig: Loaded agent configuration.
    """
    config = AgentConfig()

    # Try to get API key from environment variables with multiple fallbacks
    # Priority order: LLM_API_KEY > OPENAI_API_KEY > DEEPSEEK_API_KEY > ANTHROPIC_API_KEY > AZURE_OPENAI_API_KEY
    env_api_key = (
        os.environ.get("LLM_API_KEY") or
        os.environ.get("OPENAI_API_KEY") or
        os.environ.get("DEEPSEEK_API_KEY") or
        os.environ.get("ANTHROPIC_API_KEY") or
        os.environ.get("AZURE_OPENAI_API_KEY")
    )

    if env_api_key:
        config.llm.api_key = env_api_key

    # Try to get API base URL from environment variables with multiple fallbacks
    # Priority order: LLM_API_BASE > OPENAI_API_BASE > DEEPSEEK_API_BASE > ANTHROPIC_API_BASE > AZURE_OPENAI_ENDPOINT
    env_api_base = (
        os.environ.get("LLM_API_BASE") or
        os.environ.get("OPENAI_API_BASE") or
        os.environ.get("DEEPSEEK_API_BASE") or
        os.environ.get("ANTHROPIC_API_BASE") or
        os.environ.get("AZURE_OPENAI_ENDPOINT")
    )

    if env_api_base:
        config.llm.api_base = env_api_base

    # Try to get organization from environment variables
    env_organization = os.environ.get("LLM_ORGANIZATION") or os.environ.get("OPENAI_ORGANIZATION")
    if env_organization:
        config.llm.organization = env_organization

    # Try to get model from environment variables
    env_model = _resolve_model_name(None)
    if env_model:
        config.llm.model_name = env_model

    env_model_identifier = _load_model_identifier()
    if env_model_identifier:
        config.llm.model_identifier = env_model_identifier

    # Determine likely provider based on API_BASE and set appropriate default model
    if config.llm.api_base:
        api_base_lower = config.llm.api_base.lower()
        if "deepseek" in api_base_lower and not env_model:
            config.llm.model_name = "deepseek-chat"
        elif "anthropic" in api_base_lower and not env_model:
            config.llm.model_name = "claude-3-sonnet-20240229"
        elif "azure" in api_base_lower and not env_model:
            # Azure OpenAI requires deployment name instead of model name
            deployment_name = os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
            if deployment_name:
                config.llm.model_name = deployment_name

    # If no configuration file, return default configuration
    if not config_path:
        return config

    try:
        with open(config_path, "r", encoding = "utf-8") as f:
            config_data = json.load(f)

        # Load LLM configuration
        if "llm" in config_data:
            for key, value in config_data["llm"].items():
                if hasattr(config.llm, key):
                    setattr(config.llm, key, value)

        # Load agent configuration
        for key, value in config_data.items():
            if key != "llm" and hasattr(config, key):
                setattr(config, key, value)

        logger.info(f"Configuration loaded from {config_path}")
    except Exception as e:
        logger.error(f"Failed to load configuration from {config_path}: {e}")

    return config


def save_config(
    config: AgentConfig,
    config_path: str,
    system_prompt_override: Optional[str] = None,
    tools_override: Optional[List[str]] = None,
    skills_override: Optional[List[Dict[str, Any]]] = None
) -> bool:
    """
    Save configuration to file

    Args:
        config: Agent configuration object
        config_path: Configuration file path
        system_prompt_override: Optional resolved system prompt to persist in place
            of `config.system_prompt`
        tools_override: Optional resolved runtime tool list to persist
        skills_override: Optional resolved runtime skill payloads to persist

    Returns:
        Whether save was successful
    """
    try:
        # Convert dataclass to dictionary
        config_dict = {
            "llm": {
                key: value for key, value in config.llm.__dict__.items()
                if not key.startswith("_") and value is not None
            },
            "system_prompt": system_prompt_override if system_prompt_override is not None else config.system_prompt,
            "tools": tools_override if tools_override is not None else config.default_tools,
            "skills": skills_override if skills_override is not None else [],
            "default_tools": config.default_tools,
            "skills_root_dir": config.skills_root_dir,
            "system_skills_dir": config.system_skills_dir,
            "custom_skills_dir": config.custom_skills_dir,
            "default_system_skills": config.default_system_skills,
            "enable_system_skills": config.enable_system_skills,
            "enable_custom_skill_tool": config.enable_custom_skill_tool,
            "enable_subagent_tool": config.enable_subagent_tool,
            "subagent_max_iterations": config.subagent_max_iterations,
            "enable_reflection": config.enable_reflection,
            "reflection_system_prompt": config.reflection_system_prompt,
            "reflection_max_iterations": config.reflection_max_iterations
        }

        config_file = Path(config_path)
        config_file.parent.mkdir(parents = True, exist_ok = True)

        with open(config_file, "w", encoding = "utf-8") as f:
            json.dump(config_dict, f, indent = 2, ensure_ascii = False)

        logger.info(f"Configuration saved to: {config_path}")
        return True
    except Exception as e:
        logger.error(f"Failed to save configuration to '{config_path}': {str(e)}")
        return False
