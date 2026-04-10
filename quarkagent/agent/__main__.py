import os
import sys
import logging

from typing import Optional

from dotenv import load_dotenv

sys.path.append(os.getcwd())

from quarkagent.agent import QuarkAgent

logger = logging.getLogger(__name__)


def test_agent() -> bool:
    """
    Run a small local smoke test for the agent package entrypoint.

    Args:
        None.

    Returns:
        Whether the smoke test succeeded.
    """
    logger.info("Starting QuarkAgent test...")
    logger.info("\nTest 1: Initializing QuarkAgent")

    try:
        api_key = os.getenv("LLM_API_KEY") or "dummy_key"
        base_url: Optional[str] = os.getenv("LLM_BASE_URL")
        model = os.getenv("LLM_MODEL")

        if api_key == "dummy_key":
            logger.warning("OPENAI_API_KEY not found in .env file, using dummy key")

        agent = QuarkAgent(
            model = model,
            api_key = api_key,
            base_url = base_url,
            temperature = 0.7,
            use_reflector = False,
        )
        logger.info("✅ QuarkAgent initialized successfully")
    except Exception as exc:
        logger.error("❌ Failed to initialize QuarkAgent: %s", exc)
        return False

    logger.info("\nTest 2: Checking available built-in tools")
    try:
        available_tools = agent.get_available_tools()
        logger.info("✅ Available tools: %s", ", ".join(available_tools))
        logger.info("✅ Number of available tools: %s", len(available_tools))
    except Exception as exc:
        logger.error("❌ Failed to get available tools: %s", exc)
        return False

    logger.info("\nTest 3: Loading built-in tools")
    try:
        tools_to_load = ["read", "write", "bash", "calculator"]
        loaded_count = 0

        for tool_name in tools_to_load:
            if agent.load_builtin_tool(tool_name):
                logger.info("✅ Loaded tool: %s", tool_name)
                loaded_count += 1
            else:
                logger.warning("⚠️ Failed to load tool: %s", tool_name)

        logger.info("✅ Total tools loaded: %s", loaded_count)
    except Exception as exc:
        logger.error("❌ Failed to load built-in tools: %s", exc)
        return False

    logger.info("\nTest 4: Verifying tools are loaded")
    try:
        logger.info("✅ Number of tools in agent: %s", len(agent.tools))
        for tool in agent.tools:
            logger.info("  - Tool: %s", tool["name"])
            logger.debug("    Description: %s", tool["description"])

        if agent.tools:
            logger.info("✅ Tools loaded successfully")
        else:
            logger.warning("⚠️ No tools were loaded")
    except Exception as exc:
        logger.error("❌ Failed to verify loaded tools: %s", exc)
        return False

    logger.info("\n🎉 All tests completed successfully!")
    return True


if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(
        level = logging.INFO,
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers = [logging.StreamHandler()],
    )
    raise SystemExit(0 if test_agent() else 1)
