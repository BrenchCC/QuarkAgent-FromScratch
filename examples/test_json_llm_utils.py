#!/usr/bin/env python3
"""
Test script to verify the functionality of json_util and llm_util modules.
"""
import os
import sys
import json
import logging
sys.path.append(os.getcwd())
from quarkagent.utils.json_util import (
    extract_json_from_markdown,
    clean_json_string,
    parse_json,
    truncate_message_content,
    extract_content,
    extract_tool_calls,
    extract_tool_call,
    format_tool_response,
)
from quarkagent.utils.llm_util import (
    extract_tool_calls as llm_extract_tool_calls,
)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

def test_json_extraction():
    """Test JSON extraction from markdown"""
    print("Testing JSON extraction from markdown...")

    text = """
    Here's some JSON:
    ```json
    {"name": "test", "value": 42}
    ```
    """

    json_str, remaining = extract_json_from_markdown(text)
    print(f"Extracted JSON: {json_str}")
    assert json_str is not None, "Failed to extract JSON from markdown"

    parsed = parse_json(json_str)
    print(f"Parsed JSON: {parsed}")
    assert parsed["name"] == "test", "Failed to parse extracted JSON"

    print("✓ JSON extraction test passed")


def test_json_cleaning():
    """Test JSON cleaning functionality"""
    print("\nTesting JSON cleaning...")

    dirty_json = """
    {
        "name": "test", // This is a comment
        "value": 42,   /* Multi-line
                         comment */
        "items": [1, 2, 3],
    }
    """

    cleaned = clean_json_string(dirty_json)
    print(f"Cleaned JSON: {cleaned}")

    parsed = parse_json(cleaned)
    print(f"Parsed JSON: {parsed}")
    assert parsed["name"] == "test", "Failed to parse cleaned JSON"
    assert parsed["value"] == 42, "Failed to parse cleaned JSON"
    assert parsed["items"] == [1, 2, 3], "Failed to parse cleaned JSON"

    print("✓ JSON cleaning test passed")


def test_truncation():
    """Test message truncation"""
    print("\nTesting message truncation...")

    long_text = "A" * 200
    truncated = truncate_message_content(long_text, max_length=100)
    print(f"Truncated text: {truncated}")
    assert len(truncated) == 103, "Truncation failed"
    assert truncated.endswith("..."), "Truncation failed"

    short_text = "Short message"
    truncated = truncate_message_content(short_text)
    print(f"Short text remains: {truncated}")
    assert truncated == short_text, "Truncation of short text failed"

    print("✓ Truncation test passed")


def test_tool_call_extraction():
    """Test tool call extraction"""
    print("\nTesting tool call extraction...")

    # Test OpenAI style response
    class MockFunctionCall:
        def __init__(self, call_id, name, arguments):
            self.id = call_id
            self.function = type('', (), {
                'name': name,
                'arguments': json.dumps(arguments)
            })()

    class MockMessage:
        def __init__(self, content, tool_calls):
            self.content = content
            self.tool_calls = tool_calls

    class MockChoice:
        def __init__(self, message):
            self.message = message

    class MockResponse:
        def __init__(self, choices):
            self.choices = choices

    response = MockResponse([
        MockChoice(
            MockMessage(
                "Please use the calculator tool",
                [
                    MockFunctionCall("call_0", "calculator", {"expression": "2 + 2"}),
                    MockFunctionCall("call_1", "calculator", {"expression": "3 * 4"})
                ]
            )
        )
    ])

    tool_calls = extract_tool_calls(response)
    print(f"Extracted tool calls: {tool_calls}")
    assert len(tool_calls) == 2, "Failed to extract tool calls"
    assert tool_calls[0]["name"] == "calculator", "Failed to extract tool name"
    assert tool_calls[0]["arguments"]["expression"] == "2 + 2", "Failed to extract tool arguments"

    tool_call = extract_tool_call(response)
    print(f"Single tool call: {tool_call}")
    assert tool_call is not None, "Failed to extract single tool call"

    print("✓ Tool call extraction test passed")


def test_llm_util():
    """Test llm_util module functionality"""
    print("\nTesting llm_util module...")

    # Test llm_util's tool call extraction
    class MockFunctionCall:
        def __init__(self, name, arguments):
            self.function = type('', (), {
                'name': name,
                'arguments': json.dumps(arguments)
            })()

    class MockMessage:
        def __init__(self, content, tool_calls):
            self.content = content
            self.tool_calls = tool_calls

    class MockChoice:
        def __init__(self, message):
            self.message = message

    class MockResponse:
        def __init__(self, choices):
            self.choices = choices

    response = MockResponse([
        MockChoice(
            MockMessage(
                "Please use the calculator tool",
                [
                    MockFunctionCall("calculator", {"expression": "2 + 2"}),
                    MockFunctionCall("calculator", {"expression": "3 * 4"})
                ]
            )
        )
    ])

    llm_tool_calls = llm_extract_tool_calls(response)
    print(f"LLM util extracted tool calls: {llm_tool_calls}")
    assert len(llm_tool_calls) == 2, "LLM util failed to extract tool calls"
    assert llm_tool_calls[0]["name"] == "calculator", "LLM util failed to extract tool name"
    assert llm_tool_calls[0]["arguments"]["expression"] == "2 + 2", "LLM util failed to extract tool arguments"

    print("✓ llm_util test passed")


def test_formatting():
    """Test tool response formatting"""
    print("\nTesting tool response formatting...")

    tool_call = {
        "id": "call_0",
        "name": "calculator",
        "arguments": {"expression": "2 + 2"}
    }

    response = 4
    formatted = format_tool_response(tool_call, response)
    print(f"Formatted response: {formatted}")
    assert formatted["name"] == "calculator", "Failed to format tool response"
    assert formatted["content"] == "4", "Failed to format tool response"

    complex_response = {"result": 4, "steps": ["2 + 2 = 4"]}
    formatted = format_tool_response(tool_call, complex_response)
    print(f"Complex formatted response: {formatted}")
    assert "result" in formatted["content"], "Failed to format complex response"

    print("✓ Tool response formatting test passed")


def main():
    """Run all tests"""
    print("Running JSON utility tests...")
    print("=" * 50)

    test_json_extraction()
    test_json_cleaning()
    test_truncation()
    test_tool_call_extraction()
    test_llm_util()
    test_formatting()

    print("\n" + "=" * 50)
    print("All tests passed! ✓")


if __name__ == "__main__":
    main()
