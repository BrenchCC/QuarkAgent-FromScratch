import os
import sys
import logging

from typing import TYPE_CHECKING, Any, Dict, List, Optional
from uuid import uuid4

sys.path.append(os.getcwd())

if TYPE_CHECKING:
    from quarkagent.agent import QuarkAgent

logger = logging.getLogger(__name__)


def _clone_tool_definition(tool_definition: Dict[str, Any]) -> Dict[str, Any]:
    """
    Clone a runtime tool definition for safe reuse in a subagent.

    Args:
        tool_definition: Parent tool definition.

    Returns:
        Cloned tool definition dictionary.
    """
    return {
        "name": tool_definition["name"],
        "description": tool_definition["description"],
        "parameters": dict(tool_definition.get("parameters", {})),
        "executor": tool_definition["executor"],
    }


def _build_subagent_query(task: str, context: Optional[str]) -> str:
    """
    Build the user query passed to the delegated subagent.

    Args:
        task: Focused subtask for the child agent.
        context: Optional extra context from the parent agent.

    Returns:
        Rendered query string.
    """
    sections = [
        "You are executing a delegated subtask for the parent agent.",
        "Solve the subtask directly and return a concise final result to the parent agent.",
    ]

    if context and context.strip():
        sections.append("Additional context:\n" + context.strip())

    sections.append("Subtask:\n" + task.strip())
    return "\n\n".join(sections)


def build_subagent_tool(
    parent_agent: "QuarkAgent",
    default_max_iterations: int = 5,
    max_allowed_iterations: int = 8
) -> Dict[str, Any]:
    """
    Build the runtime `subagent` tool for one parent agent instance.

    Args:
        parent_agent: Parent agent that owns the tool.
        default_max_iterations: Default iteration cap for child runs.
        max_allowed_iterations: Hard cap for child runs.

    Returns:
        Tool definition compatible with `QuarkAgent.add_tool`.
    """
    from quarkagent.agent import QuarkAgent
    from quarkagent.memory import Memory

    def _generate_task_id() -> str:
        """
        Generate a stable task identifier for one delegated subagent run.

        Args:
            None.

        Returns:
            Task identifier string.
        """
        return f"task_{uuid4().hex[:12]}"

    def subagent(
        task: str,
        context: Optional[str] = None,
        tools: Optional[List[str]] = None,
        max_iterations: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Delegate a focused subtask to a child QuarkAgent instance.

        Args:
            task: Focused subtask to delegate.
            context: Optional extra context from the parent agent.
            tools: Optional list of allowed tool names for the child agent.
            max_iterations: Optional child iteration cap.

        Returns:
            Structured subagent execution result.
        """
        delegated_task = task.strip()
        if not delegated_task:
            return {
                "status": "error",
                "error": "task is required",
            }

        available_tools = {
            tool_definition["name"]: tool_definition
            for tool_definition in parent_agent.tools
            if tool_definition["name"] != "subagent"
        }
        available_tool_names = sorted(available_tools.keys())

        if tools is not None:
            requested_tool_names = [tool_name.strip() for tool_name in tools if tool_name and tool_name.strip()]
            invalid_tools = sorted(set(requested_tool_names) - set(available_tool_names))
            if invalid_tools:
                return {
                    "status": "error",
                    "error": "unknown tools requested",
                    "invalid_tools": invalid_tools,
                    "available_tools": available_tool_names,
                }
            selected_tool_names = requested_tool_names
        else:
            selected_tool_names = available_tool_names

        resolved_max_iterations = max_iterations or default_max_iterations
        resolved_max_iterations = max(1, min(int(resolved_max_iterations), max_allowed_iterations))
        task_id = _generate_task_id()

        subagent_memory = Memory(agent_scope = "subagent")
        subagent_memory.facts.update(
            {
                "task_id": task_id,
                "delegated_task": delegated_task,
                "delegated_tools": selected_tool_names,
                "parent_agent_scope": getattr(parent_agent, "agent_scope", "main"),
            }
        )
        subagent_memory.system_prompt = getattr(parent_agent, "base_system_prompt", None)
        if getattr(parent_agent, "memory_path", None):
            subagent_memory.facts["parent_memory_path"] = parent_agent.memory_path

        child_agent = QuarkAgent(
            model = parent_agent.model,
            api_key = parent_agent.api_key,
            base_url = parent_agent.base_url,
            temperature = parent_agent.temperature,
            top_p = parent_agent.top_p,
            system_prompt = parent_agent.base_system_prompt,
            system_skills = parent_agent.system_skills,
            skill_manager = parent_agent.skill_manager,
            model_identifier = getattr(parent_agent, "model_identifier", None),
            use_reflector = False,
            memory_context_provider = lambda query: subagent_memory.context(query = query),
        )
        child_agent.agent_scope = "subagent"
        child_agent.memory_path = str(subagent_memory.path)
        child_agent.tools = []

        for tool_name in selected_tool_names:
            child_agent.add_tool(_clone_tool_definition(available_tools[tool_name]))

        subagent_memory.set_runtime_state(
            system_prompt = child_agent.build_runtime_snapshot_prompt(),
            tools = selected_tool_names,
            skills = parent_agent.skill_manager.list_skill_payloads() if parent_agent.skill_manager else [],
            task_id = task_id,
        )

        query = _build_subagent_query(delegated_task, context)
        subagent_memory.push("user", query)
        answer = child_agent.run_with_tools(
            query,
            max_iterations = resolved_max_iterations,
            stop_callback = parent_agent._active_stop_callback,
        )
        subagent_memory.push("assistant", answer)

        return {
            "status": "stopped" if answer == child_agent.STOP_MESSAGE else "ok",
            "task_id": task_id,
            "task": delegated_task,
            "tools": selected_tool_names,
            "max_iterations": resolved_max_iterations,
            "answer": answer,
        }

    return {
        "name": "subagent",
        "description": (
            "Delegate a focused subtask to a child QuarkAgent instance. "
            "Use this when the work can be isolated, optionally restricting the child to a subset of tools."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task": {
                    "type": "string",
                    "description": "Focused subtask for the delegated child agent."
                },
                "context": {
                    "type": "string",
                    "description": "Optional extra context for the child agent."
                },
                "tools": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional subset of currently loaded parent tools that the child agent may use."
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Optional child iteration limit."
                }
            },
            "required": ["task"]
        },
        "executor": subagent,
    }
