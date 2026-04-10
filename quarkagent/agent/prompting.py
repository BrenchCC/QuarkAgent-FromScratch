import os
import sys
import logging

from typing import Any, Callable, Dict, List, Optional, Sequence

sys.path.append(os.getcwd())

from quarkagent.agent.constants import DEFAULT_SYSTEM_PROMPT, LOGGER_NAME

logger = logging.getLogger(LOGGER_NAME)


def load_system_prompt(
    system_prompt: Optional[str],
    system_prompt_file: Optional[str]
) -> str:
    """
    Load the base system prompt from a direct value or a prompt file.

    Args:
        system_prompt: Inline system prompt content when explicitly provided.
        system_prompt_file: Prompt file path to read when inline content is absent.

    Returns:
        Loaded system prompt string.
    """
    if system_prompt:
        logger.info("System prompt provided as parameter")
        return system_prompt

    prompt_file = resolve_prompt_file(system_prompt_file)
    if os.path.exists(prompt_file):
        try:
            with open(prompt_file, "r", encoding = "utf-8") as f:
                loaded_prompt = f.read().strip()
            logger.info("System prompt loaded from file: %s", prompt_file)
            return loaded_prompt
        except Exception as exc:
            logger.warning("Failed to load system prompt from file %s: %s", prompt_file, exc)
            return DEFAULT_SYSTEM_PROMPT

    logger.warning("System prompt file not found: %s", prompt_file)
    return DEFAULT_SYSTEM_PROMPT


def resolve_prompt_file(system_prompt_file: Optional[str]) -> str:
    """
    Resolve the effective system prompt file path.

    Args:
        system_prompt_file: Optional prompt file path from configuration.

    Returns:
        Resolved prompt file path.
    """
    if system_prompt_file:
        return system_prompt_file

    quarkagent_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    project_root = os.path.dirname(quarkagent_root)
    return os.path.join(project_root, "prompts", "system_prompt.txt")


def build_tools_prompt(tools: List[Dict[str, Any]]) -> str:
    """
    Build the rendered tools prompt block for the current agent tools.

    Args:
        tools: Runtime tool definitions loaded into the agent.

    Returns:
        Tools prompt string.
    """
    tool_descriptions = []
    for tool in tools:
        params = tool.get("parameters", {})
        param_descriptions = []

        for name, schema in params.get("properties", {}).items():
            required = name in params.get("required", [])
            param_descriptions.append(
                f"{name}: {schema.get('description', '')} {'(required)' if required else ''}"
            )

        tool_descriptions.append(
            "\n".join(
                [
                    f"Tool: {tool['name']}",
                    f"Description: {tool['description']}",
                    "Parameters:",
                    "\n".join(param_descriptions),
                ]
            )
        )

    return "\n".join(tool_descriptions)


def build_system_skills_prompt(system_skills: Sequence[Any]) -> str:
    """
    Build the rendered system skills block for the current turn.

    Args:
        system_skills: Loaded system skill definitions.

    Returns:
        System skills prompt string.
    """
    if not system_skills:
        return "No default system skills loaded."

    rendered_skills = []
    for skill in system_skills:
        rendered_skills.append(
            "\n".join(
                [
                    f"### System Skill: {skill.name}",
                    f"Description: {skill.description}",
                    f"Source: {skill.directory}",
                    skill.content,
                ]
            ).strip()
        )

    return "\n\n".join(rendered_skills)


def build_memory_context(
    memory_context_provider: Optional[Callable[[Optional[str]], str]],
    query: Optional[str]
) -> str:
    """
    Render dynamic memory context when a memory provider is available.

    Args:
        memory_context_provider: Optional callable for runtime memory rendering.
        query: Current user query.

    Returns:
        Rendered memory context string.
    """
    if not memory_context_provider:
        return ""

    try:
        return (memory_context_provider(query) or "").strip()
    except Exception as exc:
        logger.warning("Failed to render memory context: %s", exc)
        return ""


def build_runtime_system_prompt(
    base_system_prompt: str,
    tools: List[Dict[str, Any]],
    system_skills: Sequence[Any],
    skill_manager: Optional[Any],
    memory_context_provider: Optional[Callable[[Optional[str]], str]],
    query: str
) -> str:
    """
    Build the final runtime system prompt for one user turn.

    Args:
        base_system_prompt: Base system prompt content.
        tools: Runtime tool definitions.
        system_skills: Loaded system skill definitions.
        skill_manager: Optional skill manager used to render custom skill hints.
        memory_context_provider: Optional memory provider for runtime context.
        query: Current user query.

    Returns:
        Fully rendered runtime system prompt.
    """
    runtime_prompt = base_system_prompt
    tools_prompt = build_tools_prompt(tools) if tools else "No tools available."
    system_skills_prompt = build_system_skills_prompt(system_skills)
    custom_skill_hint = ""

    if skill_manager:
        custom_skill_hint = skill_manager.build_custom_skill_hint(query)

    has_system_skills_placeholder = "{system_skills_prompt}" in runtime_prompt
    has_custom_skills_hint_placeholder = "{custom_skills_hint}" in runtime_prompt
    has_tools_placeholder = "{tools_prompt}" in runtime_prompt

    runtime_prompt = runtime_prompt.replace("{system_skills_prompt}", system_skills_prompt)
    runtime_prompt = runtime_prompt.replace("{custom_skills_hint}", custom_skill_hint)
    runtime_prompt = runtime_prompt.replace("{tools_prompt}", tools_prompt)

    if not has_system_skills_placeholder and system_skills:
        runtime_prompt = runtime_prompt.rstrip() + "\n\nLoaded System Skills:\n" + system_skills_prompt

    if not has_custom_skills_hint_placeholder and custom_skill_hint:
        runtime_prompt = runtime_prompt.rstrip() + "\n\nCustom Skill Hint:\n" + custom_skill_hint

    if not has_tools_placeholder and tools:
        runtime_prompt = runtime_prompt.rstrip() + "\n\nAvailable Tools:\n" + tools_prompt

    memory_context = build_memory_context(memory_context_provider, query)
    if memory_context:
        runtime_prompt = runtime_prompt.rstrip() + "\n\nConversation Memory:\n" + memory_context

    return runtime_prompt
