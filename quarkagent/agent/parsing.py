import os
import re
import sys
import json
import logging

from typing import Any, Dict, Optional

sys.path.append(os.getcwd())

from quarkagent.agent.constants import LOGGER_NAME
from quarkagent.utils import parse_json

logger = logging.getLogger(LOGGER_NAME)

TOOL_NAME_PATTERNS = [
    r"TOOL:\s*(\w+)\s*ARGS:\s*",
    r"TOL:\s*(\w+)\s*ARGS:\s*",
    r"使用工具:\s*(\w+)\s*参数:\s*",
    r"USE TOOL:\s*(\w+)\s*WITH ARGS:\s*",
    r"工具名称:\s*(\w+)\s*工具参数:\s*",
    r"Tool:\s*(\w+)\s*Args:\s*",
    r"Tool:\s*(\w+)\s*Arguments:\s*",
]


def extract_string_value(text: str, quote_char: str) -> Optional[str]:
    """
    Extract a string value while preserving escaped characters.

    Args:
        text: Remaining text that starts after the opening quote.
        quote_char: Quote character used to close the string.

    Returns:
        Extracted string value when successful, otherwise `None`.
    """
    result = []
    index = 0
    text_length = len(text)

    while index < text_length:
        char = text[index]

        if char == "\\":
            if index + 1 < text_length:
                next_char = text[index + 1]
                if next_char == quote_char:
                    result.append(quote_char)
                    index += 2
                elif next_char == "\\":
                    result.append("\\")
                    index += 2
                elif next_char == "n":
                    result.append("\n")
                    index += 2
                elif next_char == "t":
                    result.append("\t")
                    index += 2
                else:
                    result.append(char)
                    result.append(next_char)
                    index += 2
            else:
                result.append(char)
                index += 1
        elif char == quote_char:
            return "".join(result)
        else:
            result.append(char)
            index += 1

    return None


def extract_write_args(text: str) -> Optional[Dict[str, Any]]:
    """
    Extract write-tool arguments from loosely formatted tool call text.

    Args:
        text: Text containing write tool arguments.

    Returns:
        Parsed write tool arguments when successful, otherwise `None`.
    """
    path_match = re.search(r'["\']path["\']\s*:\s*["\']([^"\']+)["\']', text)
    if not path_match:
        return None

    path = path_match.group(1)
    content_match = re.search(r'["\']content["\']\s*:\s*["\']', text)
    if not content_match:
        return None

    content_start = content_match.end()
    quote_char = text[content_start - 1]
    content = extract_string_value(text[content_start:], quote_char)

    if content is None:
        return None

    return {"path": path, "content": content}


def extract_balanced_json(text: str) -> Optional[str]:
    """
    Extract the last complete JSON object from mixed free-form text.

    Args:
        text: Text that may contain JSON content.

    Returns:
        Extracted JSON string when successful, otherwise `None`.
    """
    start = text.find("{")
    if start == -1:
        return None

    brace_count = 0
    in_string = False
    escape_next = False
    end = -1
    index = start

    while index < len(text):
        char = text[index]

        if escape_next:
            escape_next = False
            index += 1
            continue

        if char == "\\":
            escape_next = True
            index += 1
            continue

        if char in ('"', "'"):
            in_string = not in_string
            index += 1
            continue

        if not in_string:
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    end = index
                    temp_index = index + 1
                    temp_brace_count = 0
                    temp_in_string = False
                    temp_escape_next = False

                    while temp_index < len(text):
                        temp_char = text[temp_index]

                        if temp_escape_next:
                            temp_escape_next = False
                            temp_index += 1
                            continue

                        if temp_char == "\\":
                            temp_escape_next = True
                            temp_index += 1
                            continue

                        if temp_char in ('"', "'"):
                            temp_in_string = not temp_in_string
                            temp_index += 1
                            continue

                        if not temp_in_string:
                            if temp_char == "{":
                                temp_brace_count += 1
                            elif temp_char == "}":
                                temp_brace_count -= 1
                                if temp_brace_count == 0:
                                    end = temp_index
                        temp_index += 1
                    break
        index += 1

    if end != -1:
        return text[start:end + 1]

    logger.error("Failed to extract balanced JSON from text: %s...", text[:100])
    return None


def parse_tool_call(content: str) -> Optional[Dict[str, Any]]:
    """
    Parse a tool call from model output content.

    Args:
        content: LLM response content.

    Returns:
        Tool call dictionary when a supported pattern is found, otherwise `None`.
    """
    logger.debug("Parsing tool call from content (length=%s)", len(content))

    for pattern in TOOL_NAME_PATTERNS:
        match = re.search(pattern, content, re.DOTALL)
        if not match:
            continue

        tool_name = match.group(1)
        remaining = content[match.end():]

        if tool_name == "write":
            args = extract_write_args(remaining)
            if args:
                logger.info("Parsed write tool call with path: %s", args.get("path", "unknown"))
                return {"name": tool_name, "arguments": args}

        args_str = extract_balanced_json(remaining)
        if not args_str:
            continue

        logger.debug("Matched tool '%s', args length=%s", tool_name, len(args_str))

        try:
            return {
                "name": tool_name,
                "arguments": json.loads(args_str),
            }
        except json.JSONDecodeError as exc:
            logger.debug("Strict JSON parse failed: %s", exc)

        args = parse_json(args_str)
        if args:
            logger.info("Parsed tool call: %s with %s args", tool_name, len(args))
            return {
                "name": tool_name,
                "arguments": args,
            }

        logger.warning("Failed to parse tool arguments for %s: %s...", tool_name, args_str[:100])

    logger.debug("No tool call pattern matched")
    return None
