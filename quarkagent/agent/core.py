import os
import sys
import logging

from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

sys.path.append(os.getcwd())

from quarkagent.utils import Reflector
from quarkagent.skills import SkillDefinition, SkillManager
from quarkagent.tools import get_registered_tools, get_tool, get_tool_description

from quarkagent.agent.runtime import call_llm, execute_tool, is_stop_requested, build_stop_response, run_with_tools
from quarkagent.agent.constants import DEFAULT_SYSTEM_PROMPT_FILE, LOGGER_NAME, STOP_MESSAGE
from quarkagent.agent.prompting import (
    load_system_prompt,
    build_tools_prompt,
    build_memory_context,
    build_system_skills_prompt,
    build_runtime_system_prompt,
)
from quarkagent.agent.parsing import (
    parse_tool_call,
    extract_write_args,
    extract_string_value,
    extract_balanced_json,
)

logger = logging.getLogger(LOGGER_NAME)


class QuarkAgent:
    """
    Main runtime class for QuarkAgent.
    """

    STOP_MESSAGE = STOP_MESSAGE

    def __init__(
        self,
        model: str,
        api_key: str,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        top_p: float = 0.9,
        system_prompt: Optional[str] = None,
        system_prompt_file: Optional[str] = DEFAULT_SYSTEM_PROMPT_FILE,
        system_skills: Optional[List[SkillDefinition]] = None,
        skill_manager: Optional[SkillManager] = None,
        model_identifier: Optional[str] = None,
        use_reflector: bool = False,
        memory_context_provider: Optional[Callable[[Optional[str]], str]] = None,
        **kwargs: Any
    ):
        """
        Initialize one QuarkAgent instance.

        Args:
            model: LLM model name.
            api_key: API key for the LLM service.
            base_url: Base URL for the LLM service.
            temperature: Temperature used for model sampling.
            top_p: Top-p value used for model sampling.
            system_prompt: Inline system prompt content.
            system_prompt_file: Optional prompt file path.
            system_skills: Default-loaded system skills.
            skill_manager: Shared skill manager for custom skills.
            model_identifier: Optional display name for the configured model.
            use_reflector: Whether response reflection should be enabled.
            memory_context_provider: Optional callable that renders memory context.
            **kwargs: Additional keyword arguments reserved for future extensions.
        """
        del kwargs

        self.model = model
        self.model_identifier = model_identifier or None
        self.api_key = api_key
        self.base_url = base_url
        self.temperature = temperature
        self.top_p = top_p

        self.base_system_prompt = load_system_prompt(system_prompt, system_prompt_file)
        self.system_prompt = self.base_system_prompt
        self.tools: List[Dict[str, Any]] = []
        self.client: Optional[OpenAI] = None
        self.system_skills = system_skills or []
        self.skill_manager = skill_manager
        self.agent_scope = "main"
        self.memory_path: Optional[str] = None
        self._active_stop_callback: Optional[Callable[[], bool]] = None
        self.use_reflector = use_reflector
        self.memory_context_provider = memory_context_provider
        self.reflector: Optional[Reflector] = None

        self._init_llm_client()

        if self.use_reflector:
            self.reflector = Reflector(self.client, self.model)

        logger.info(
            "QuarkAgent initialized with model %s, model_identifier %s, temperature %s, "
            "top_p %s, system_prompt %s, use_reflector %s",
            self.model,
            self.model_identifier,
            self.temperature,
            self.top_p,
            self.system_prompt,
            self.use_reflector,
        )

    def _init_llm_client(self) -> None:
        """
        Initialize the OpenAI-compatible client used by the agent.

        Args:
            None.

        Returns:
            None.
        """
        logger.info("Default to use OpenAI client")
        try:
            self.client = OpenAI(
                api_key = self.api_key,
                base_url = self.base_url,
            )
            logger.info("OpenAI client initialized with model: %s", self.model)
        except ImportError:
            logger.error("OpenAI package not installed. Please install it with 'pip install openai'")
            raise
        except Exception as exc:
            logger.error("Failed to initialize OpenAI client: %s", exc)
            raise

    def add_tool(self, tool: Dict[str, Any]) -> None:
        """
        Add one runtime tool definition to the agent.

        Args:
            tool: Tool definition containing name, description, and executor.

        Returns:
            None.
        """
        if not isinstance(tool, dict):
            raise TypeError("Tool must be a dictionary type")

        required_keys = ["name", "description", "executor"]
        for key in required_keys:
            if key not in tool:
                raise ValueError(f"Tool is missing a required field: {key}")

        self.tools.append(tool)
        logger.debug("Added tool for QuarkAgent: %s", tool["name"])

    def load_builtin_tool(self, tool_name: str) -> bool:
        """
        Load one built-in tool by name.

        Args:
            tool_name: Built-in tool name to load.

        Returns:
            Whether the tool was loaded successfully.
        """
        tool_item = get_tool(tool_name)
        if not tool_item:
            logger.warning("Built-in tool not found: %s", tool_name)
            return False

        tool_description = get_tool_description(tool_item)
        tool = {
            "name": tool_description["name"],
            "description": tool_description["description"],
            "parameters": tool_description.get("parameters", {}),
            "executor": tool_item,
        }
        self.add_tool(tool)
        logger.info("Loaded built-in tool: %s", tool_name)
        return True

    def get_available_tools(self) -> List[str]:
        """
        Return all registered built-in tool names.

        Args:
            None.

        Returns:
            List of tool names.
        """
        return list(get_registered_tools().keys())

    def _build_tools_prompt(self) -> str:
        """
        Build the tools prompt block for the current agent tools.

        Args:
            None.

        Returns:
            Tools prompt string.
        """
        return build_tools_prompt(self.tools)

    def _build_system_skills_prompt(self) -> str:
        """
        Build the system skills prompt block for the current agent.

        Args:
            None.

        Returns:
            System skills prompt string.
        """
        return build_system_skills_prompt(self.system_skills)

    def _build_runtime_system_prompt(self, query: str) -> str:
        """
        Build the final runtime system prompt for one user turn.

        Args:
            query: Current user query.

        Returns:
            Fully rendered runtime system prompt.
        """
        return build_runtime_system_prompt(
            base_system_prompt = self.base_system_prompt,
            tools = self.tools,
            system_skills = self.system_skills,
            skill_manager = self.skill_manager,
            memory_context_provider = self.memory_context_provider,
            query = query,
        )

    def _build_memory_context(self, query: Optional[str]) -> str:
        """
        Render dynamic memory context for the current query.

        Args:
            query: Current user query string.

        Returns:
            Rendered memory context string.
        """
        return build_memory_context(self.memory_context_provider, query)

    def build_runtime_snapshot_prompt(self) -> str:
        """
        Build a prompt preview suitable for config and memory snapshots.

        Args:
            None.

        Returns:
            Resolved runtime prompt preview string.
        """
        return self._build_runtime_system_prompt("")

    def _extract_string_value(self, text: str, quote_char: str) -> Optional[str]:
        """
        Extract a quoted string value from free-form text.

        Args:
            text: Remaining text after the opening quote.
            quote_char: Quote character used by the value.

        Returns:
            Extracted string when successful, otherwise `None`.
        """
        return extract_string_value(text, quote_char)

    def _extract_write_args(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Extract write-tool arguments from model output text.

        Args:
            text: Model output text containing write-tool arguments.

        Returns:
            Parsed arguments when successful, otherwise `None`.
        """
        return extract_write_args(text)

    def _extract_balanced_json(self, text: str) -> Optional[str]:
        """
        Extract the last complete JSON object from free-form text.

        Args:
            text: Mixed text that may contain JSON content.

        Returns:
            Extracted JSON string when successful, otherwise `None`.
        """
        return extract_balanced_json(text)

    def _parse_tool_call(self, content: str) -> Optional[Dict[str, Any]]:
        """
        Parse a tool call from model output content.

        Args:
            content: Model output content.

        Returns:
            Parsed tool call dictionary when successful, otherwise `None`.
        """
        return parse_tool_call(content)

    def _execute_tool(
        self,
        tool_call: Dict[str, Any],
        tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None
    ) -> Any:
        """
        Execute one parsed tool call.

        Args:
            tool_call: Parsed tool call payload.
            tool_callback: Optional callback for tool execution events.

        Returns:
            Tool execution result.
        """
        return execute_tool(self, tool_call, tool_callback)

    def _call_llm(self, messages: List[Dict[str, str]]) -> str:
        """
        Call the configured LLM client with runtime messages.

        Args:
            messages: Runtime conversation messages.

        Returns:
            LLM response content string.
        """
        return call_llm(self, messages)

    def _is_stop_requested(self, stop_callback: Optional[Callable[[], bool]]) -> bool:
        """
        Evaluate whether the current run should stop.

        Args:
            stop_callback: Optional callback that returns `True` on stop requests.

        Returns:
            Whether stop has been requested.
        """
        return is_stop_requested(stop_callback)

    def _build_stop_response(
        self,
        status_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """
        Build the normalized stop response text.

        Args:
            status_callback: Optional callback for stop status updates.

        Returns:
            Stop message text.
        """
        return build_stop_response(self.STOP_MESSAGE, status_callback)

    def run_with_tools(
        self,
        query: str,
        max_iterations: int = 10,
        tool_callback: Optional[Callable[[str, str, Dict[str, Any]], None]] = None,
        status_callback: Optional[Callable[[str], None]] = None,
        stop_callback: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Execute one agent run with formatted tool-calling support.

        Args:
            query: User query text.
            max_iterations: Maximum number of tool-execution iterations.
            tool_callback: Optional callback for tool execution events.
            status_callback: Optional callback for status text updates.
            stop_callback: Optional callback that stops the run at safe boundaries.

        Returns:
            Final response text.
        """
        return run_with_tools(
            self,
            query = query,
            max_iterations = max_iterations,
            tool_callback = tool_callback,
            status_callback = status_callback,
            stop_callback = stop_callback,
        )

    def run(
        self,
        query: str,
        max_iterations: int = 10,
        stop_callback: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Execute the default agent run loop.

        Args:
            query: User query text.
            max_iterations: Maximum number of runtime iterations.
            stop_callback: Optional callback that stops the run at safe boundaries.

        Returns:
            Agent response text.
        """
        logger.info("Starting run with query: %s", query)
        return self.run_with_tools(
            query = query,
            max_iterations = max_iterations,
            stop_callback = stop_callback,
        )
