#!/usr/bin/env python3
"""
Test script to verify the functionality of QuarkAgent built-in tools.
"""
import os
import sys
import tempfile
import logging
sys.path.append(os.getcwd())

from quarkagent.tools import get_registered_tools, get_tool, execute_tool
from quarkagent.tools.basic_tools import (
    read_file,
    write_file,
    edit_file,
    list_dir,
    bash_command
)
from quarkagent.tools.caculator import calculator
from quarkagent.tools.code_tools import (
    search_by_pattern,
    search_by_regex,
    get_file_content,
    write_new_file,
    update_file_content,
    view_files,
    run_command
)

# Configure logging
logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


def test_tool_registration():
    """Test tool registration system"""
    logger.info("=" * 80)
    logger.info("Testing Tool Registration System")
    logger.info("=" * 80)

    try:
        registered_tools = get_registered_tools()
        logger.info(f"✓ Number of registered tools: {len(registered_tools)}")
        logger.debug(f"Registered tools: {list(registered_tools.keys())}")

        assert len(registered_tools) > 0, "No tools registered"

        # Test getting tools by name
        test_tool_names = ["read", "write", "bash", "calculator", "grep", "glob"]
        for tool_name in test_tool_names:
            tool = get_tool(tool_name)
            if tool:
                logger.info(f"✓ Tool '{tool_name}' found in registered tools")
            else:
                logger.warning(f"⚠️  Tool '{tool_name}' not found")

        logger.info("✓ All tool registration tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Tool registration test failed: {e}")
        return False


def test_calculator_tool():
    """Test calculator tool"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Calculator Tool")
    logger.info("-" * 60)

    try:
        # Test basic arithmetic
        test_cases = [
            ("2 + 2", 4),
            ("3 * 4", 12),
            ("10 - 5", 5),
            ("100 / 4", 25),
            ("2^3", 8),
            ("sqrt(16)", 4)
        ]

        for expression, expected in test_cases:
            result = calculator(expression = expression)
            logger.info(f"✓ {expression} = {result}")
            # Allow for floating point precision issues
            assert abs(float(result) - expected) < 0.001, f"Calculation error: {expression} should be {expected}, got {result}"

        logger.info("✓ All calculator tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Calculator tool test failed: {e}")
        return False


def test_file_operations_tools():
    """Test file operation tools"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing File Operation Tools")
    logger.info("-" * 60)

    try:
        # Create a temporary file for testing
        with tempfile.NamedTemporaryFile(mode = 'w', suffix = '.txt', delete = False) as temp:
            temp_filename = temp.name
            temp.write("Test content for file operations")

        # Test read file
        content = read_file(path = temp_filename)
        logger.info(f"✓ Read file successful: {content.strip()}")

        # Test write file
        test_content = "Updated content from write tool"
        write_file(path = temp_filename, content = test_content)
        updated_content = read_file(path = temp_filename)
        assert updated_content.strip() == test_content, "Write tool failed to update file"
        logger.info("✓ Write file successful")

        # Test edit file
        edit_file(path = temp_filename, old_str = test_content, new_str = "Edited content")
        edited_content = read_file(path = temp_filename)
        assert "Edited content" in edited_content, "Edit tool failed"
        logger.info("✓ Edit file successful")

        # Clean up
        os.unlink(temp_filename)

        logger.info("✓ All file operation tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ File operation tool test failed: {e}")
        # Clean up temp file if it exists
        try:
            os.unlink(temp_filename)
        except:
            pass
        return False


def test_bash_tool():
    """Test bash command tool"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Bash Command Tool")
    logger.info("-" * 60)

    try:
        # Test simple command
        result = bash_command(cmd = "echo 'Hello World'")
        logger.info(f"✓ Bash command successful: {result}")
        assert "Hello World" in str(result), "Bash command failed"

        # Test command with exit code
        result = bash_command(cmd = "ls -la")
        logger.info("✓ ls command executed successfully")

        logger.info("✓ All bash tool tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Bash tool test failed: {e}")
        return False


def test_directory_listing():
    """Test directory listing tool"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Directory Listing Tool")
    logger.info("-" * 60)

    try:
        # List current directory
        result = list_dir(path = ".")
        logger.info(f"✓ Directory listing successful: {len(result)} items")
        assert len(result) > 0, "Directory listing returned no items"

        logger.info("✓ Directory listing tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Directory listing test failed: {e}")
        return False


def test_code_tools():
    """Test code tools"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Code Tools")
    logger.info("-" * 60)

    try:
        # Test search by pattern (looking for test files)
        pattern = "test_"
        files = search_by_pattern(pattern = pattern, path = ".")
        logger.info(f"✓ Found {len(files)} files matching pattern '{pattern}'")
        assert len(files) > 0, "Search by pattern failed"

        # Test search by regex
        regex = r"test.*\.py$"
        matches = search_by_regex(pattern = regex, path = ".")
        logger.info(f"✓ Found {len(matches)} files matching regex '{regex}'")
        assert len(matches) > 0, "Search by regex failed"

        logger.info("✓ All code tool tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Code tool test failed: {e}")
        return False


def test_execute_tool_function():
    """Test the general execute_tool function"""
    logger.info("\n" + "-" * 60)
    logger.info("Testing Execute Tool Function")
    logger.info("-" * 60)

    try:
        # Test calculator via execute_tool
        result = execute_tool("calculator", expression = "2 + 2")
        logger.info(f"✓ Execute tool - calculator: {result}")
        assert abs(float(result) - 4) < 0.001, "Execute tool failed for calculator"

        logger.info("✓ Execute tool function tests passed")
        return True

    except Exception as e:
        logger.error(f"✗ Execute tool function test failed: {e}")
        return False


def main():
    """Run all tool tests"""
    logger.info("Running QuarkAgent tool functionality tests...")

    tests = [
        test_tool_registration,
        test_calculator_tool,
        test_file_operations_tools,
        test_bash_tool,
        test_directory_listing,
        test_code_tools,
        test_execute_tool_function
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
