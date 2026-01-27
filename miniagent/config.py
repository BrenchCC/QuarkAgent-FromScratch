import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List

from dotenv import load_dotenv
from dataclasses import dataclass, field

logger = logging.getLogger("MiniAgent_Config")

load_dotenv()


@dataclass
class LLMConfig:
    """LLM Configuration"""
    model_name: str = field(default_factory = lambda: os.getenv("LLM_MODEL_NAME", "gpt-3.5-turbo"))
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
    system_prompt: str = "You are a helpful AI assistant call MiniAgent, created by Brench."
    default_tools: List[str] = field(default_factory = list)
    enable_reflection: bool = False
    reflection_system_prompt: Optional[str] = None
    reflection_max_iterations: int = 3


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
    env_model = os.environ.get("LLM_MODEL")
    if env_model:
        config.llm.model_name = env_model

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


def save_config(config: AgentConfig, config_path: str) -> bool:
    """
    Save configuration to file

    Args:
        config: Agent configuration object
        config_path: Configuration file path

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
            "system_prompt": config.system_prompt,
            "default_tools": config.default_tools,
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
