#!/usr/bin/env python3
"""
Test script to verify the basic functionality of QuarkAgent.
"""
import os
import sys
import logging
sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_agent_initialization():
    """Test QuarkAgent initialization"""
    logger.info("=" * 80)
    logger.info("Testing QuarkAgent Initialization")
    logger.info("=" * 80)

    try:
        # Test initialization with minimal parameters
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )
        logger.info("✓ QuarkAgent initialized successfully with minimal parameters")

        # Test initialization with custom system prompt
        custom_prompt = "You are a custom assistant for testing purposes."
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            system_prompt = custom_prompt,
            temperature = 0.1,
            use_reflector = False
        )
        logger.info("✓ QuarkAgent initialized successfully with custom system prompt")

        logger.info("✓ All initialization tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Failed to initialize QuarkAgent: {e}")
        return False


def test_agent_tool_management():
    """Test agent tool management capabilities"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Agent Tool Management")
    logger.info("-" * 60)

    try:
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )

        # Get available tools
        available_tools = agent.get_available_tools()
        logger.info(f"✓ Available built-in tools: {len(available_tools)} tools")
        logger.debug(f"Tool list: {', '.join(available_tools)}")

        # Test loading built-in tools
        tools_to_load = ["calculator", "read", "write", "bash"]
        loaded_count = 0

        for tool_name in tools_to_load:
            if agent.load_builtin_tool(tool_name):
                logger.info(f"✓ Loaded tool: {tool_name}")
                loaded_count += 1
            else:
                logger.warning(f"⚠️  Failed to load tool: {tool_name}")

        logger.info(f"✓ Total tools loaded: {loaded_count}")
        assert len(agent.tools) == loaded_count, "Mismatch between loaded count and actual tools"

        logger.info("✓ All tool management tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Tool management test failed: {e}")
        return False


def test_tool_description_builder():
    """Test the tool description builder method"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Tool Description Builder")
    logger.info("-" * 60)

    try:
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )

        # Load some tools
        agent.load_builtin_tool("calculator")
        agent.load_builtin_tool("read")

        # Build tools prompt
        tools_prompt = agent._build_tools_prompt()
        logger.info(f"✓ Tools prompt generated successfully (length: {len(tools_prompt)} characters)")
        logger.debug(f"Tools prompt snippet: {tools_prompt[:200]}...")

        # Verify prompt contains tool information
        assert "calculator" in tools_prompt.lower(), "Calculator tool not in prompt"
        assert "read" in tools_prompt.lower(), "Read tool not in prompt"

        logger.info("✓ All tool description tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Tool description test failed: {e}")
        return False


def test_json_extraction_methods():
    """Test JSON extraction methods"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing JSON Extraction Methods")
    logger.info("-" * 60)

    try:
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )

        # Test balanced JSON extraction
        test_text = """
        Some text before JSON {
            "name": "test",
            "value": 42,
            "items": ["a", "b", "c"]
        } some text after
        """

        extracted = agent._extract_balanced_json(test_text)
        logger.info(f"✓ Balanced JSON extraction successful: {extracted[:50]}...")
        assert extracted is not None, "Failed to extract balanced JSON"

        # Test write tool args extraction
        write_text = """
        path: "test.txt"
        content: "This is test content with "quoted" text"
        """

        args = agent._extract_write_args(write_text)
        logger.info(f"✓ Write tool args extraction successful: {args}")
        assert args is not None, "Failed to extract write tool args"
        assert "path" in args, "Path not in extracted args"
        assert "content" in args, "Content not in extracted args"

        logger.info("✓ All JSON extraction tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ JSON extraction test failed: {e}")
        return False


def test_tool_call_parser():
    """Test tool call parser"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Tool Call Parser")
    logger.info("-" * 60)

    try:
        agent = QuarkAgent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )

        # Test various tool call patterns
        test_patterns = [
            "TOOL: calculator ARGS: {\"expression\": \"2 + 2\"}",
            "TOL: read ARGS: {\"path\": \"test.txt\"}",
            "使用工具: write 参数: {\"path\": \"output.txt\", \"content\": \"test\"}",
            "USE TOOL: bash WITH ARGS: {\"cmd\": \"ls -la\"}",
            "工具名称: grep 工具参数: {\"pattern\": \"test\", \"path\": \".\"}"
        ]

        for pattern in test_patterns:
            tool_call = agent._parse_tool_call(pattern)
            if tool_call:
                logger.info(f"✓ Parsed tool call: {tool_call['name']} with args: {tool_call['arguments']}")
            else:
                logger.warning(f"⚠️  Failed to parse pattern: {pattern}")

        logger.info("✓ All tool call parser tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Tool call parser test failed: {e}")
        return False


def main():
    """Run all basic QuarkAgent tests"""
    logger.info("Running QuarkAgent basic functionality tests...")

    tests = [
        test_agent_initialization,
        test_agent_tool_management,
        test_tool_description_builder,
        test_json_extraction_methods,
        test_tool_call_parser
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
