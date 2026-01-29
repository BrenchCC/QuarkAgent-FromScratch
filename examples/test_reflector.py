#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent Reflector.
"""
import os
import sys
import logging
sys.path.append(os.getcwd())

from quarkagent.utils.reflector import Reflector

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_reflector_initialization():
    """Test Reflector initialization"""
    logger.info("=" * 80)
    logger.info("Testing Reflector Initialization")
    logger.info("=" * 80)

    try:
        # Test basic initialization
        reflector = Reflector()
        logger.info("✓ Reflector initialized successfully without parameters")
        assert not reflector.disabled, "Reflector should not be disabled by default"

        # Test initialization with configuration
        config = {
            "temperature": 0.5,
            "max_tokens": 1000,
            "disabled": False
        }
        reflector = Reflector(config = config)
        logger.info(f"✓ Reflector initialized with config: temperature={reflector.temperature}, max_tokens={reflector.max_tokens}")
        assert reflector.temperature == 0.5, "Temperature not set from config"
        assert reflector.max_tokens == 1000, "Max tokens not set from config"
        assert not reflector.disabled, "Reflector should not be disabled"

        # Test disabled reflector
        disabled_config = {"disabled": True}
        reflector = Reflector(config = disabled_config)
        logger.info("✓ Disabled reflector initialized")
        assert reflector.disabled, "Reflector should be disabled"

        logger.info("✓ All initialization tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Reflector initialization test failed: {e}")
        return False


def test_reflection_disabled_behavior():
    """Test reflector behavior when disabled"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Reflector Disabled Behavior")
    logger.info("-" * 60)

    try:
        reflector = Reflector(config = {"disabled": True})

        # Test apply_reflection
        messages = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"}
        ]
        result = reflector.apply_reflection(messages)
        assert result == messages, "Disabled reflector should return messages unchanged"
        logger.info("✓ apply_reflection returns messages unchanged when disabled")

        # Test reflect method
        query = "What's the capital of France?"
        response = "Paris is the capital of France."
        result = reflector.reflect(query, response)
        assert result == response, "Disabled reflector should return response unchanged"
        logger.info("✓ reflect returns response unchanged when disabled")

        logger.info("✓ All disabled reflector tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Disabled reflector test failed: {e}")
        return False


def test_reflection_message_processing():
    """Test reflection message processing"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Reflection Message Processing")
    logger.info("-" * 60)

    try:
        reflector = Reflector()

        # Test with too few messages
        empty_messages = []
        result = reflector.apply_reflection(empty_messages)
        assert result == empty_messages, "Empty messages should be returned unchanged"

        single_message = [{"role": "user", "content": "Hello"}]
        result = reflector.apply_reflection(single_message)
        assert result == single_message, "Single message should be returned unchanged"

        logger.info("✓ Messages with insufficient context returned unchanged")

        # Test valid conversation
        conversation = [
            {"role": "user", "content": "What's the capital of France?"},
            {"role": "assistant", "content": "Paris is the capital of France."}
        ]
        result = reflector.apply_reflection(conversation)
        logger.info("✓ Valid conversation processed successfully")

        logger.info("✓ All message processing tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Reflection message processing test failed: {e}")
        return False


def test_reflection_prompt_generation():
    """Test reflection prompt generation"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Reflection Prompt Generation")
    logger.info("-" * 60)

    try:
        reflector = Reflector()

        query = "What's the capital of France?"
        response = "Paris is the capital of France."

        prompt = reflector._build_reflection_prompt(query, response)
        logger.info(f"✓ Prompt generated successfully (length: {len(prompt)} characters)")
        logger.debug(f"Prompt snippet: {prompt[:200]}...")

        assert query in prompt, "Query not in prompt"
        assert response in prompt, "Response not in prompt"
        assert "evaluate" in prompt.lower(), "Prompt should contain evaluation instructions"
        assert "improved" in prompt.lower(), "Prompt should contain improvement instructions"

        logger.info("✓ Reflection prompt contains all necessary elements")

        logger.info("✓ All prompt generation tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Reflection prompt generation test failed: {e}")
        return False


def test_response_extraction():
    """Test improved response extraction"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Response Extraction")
    logger.info("-" * 60)

    try:
        reflector = Reflector()

        # Test with clear improved response section
        reflection_content = """
The response is accurate but could be more detailed.

Improved Response:
Paris is the capital and most populous city of France. It is located in the north-central part of the country and serves as the political, cultural, and economic center of France.
        """.strip()

        improved = reflector._extract_improved_response(reflection_content)
        logger.info(f"✓ Extracted improved response: {improved[:50]}...")
        assert "capital and most populous city" in improved, "Failed to extract improved response"

        # Test without clear section
        simple_content = "The response is good, no improvement needed."
        extracted = reflector._extract_improved_response(simple_content)
        assert extracted == simple_content, "Should return entire content if no section found"

        logger.info("✓ Response extraction works with various formats")

        logger.info("✓ All response extraction tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Response extraction test failed: {e}")
        return False


def test_reflector_configuration():
    """Test reflector configuration handling"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Reflector Configuration")
    logger.info("-" * 60)

    try:
        config = {
            "temperature": 0.3,
            "max_tokens": 500,
            "disabled": False
        }
        reflector = Reflector(config = config)

        assert reflector.temperature == 0.3, "Temperature not configured"
        assert reflector.max_tokens == 500, "Max tokens not configured"
        assert not reflector.disabled, "Should not be disabled"
        logger.info(f"✓ Reflector configured with temperature={reflector.temperature}, max_tokens={reflector.max_tokens}")

        # Test default values
        default_reflector = Reflector()
        assert default_reflector.temperature == 0.7, "Default temperature should be 0.7"
        assert default_reflector.max_tokens is None, "Default max tokens should be None"
        assert not default_reflector.disabled, "Default should be enabled"
        logger.info("✓ Default configuration correctly set")

        logger.info("✓ All configuration tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Reflector configuration test failed: {e}")
        return False


def main():
    """Run all reflector tests"""
    logger.info("Running QuarkAgent Reflector tests...")

    tests = [
        test_reflector_initialization,
        test_reflection_disabled_behavior,
        test_reflection_message_processing,
        test_reflection_prompt_generation,
        test_response_extraction,
        test_reflector_configuration
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
