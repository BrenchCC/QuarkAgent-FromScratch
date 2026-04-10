#!/usr/bin/env python3
"""
Test script to verify QuarkAgent subagent functionality.
"""
import os
import sys
import json
import logging
import shutil
import tempfile

from contextlib import contextmanager

sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent
from quarkagent.subagent import build_subagent_tool

logging.basicConfig(
    level = logging.INFO,
    format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers = [logging.StreamHandler()]
)

logger = logging.getLogger(__name__)


@contextmanager
def temporary_memory_home():
    """
    Run one subagent test with an isolated QUARKAGENT_HOME directory.

    Args:
        None.

    Yields:
        Temporary directory path used as QUARKAGENT_HOME.
    """
    original_home = os.environ.get("QUARKAGENT_HOME")
    temp_dir = tempfile.mkdtemp(prefix = "quarkagent-subagent-memory-")
    os.environ["QUARKAGENT_HOME"] = temp_dir

    try:
        yield temp_dir
    finally:
        if original_home is None:
            os.environ.pop("QUARKAGENT_HOME", None)
        else:
            os.environ["QUARKAGENT_HOME"] = original_home
        shutil.rmtree(temp_dir, ignore_errors = True)


def clear_proxy_environment() -> dict:
    """
    Temporarily remove proxy variables from the current process environment.

    Args:
        None.

    Returns:
        Dictionary of removed environment variables and their original values.
    """
    removed_values = {}
    proxy_keys = [
        "http_proxy",
        "https_proxy",
        "all_proxy",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
    ]

    for key in proxy_keys:
        if key in os.environ:
            removed_values[key] = os.environ.pop(key)

    return removed_values


def restore_environment(saved_values: dict) -> None:
    """
    Restore environment variables from a saved dictionary.

    Args:
        saved_values: Environment variable values keyed by variable name.

    Returns:
        None.
    """
    for key, value in saved_values.items():
        os.environ[key] = value


def create_test_agent(**kwargs) -> QuarkAgent:
    """
    Build a test agent while temporarily disabling proxy environment variables.

    Args:
        **kwargs: Keyword arguments forwarded to `QuarkAgent`.

    Returns:
        Initialized `QuarkAgent` instance.
    """
    removed_proxy_values = clear_proxy_environment()

    try:
        return QuarkAgent(**kwargs)
    finally:
        restore_environment(removed_proxy_values)


def test_subagent_tool_registration() -> bool:
    """
    Test that the subagent tool can be attached to a parent agent.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("=" * 80)
    logger.info("Testing Subagent Tool Registration")
    logger.info("=" * 80)

    try:
        agent = create_test_agent(
            model = "gpt-3.5-turbo",
            api_key = "dummy_key",
            temperature = 0.1,
            use_reflector = False
        )
        agent.load_builtin_tool("calculator")
        agent.add_tool(build_subagent_tool(agent, default_max_iterations = 3))

        tool_names = [tool["name"] for tool in agent.tools]
        assert "subagent" in tool_names, "Subagent tool was not added"

        tools_prompt = agent._build_tools_prompt()
        assert "subagent" in tools_prompt.lower(), "Subagent tool missing from tools prompt"

        logger.info("✓ Subagent tool registration passed")
        return True
    except Exception as e:
        logger.error(f"✗ Subagent registration test failed: {e}")
        return False


def test_subagent_execution() -> bool:
    """
    Test that the delegated child agent can execute a focused tool task.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Subagent Execution")
    logger.info("-" * 60)

    original_call_llm = QuarkAgent._call_llm
    responses = [
        'TOOL: calculator ARGS: {"expression": "2 + 2"}',
        "The delegated result is 4.",
    ]

    def fake_call_llm(self, messages):
        """
        Return deterministic child-agent outputs for testing.

        Args:
            self: Current QuarkAgent instance.
            messages: Current conversation messages.

        Returns:
            Next canned model response.
        """
        del self
        del messages
        return responses.pop(0)

    try:
        QuarkAgent._call_llm = fake_call_llm

        with temporary_memory_home() as temp_home:
            agent = create_test_agent(
                model = "gpt-3.5-turbo",
                api_key = "dummy_key",
                temperature = 0.1,
                use_reflector = False
            )
            agent.agent_scope = "main"
            agent.memory_path = os.path.join(temp_home, "memory", "main", "main_test.json")
            agent.load_builtin_tool("calculator")
            agent.add_tool(build_subagent_tool(agent, default_max_iterations = 3))

            subagent_tool = next(tool for tool in agent.tools if tool["name"] == "subagent")
            result = subagent_tool["executor"](
                task = "Compute 2 + 2 and return the result.",
                tools = ["calculator"],
                max_iterations = 3,
            )

            assert result["status"] == "ok", f"Unexpected subagent status: {result}"
            assert result["task_id"].startswith("task_"), f"Unexpected task_id format: {result}"
            assert result["tools"] == ["calculator"], f"Unexpected delegated tools: {result}"
            assert result["answer"] == "The delegated result is 4.", f"Unexpected subagent answer: {result}"

            subagent_dir = os.path.join(temp_home, "memory", "subagent")
            subagent_files = sorted(os.listdir(subagent_dir))
            assert len(subagent_files) == 1, f"Expected one subagent log file, got {subagent_files}"

            payload_path = os.path.join(subagent_dir, subagent_files[0])
            with open(payload_path, "r", encoding = "utf-8") as f:
                payload = json.loads(f.read())
            assert payload["agent_scope"] == "subagent", "Subagent payload missing scope marker"
            assert payload["task_id"] == result["task_id"], "Subagent payload task_id should match tool result"
            assert isinstance(payload["system_prompt"], str) and payload["system_prompt"].strip(), \
                "Subagent payload missing system prompt"
            assert "{tools_prompt}" not in payload["system_prompt"], "Subagent payload should persist resolved prompt"
            assert "calculator" in payload["system_prompt"], "Resolved subagent prompt should mention delegated tools"
            assert payload["tools"] == ["calculator"], "Subagent payload missing delegated tools list"
            assert isinstance(payload["skills"], list), "Subagent payload missing skills list"
            assert payload["facts"]["parent_agent_scope"] == "main", "Subagent payload missing parent scope"
            assert payload["facts"]["parent_memory_path"] == agent.memory_path, "Parent memory path was not persisted"
            assert payload["facts"]["delegated_task"] == "Compute 2 + 2 and return the result.", \
                "Delegated task was not persisted"
            assert payload["messages"][0]["role"] == "user", "Subagent log should start with delegated query"
            assert payload["messages"][-1]["content"] == "The delegated result is 4.", \
                "Subagent log should persist the delegated answer"

        logger.info("✓ Subagent execution passed")
        return True
    except Exception as e:
        logger.error(f"✗ Subagent execution test failed: {e}")
        return False
    finally:
        QuarkAgent._call_llm = original_call_llm


def test_subagent_stop_propagation() -> bool:
    """
    Test that the child agent respects the parent stop callback.

    Args:
        None.

    Returns:
        Whether the test passed.
    """
    logger.info("\n" + "-" * 60)
    logger.info("Testing Subagent Stop Propagation")
    logger.info("-" * 60)

    try:
        with temporary_memory_home():
            agent = create_test_agent(
                model = "gpt-3.5-turbo",
                api_key = "dummy_key",
                temperature = 0.1,
                use_reflector = False
            )
            agent.load_builtin_tool("calculator")
            agent.add_tool(build_subagent_tool(agent, default_max_iterations = 3))
            agent._active_stop_callback = lambda: True

            subagent_tool = next(tool for tool in agent.tools if tool["name"] == "subagent")
            result = subagent_tool["executor"](task = "Any delegated task is fine.")

            assert result["status"] == "stopped", f"Unexpected stop result: {result}"
            assert result["answer"] == agent.STOP_MESSAGE, f"Unexpected stop message: {result}"

        logger.info("✓ Subagent stop propagation passed")
        return True
    except Exception as e:
        logger.error(f"✗ Subagent stop propagation test failed: {e}")
        return False
    finally:
        if "agent" in locals():
            agent._active_stop_callback = None


def main() -> int:
    """
    Run all subagent tests.

    Args:
        None.

    Returns:
        Process exit code.
    """
    tests = [
        test_subagent_tool_registration,
        test_subagent_execution,
        test_subagent_stop_propagation,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
        except Exception as exc:
            logger.error("✗ %s failed: %s", test.__name__, exc)
            failed += 1

    logger.info("\n" + "=" * 80)
    logger.info("Subagent Test Results: %s passed, %s failed", passed, failed)
    logger.info("=" * 80)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
