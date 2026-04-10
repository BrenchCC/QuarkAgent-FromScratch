import os
import sys
import logging

from typing import Any, Callable, Dict, List, Optional

from tenacity import retry, stop_after_attempt, wait_random_exponential

sys.path.append(os.getcwd())

from quarkagent.agent.constants import LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def execute_tool(
    agent: Any,
    tool_call: Dict[str, Any],
    tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
) -> Any:
    """
    Execute one parsed tool call for the current agent.

    Args:
        agent: Agent instance that owns the runtime tools.
        tool_call: Parsed tool call payload.
        tool_callback: Optional callback for tool execution lifecycle events.

    Returns:
        Tool execution result.
    """
    tool_name = tool_call["name"]
    tool_args = tool_call["arguments"]

    logger.info("Executing tool: %s with arguments: %s", tool_name, tool_args)

    tool_definition = None
    for candidate in agent.tools:
        if candidate["name"] == tool_name:
            tool_definition = candidate
            break

    if tool_definition:
        try:
            result = tool_definition["executor"](**tool_args)
            logger.info("Tool %s executed successfully", tool_name)
        except Exception as exc:
            error_message = f"Error executing tool {tool_name}: {str(exc)}"
            logger.error(error_message)
            result = {"error": error_message}
    else:
        from quarkagent.tools import execute_tool as execute_registered_tool

        result = execute_registered_tool(tool_name, **tool_args)

    if tool_callback:
        tool_callback("status", tool_name, {"arguments": tool_args})
        tool_callback("end", tool_name, {"result": result})

    return result


@retry(stop = stop_after_attempt(3), wait = wait_random_exponential(min = 1, max = 60))
def call_llm(agent: Any, messages: List[Dict[str, str]]) -> str:
    """
    Call the configured LLM client for the current agent.

    Args:
        agent: Agent instance with model and client configuration.
        messages: Runtime conversation messages.

    Returns:
        LLM response content string.
    """
    logger.debug("Calling LLM with %s messages", len(messages))

    try:
        response = agent.client.chat.completions.create(
            model = agent.model,
            messages = messages,
            temperature = agent.temperature,
            top_p = agent.top_p,
        )
        content = response.choices[0].message.content or ""
        logger.debug("LLM response received: %s...", content[:100])
        return content
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        raise


def is_stop_requested(stop_callback: Optional[Callable[[], bool]]) -> bool:
    """
    Safely evaluate whether the current run should stop.

    Args:
        stop_callback: Optional callback that returns `True` when stopping is requested.

    Returns:
        Whether stop has been requested.
    """
    if not stop_callback:
        return False

    try:
        return bool(stop_callback())
    except Exception as exc:
        logger.warning("Stop callback failed: %s", exc)
        return False


def build_stop_response(
    stop_message: str,
    status_callback: Optional[Callable[[str], None]] = None
) -> str:
    """
    Build the normalized stop response text for the current run.

    Args:
        stop_message: Stop response message returned to the caller.
        status_callback: Optional callback for stop status updates.

    Returns:
        Normalized stop message text.
    """
    if status_callback:
        status_callback("Stop requested. Ending session...")
    return stop_message


def run_with_tools(
    agent: Any,
    query: str,
    max_iterations: int = 10,
    tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
    status_callback: Optional[Callable[[str], None]] = None,
    stop_callback: Optional[Callable[[], bool]] = None
) -> str:
    """
    Execute one agent run with formatted tool-calling support.

    Args:
        agent: Agent instance coordinating the run.
        query: Current user query text.
        max_iterations: Maximum number of tool-execution iterations.
        tool_callback: Optional callback for tool execution events.
        status_callback: Optional callback for status text updates.
        stop_callback: Optional callback that stops the run at safe boundaries.

    Returns:
        Final response text.
    """
    logger.info("Starting run_with_tools with query: %s", query)

    messages = [
        {"role": "system", "content": agent._build_runtime_system_prompt(query)},
        {"role": "user", "content": query},
    ]
    agent._active_stop_callback = stop_callback

    try:
        for iteration in range(max_iterations):
            logger.debug("Iteration %s/%s", iteration + 1, max_iterations)

            if agent._is_stop_requested(stop_callback):
                return agent._build_stop_response(status_callback)

            if status_callback:
                status_callback(f"Thinking... (Iteration {iteration + 1})")

            try:
                content = agent._call_llm(messages)
            except Exception as exc:
                error_message = f"Failed to get LLM response: {str(exc)}"
                logger.error(error_message)
                return error_message

            if agent._is_stop_requested(stop_callback):
                return agent._build_stop_response(status_callback)

            tool_call = agent._parse_tool_call(content)
            if not tool_call:
                logger.info("Run completed without tool calls")

                if agent._is_stop_requested(stop_callback):
                    return agent._build_stop_response(status_callback)

                if agent.use_reflector and agent.reflector:
                    if agent._is_stop_requested(stop_callback):
                        return agent._build_stop_response(status_callback)
                    if status_callback:
                        status_callback("Improving response...")
                    content = agent.reflector.enhance_response(query, content)

                return content

            tool_name = tool_call["name"]
            logger.info("Tool call detected: %s", tool_name)

            if agent._is_stop_requested(stop_callback):
                return agent._build_stop_response(status_callback)

            if status_callback:
                status_callback(f"Executing {tool_name}...")

            result = agent._execute_tool(tool_call, tool_callback)
            tool_response = f"Tool {tool_name} returned: {result}"
            logger.debug("Tool response: %s...", tool_response[:100])

            messages.append({"role": "assistant", "content": content})
            messages.append({"role": "user", "content": tool_response})
    finally:
        agent._active_stop_callback = None

    error_message = "Reached maximum iterations without completing the task"
    logger.error(error_message)
    return error_message
