#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent configuration system.
"""
import os
import sys
import tempfile
import json
import logging
sys.path.append(os.getcwd())

from quarkagent.config import load_config, save_config, AgentConfig, LLMConfig

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_default_config():
    """Test default configuration"""
    logger.info("=" * 80)
    logger.info("Testing Default Configuration")
    logger.info("=" * 80)

    try:
        # Load default config
        config = load_config()
        logger.info("✓ Default configuration loaded successfully")

        # Verify LLM config has default values
        assert isinstance(config.llm, LLMConfig), "LLM config should be instance of LLMConfig"
        assert config.llm.model_name == "gpt-3.5-turbo", f"Default model should be gpt-3.5-turbo, got {config.llm.model_name}"
        assert config.llm.temperature == 0.7, f"Default temperature should be 0.7, got {config.llm.temperature}"
        assert config.llm.top_p == 0.9, f"Default top_p should be 0.9, got {config.llm.top_p}"
        logger.info("✓ LLM default configuration correct")

        # Verify agent config
        assert isinstance(config, AgentConfig), "Config should be instance of AgentConfig"
        assert len(config.default_tools) == 0, f"Default tools should be empty, got {len(config.default_tools)}"
        assert config.enable_reflection is False, f"Reflection should be disabled by default, got {config.enable_reflection}"
        logger.info("✓ Agent default configuration correct")

        logger.info("✓ All default configuration tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Default configuration test failed: {e}")
        return False


def test_config_save_load():
    """Test config save and load functionality"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Configuration Save and Load")
    logger.info("-" * 60)

    try:
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.json', delete = False) as temp:
            temp_filename = temp.name

        # Create and save custom config
        config = AgentConfig()
        config.llm.model_name = "gpt-4"
        config.llm.temperature = 0.3
        config.llm.top_p = 0.8
        config.default_tools = ["read", "write", "calculator"]
        config.enable_reflection = True

        save_success = save_config(config, temp_filename)
        assert save_success, "Failed to save configuration"
        logger.info("✓ Configuration saved successfully")

        # Load saved config
        loaded_config = load_config(temp_filename)
        logger.info("✓ Configuration loaded successfully")

        # Verify loaded config matches saved config
        assert loaded_config.llm.model_name == "gpt-4", "Model name mismatch"
        assert loaded_config.llm.temperature == 0.3, "Temperature mismatch"
        assert loaded_config.llm.top_p == 0.8, "Top_p mismatch"
        assert loaded_config.default_tools == ["read", "write", "calculator"], "Default tools mismatch"
        assert loaded_config.enable_reflection is True, "Reflection flag mismatch"
        logger.info("✓ Loaded configuration matches saved configuration")

        # Clean up
        os.unlink(temp_filename)

        logger.info("✓ All save/load tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Config save/load test failed: {e}")
        try:
            os.unlink(temp_filename)
        except:
            pass
        return False


def test_env_variable_loading():
    """Test environment variable loading"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Environment Variable Loading")
    logger.info("-" * 60)

    try:
        # Set test environment variables
        os.environ["LLM_API_KEY"] = "test_api_key"
        os.environ["LLM_MODEL"] = "test-model-123"
        os.environ["LLM_API_BASE"] = "https://api.example.com"
        os.environ["LLM_TEMPERATURE"] = "0.5"

        # Load config with environment variables
        config = load_config()
        logger.info("✓ Config loaded with environment variables")

        # Verify environment variables are picked up
        assert config.llm.api_key == "test_api_key", "API key not loaded from environment"
        assert config.llm.model_name == "test-model-123", "Model name not loaded from environment"
        assert config.llm.api_base == "https://api.example.com", "API base not loaded from environment"
        logger.info("✓ Environment variables correctly loaded")

        # Clean up
        del os.environ["LLM_API_KEY"]
        del os.environ["LLM_MODEL"]
        del os.environ["LLM_API_BASE"]
        del os.environ["LLM_TEMPERATURE"]

        logger.info("✓ All environment variable tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Environment variable test failed: {e}")
        # Clean up even if test fails
        for key in ["LLM_API_KEY", "LLM_MODEL", "LLM_API_BASE", "LLM_TEMPERATURE"]:
            if key in os.environ:
                del os.environ[key]
        return False


def test_api_base_model_inference():
    """Test API base to model inference"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing API Base to Model Inference")
    logger.info("-" * 60)

    try:
        # Test different API base URLs
        test_cases = [
            ("https://api.openai.com/v1", "gpt-3.5-turbo"),
            ("https://api.deepseek.com", "deepseek-chat"),
            ("https://api.anthropic.com", "claude-3-sonnet-20240229"),
            ("https://azure.openai.com", "gpt-3.5-turbo")  # Default since no deployment name
        ]

        for api_base, expected_model in test_cases:
            os.environ["LLM_API_BASE"] = api_base
            config = load_config()
            if "azure" in api_base.lower() and "AZURE_OPENAI_DEPLOYMENT_NAME" not in os.environ:
                assert config.llm.model_name == "gpt-3.5-turbo", f"Azure default model should be gpt-3.5-turbo"
            else:
                assert config.llm.model_name == expected_model, \
                    f"Expected model {expected_model} for API base {api_base}, got {config.llm.model_name}"
            logger.info(f"✓ API base {api_base} correctly inferred model {config.llm.model_name}")

        # Clean up
        del os.environ["LLM_API_BASE"]

        logger.info("✓ All API base inference tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ API base inference test failed: {e}")
        if "LLM_API_BASE" in os.environ:
            del os.environ["LLM_API_BASE"]
        return False


def test_config_from_file():
    """Test loading config from file"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Configuration from File")
    logger.info("-" * 60)

    try:
        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.json', delete = False) as temp:
            temp.write(json.dumps({
                "llm": {
                    "model_name": "custom-model",
                    "api_key": "file-api-key",
                    "api_base": "https://custom.api",
                    "temperature": 0.2,
                    "top_p": 0.7
                },
                "default_tools": ["bash", "grep", "calculator"],
                "enable_reflection": True,
                "reflection_max_iterations": 5
            }))
            temp_filename = temp.name

        # Load from file
        config = load_config(temp_filename)
        logger.info("✓ Config loaded from file successfully")

        # Verify config
        assert config.llm.model_name == "custom-model", "Model name not from file"
        assert config.llm.api_key == "file-api-key", "API key not from file"
        assert config.llm.api_base == "https://custom.api", "API base not from file"
        assert config.llm.temperature == 0.2, "Temperature not from file"
        assert config.llm.top_p == 0.7, "Top_p not from file"
        assert config.default_tools == ["bash", "grep", "calculator"], "Default tools not from file"
        assert config.enable_reflection is True, "Reflection flag not from file"
        assert config.reflection_max_iterations == 5, "Reflection iterations not from file"

        logger.info("✓ All file config tests passed")

        # Clean up
        os.unlink(temp_filename)

        return True

    except Exception as e:
        logger.error(f"✗ Config from file test failed: {e}")
        try:
            os.unlink(temp_filename)
        except:
            pass
        return False


def main():
    """Run all config tests"""
    logger.info("Running QuarkAgent configuration system tests...")

    tests = [
        test_default_config,
        test_config_save_load,
        test_env_variable_loading,
        test_api_base_model_inference,
        test_config_from_file
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            logger.error(f"✗ Test failed with exception: {e}")
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info(f"Test Results: {passed} passed, {failed} failed")
    logger.info("=" * 80)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
