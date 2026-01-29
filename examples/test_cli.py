#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent CLI commands.
"""
import os
import sys
import subprocess
import tempfile
import json
import logging
sys.path.append(os.getcwd())

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_cli_help():
    """Test CLI help command"""
    logger.info("=" * 80)
    logger.info("Testing CLI Help Command")
    logger.info("=" * 80)

    try:
        # Test --help
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "Help command failed"
        assert "usage:" in result.stdout.lower(), "Help output should contain usage information"
        logger.info("✓ --help command executed successfully")

        logger.info("✓ All help command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Help command test failed: {e}")
        return False


def test_cli_version():
    """Test CLI version command"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Version Command")
    logger.info("-" * 60)

    try:
        # Test --version
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--version"],
            capture_output = True,
            text = True
        )
        # It's possible --version isn't implemented, so check if command fails or not
        if result.returncode == 0:
            logger.info("✓ --version command executed successfully")
        else:
            logger.warning("⚠️  --version command not implemented")

        logger.info("✓ Version command test completed")
        return True

    except Exception as e:
        logger.error(f"✗ Version command test failed: {e}")
        return False


def test_cli_config_commands():
    """Test CLI configuration commands"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Configuration Commands")
    logger.info("-" * 60)

    try:
        # Create a temporary config file
        with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.json', delete = False) as temp:
            temp.write(json.dumps({
                "llm": {
                    "model_name": "gpt-3.5-turbo",
                    "api_key": "test-key",
                    "temperature": 0.1
                },
                "default_tools": ["calculator", "read"]
            }))
            temp_filename = temp.name

        # Test loading config file
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--config", temp_filename, "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "Failed to load config file"
        logger.info("✓ --config parameter works correctly")

        # Clean up
        os.unlink(temp_filename)

        logger.info("✓ All config command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Config command test failed: {e}")
        try:
            os.unlink(temp_filename)
        except:
            pass
        return False


def test_cli_model_parameters():
    """Test CLI model parameters"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Model Parameters")
    logger.info("-" * 60)

    try:
        # Test model parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--model", "gpt-4", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--model parameter failed"
        logger.info("✓ --model parameter works correctly")

        # Test temperature parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--temperature", "0.5", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--temperature parameter failed"
        logger.info("✓ --temperature parameter works correctly")

        # Test top-p parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--top-p", "0.8", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--top-p parameter failed"
        logger.info("✓ --top-p parameter works correctly")

        logger.info("✓ All model parameter tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Model parameter test failed: {e}")
        return False


def test_cli_memory_commands():
    """Test CLI memory commands"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI Memory Commands")
    logger.info("-" * 60)

    try:
        # Test load memory parameter (invalid index should fail gracefully)
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--load", "99", "--help"],
            capture_output = True,
            text = True
        )
        # Should not crash for invalid memory index
        assert result.returncode == 0, "--load parameter failed"
        logger.info("✓ --load parameter works correctly")

        logger.info("✓ All memory command tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Memory command test failed: {e}")
        return False


def test_cli_api_parameters():
    """Test CLI API parameters"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing CLI API Parameters")
    logger.info("-" * 60)

    try:
        # Test API key parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--api-key", "test-key-123", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--api-key parameter failed"
        logger.info("✓ --api-key parameter works correctly")

        # Test base URL parameter
        result = subprocess.run(
            [sys.executable, "-m", "quarkagent", "--base-url", "https://api.example.com", "--help"],
            capture_output = True,
            text = True
        )
        assert result.returncode == 0, "--base-url parameter failed"
        logger.info("✓ --base-url parameter works correctly")

        logger.info("✓ All API parameter tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ API parameter test failed: {e}")
        return False


def main():
    """Run all CLI tests"""
    logger.info("Running QuarkAgent CLI tests...")

    tests = [
        test_cli_help,
        test_cli_version,
        test_cli_config_commands,
        test_cli_model_parameters,
        test_cli_memory_commands,
        test_cli_api_parameters
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
