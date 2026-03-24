import os
import sys

from dataclasses import dataclass
from typing import Optional, Tuple

sys.path.append(os.getcwd())

from quarkagent.skills.manager import SkillManager


@dataclass
class SkillCommandResult:
    """
    Shared response payload for local `/skills` commands.

    Args:
        status: Resolution status for the command.
        title: Short display title.
        body: Markdown-friendly body text.
    """

    status: str
    title: str
    body: str


def parse_skill_command(message: str) -> Optional[Tuple[str, Optional[str]]]:
    """
    Parse a local skills command from raw user input.

    Args:
        message: Raw user message.

    Returns:
        Tuple of command type and optional skill name, or `None`.
    """
    normalized_message = message.strip()
    if not normalized_message:
        return None

    for prefix in ["/skills", "$skills"]:
        if normalized_message == prefix:
            return "overview", None

        if normalized_message.startswith(prefix + " "):
            requested_name = normalized_message[len(prefix):].strip()
            if not requested_name:
                return "overview", None
            return "detail", requested_name

    return None


def build_skill_command_response(
    skill_manager: Optional[SkillManager],
    message: str
) -> Optional[SkillCommandResult]:
    """
    Resolve a local skills command into markdown content.

    Args:
        skill_manager: Skill manager for the current runtime.
        message: Raw user message.

    Returns:
        Structured command response or `None` if the message is not a skill command.
    """
    command = parse_skill_command(message)
    if not command:
        return None

    if not skill_manager:
        return SkillCommandResult(
            status = "unavailable",
            title = "Skills",
            body = "Skills are not configured for this session.",
        )

    command_type, skill_name = command
    if command_type == "overview":
        return SkillCommandResult(
            status = "overview",
            title = "Skills",
            body = _render_skills_overview(skill_manager),
        )

    skill_definition = skill_manager.get_skill_definition(skill_name or "")
    if not skill_definition:
        return SkillCommandResult(
            status = "not_found",
            title = "Skill Detail",
            body = (
                f"Skill `{skill_name}` was not found.\n\n"
                "Use `/skills` or `$skills` to list the available system and custom skills."
            ),
        )

    return SkillCommandResult(
        status = "detail",
        title = f"Skill Detail: {skill_definition.name}",
        body = _render_skill_detail(skill_manager, skill_definition.name),
    )


def _render_skills_overview(skill_manager: SkillManager) -> str:
    """
    Render the markdown overview for all available skills.

    Args:
        skill_manager: Skill manager for the current runtime.

    Returns:
        Markdown text for the overview.
    """
    system_skills = skill_manager.get_enabled_system_skills()
    custom_skills = [
        skill_manager.custom_skills[skill_name]
        for skill_name in sorted(skill_manager.custom_skills.keys())
    ]

    lines = [
        "# Skills",
        "",
        "## System Skills",
    ]

    if system_skills:
        for skill in system_skills:
            lines.append(f"- `{skill.name}`: {skill.description or '-'} (source: `{skill.directory}`)")
    else:
        lines.append("- None: No default system skills are enabled.")

    lines.extend(
        [
            "",
            "## Custom Skills",
        ]
    )

    if custom_skills:
        for skill in custom_skills:
            lines.append(f"- `{skill.name}`: {skill.description or '-'} (source: `{skill.directory}`)")
    else:
        lines.append("- None: No custom skills found under `skills/custom`.")

    custom_usage = (
        "Use `${skill_name}` to load a custom skill from `skills/custom/<skill_name>/`."
        if skill_manager.enable_custom_skill_tool
        else "Custom skill loading is disabled in the current configuration."
    )

    lines.extend(
        [
            "",
            "## Usage",
            "- `skills/system/*` are loaded automatically for each session.",
            f"- {custom_usage}",
            "- Use `/skills <name>` or `$skills <name>` to inspect one skill locally.",
        ]
    )

    return "\n".join(lines)


def _render_skill_detail(skill_manager: SkillManager, skill_name: str) -> str:
    """
    Render the markdown detail for one skill.

    Args:
        skill_manager: Skill manager for the current runtime.
        skill_name: Requested skill name.

    Returns:
        Markdown text for the detail view.
    """
    skill_definition = skill_manager.get_skill_definition(skill_name)
    if not skill_definition:
        return (
            f"Skill `{skill_name}` was not found.\n\n"
            "Use `/skills` or `$skills` to list the available system and custom skills."
        )

    if skill_definition.namespace == "system":
        load_policy = "Loaded by default in the runtime prompt."
    else:
        load_policy = f"Load on demand with `${{{skill_definition.name}}}`."

    lines = [
        f"# Skill: {skill_definition.name}",
        "",
        "## Summary",
        f"- Name: `{skill_definition.name}`",
        f"- Namespace: `{skill_definition.namespace}`",
        f"- Description: {skill_definition.description or '-'}",
        f"- Source: `{skill_definition.directory}`",
        f"- Load Policy: {load_policy}",
        "",
        "## Content",
        skill_definition.content or "_No skill content found._",
    ]

    return "\n".join(lines)
