import os
import sys
import json
import logging
from typing import Any, Dict, List, Optional

sys.path.append(os.getcwd())
from miniagent.utils.json_util import truncate_message_content

logger = logging.getLogger("LLM Call Util")

def _parse_tool_arguments(arguments: Any) -> Dict[str, Any]:
    """
    Parse tool arguments from various formats

    Args:
        arguments: Raw arguments (string or dict)

    Returns:
        Parsed arguments dictionary
    """
    if isinstance(arguments, dict):
        return arguments

    if isinstance(arguments, str):
        try:
            from .json_util import parse_json
            return parse_json(arguments)
        except Exception:
            logger.warning(f"Failed to parse tool call arguments: {truncate_message_content(arguments)}")

    return {}

def _extract_from_openai_object(response: Any) -> List[Dict[str, Any]]:
    """
    Extract tool calls from OpenAI API response object

    Args:
        response: OpenAI API response object

    Returns:
        List of tool calls
    """
    tool_calls = []

    if not (hasattr(response, "choices") and hasattr(response.choices[0], "message")):
        return tool_calls

    message = response.choices[0].message
    if not (hasattr(message, "tool_calls") and message.tool_calls):
        return tool_calls

    for i, function_call in enumerate(message.tool_calls):
        if hasattr(function_call, "function"):
            args = _parse_tool_arguments(function_call.function.arguments)
            tool_calls.append({
                "id": f"call_{i}",
                "name": function_call.function.name,
                "arguments": args,
            })

    return tool_calls

def _extract_from_dict_response(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract tool calls from dictionary response (e.g., DeepSeek API)

    Args:
        response: Dictionary response

    Returns:
        List of tool calls
    """
    tool_calls = []

    if "choices" not in response:
        return tool_calls

    choices = response["choices"]
    if not (choices and isinstance(choices, list) and len(choices) > 0):
        return tool_calls

    message = choices[0].get("message", {})
    if "tool_calls" not in message or not message["tool_calls"]:
        return tool_calls

    for i, tc in enumerate(message["tool_calls"]):
        if isinstance(tc, dict) and "function" in tc:
            function_data = tc["function"]
            arguments = _parse_tool_arguments(function_data.get("arguments"))
            tool_calls.append({
                "id": tc.get("id", f"call_{i}"),
                "name": function_data.get("name", ""),
                "arguments": arguments,
            })

    return tool_calls

def _extract_from_string_response(response: str) -> List[Dict[str, Any]]:
    """
    Extract tool calls from JSON string response

    Args:
        response: JSON string response

    Returns:
        List of tool calls
    """
    tool_calls = []

    if not (response.strip().startswith("{") and response.strip().endswith("}")):
        return tool_calls

    try:
        data = json.loads(response)
        if "tool" in data and "parameters" in data:
            tool_calls.append({
                "id": "call_0",
                "name": data["tool"],
                "arguments": data["parameters"],
            })
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse tool call from response string: {truncate_message_content(response)}")

    return tool_calls

def extract_tool_calls(response: Any) -> List[Dict[str, Any]]:
    """
    Extract tool calls from LLM API response

    Args:
        response: LLM API response

    Returns:
        List of tool calls
    """
    if response is None:
        logger.info("Response is None, no tool calls to extract.")
        return []

    try:
        if hasattr(response, "choices"):
            return _extract_from_openai_object(response)

        if isinstance(response, dict):
            return _extract_from_dict_response(response)

        if isinstance(response, str):
            return _extract_from_string_response(response)

        logger.warning(f"Unknown response format: {truncate_message_content(str(response))}")
        return []

    except Exception as e:
        logger.error(f"Error extracting tool calls from response: {e}")
        return [] 