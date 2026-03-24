import os
import sys
import logging

from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.getcwd())

from quarkagent.skills.models import SkillDefinition
from quarkagent.skills.parsing import (
    SKILL_REFERENCE_PATTERN,
    VALID_SKILL_NAME_PATTERN,
    normalize_skill_name,
    split_frontmatter,
)

logger = logging.getLogger(__name__)


class SkillManager:
    """
    Discover and manage system/custom skills for the runtime.

    Args:
        system_skills_dir: Directory containing default system skills.
        custom_skills_dir: Directory containing user-invoked custom skills.
        default_system_skills: Optional allowlist of system skill directory names.
        enable_system_skills: Whether system skills should be injected by default.
        enable_custom_skill_tool: Whether the dynamic `skills` tool is exposed.
    """

    def __init__(
        self,
        system_skills_dir: str = "skills/system",
        custom_skills_dir: str = "skills/custom",
        default_system_skills: Optional[List[str]] = None,
        enable_system_skills: bool = True,
        enable_custom_skill_tool: bool = True
    ):
        """
        Initialize the skill manager and discover available skills.

        Args:
            system_skills_dir: Directory containing default system skills.
            custom_skills_dir: Directory containing user-invoked custom skills.
            default_system_skills: Optional allowlist of system skill directory names.
            enable_system_skills: Whether system skills should be injected by default.
            enable_custom_skill_tool: Whether the dynamic `skills` tool is exposed.
        """
        self.system_skills_dir = system_skills_dir
        self.custom_skills_dir = custom_skills_dir
        self.default_system_skills = default_system_skills or []
        self.enable_system_skills = enable_system_skills
        self.enable_custom_skill_tool = enable_custom_skill_tool
        self.system_skills: Dict[str, SkillDefinition] = {}
        self.custom_skills: Dict[str, SkillDefinition] = {}
        self.refresh()

    def refresh(self) -> None:
        """
        Refresh skill discovery from disk.

        Args:
            None.

        Returns:
            None.
        """
        self.system_skills = self._discover_namespace(self.system_skills_dir, "system")
        self.custom_skills = self._discover_namespace(self.custom_skills_dir, "custom")

    def _discover_namespace(
        self,
        root_dir: str,
        namespace: str
    ) -> Dict[str, SkillDefinition]:
        """
        Discover skills from a namespace directory.

        Args:
            root_dir: Namespace root directory.
            namespace: Namespace label.

        Returns:
            Mapping of normalized directory name to skill definition.
        """
        discovered_skills: Dict[str, SkillDefinition] = {}
        namespace_path = Path(root_dir)

        if not namespace_path.exists():
            logger.warning("Skill namespace directory does not exist: %s", root_dir)
            return discovered_skills

        if not namespace_path.is_dir():
            logger.warning("Skill namespace path is not a directory: %s", root_dir)
            return discovered_skills

        for skill_dir in sorted(namespace_path.iterdir(), key = lambda item: item.name.lower()):
            if not skill_dir.is_dir():
                continue

            skill_definition = self._load_skill_definition(skill_dir, namespace)
            if not skill_definition:
                continue

            discovered_skills[skill_dir.name.lower()] = skill_definition

        return discovered_skills

    def _load_skill_definition(
        self,
        skill_dir: Path,
        namespace: str
    ) -> Optional[SkillDefinition]:
        """
        Load one skill definition from disk.

        Args:
            skill_dir: Skill directory path.
            namespace: Namespace label.

        Returns:
            Parsed skill definition or `None` when invalid.
        """
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            logger.warning("Skipping skill without SKILL.md: %s", skill_dir)
            return None

        try:
            raw_text = skill_file.read_text(encoding = "utf-8")
        except Exception as exc:
            logger.warning("Failed to read skill file %s: %s", skill_file, exc)
            return None

        metadata, body = split_frontmatter(raw_text)
        skill_name = metadata.get("name") or skill_dir.name
        description = metadata.get("description") or (body.splitlines()[0].strip() if body else "")

        return SkillDefinition(
            name = skill_name,
            description = description,
            namespace = namespace,
            directory = str(skill_dir),
            skill_file = str(skill_file),
            content = body.strip(),
            enabled = False
        )

    def get_enabled_system_skills(self) -> List[SkillDefinition]:
        """
        Return the system skills enabled for default runtime loading.

        Args:
            None.

        Returns:
            Ordered list of enabled system skills.
        """
        if not self.enable_system_skills:
            return []

        if self.default_system_skills:
            target_skill_names = [normalize_skill_name(name).lower() for name in self.default_system_skills]
        else:
            target_skill_names = sorted(self.system_skills.keys())

        enabled_skills: List[SkillDefinition] = []
        for skill_name in target_skill_names:
            skill_definition = self.system_skills.get(skill_name)
            if not skill_definition:
                logger.warning("Configured system skill was not found: %s", skill_name)
                continue

            enabled_skills.append(
                SkillDefinition(
                    name = skill_definition.name,
                    description = skill_definition.description,
                    namespace = skill_definition.namespace,
                    directory = skill_definition.directory,
                    skill_file = skill_definition.skill_file,
                    content = skill_definition.content,
                    enabled = True
                )
            )

        return enabled_skills

    def list_skill_payloads(self) -> List[Dict[str, Any]]:
        """
        Build API-friendly payloads for all discovered skills.

        Args:
            None.

        Returns:
            List of serialized skill metadata dictionaries.
        """
        enabled_system_skill_names = {skill.directory.lower() for skill in self.get_enabled_system_skills()}
        payloads: List[Dict[str, Any]] = []

        for skill_map in [self.system_skills, self.custom_skills]:
            for skill_key in sorted(skill_map.keys()):
                skill_definition = skill_map[skill_key]
                payloads.append(
                    {
                        "name": skill_definition.name,
                        "description": skill_definition.description,
                        "namespace": skill_definition.namespace,
                        "path": skill_definition.directory,
                        "enabled": skill_definition.directory.lower() in enabled_system_skill_names,
                    }
                )

        return payloads

    def get_skill_definition(
        self,
        skill_name: str,
        namespace: Optional[str] = None
    ) -> Optional[SkillDefinition]:
        """
        Resolve one skill definition by directory key or display name.

        Args:
            skill_name: Raw skill name input.
            namespace: Optional namespace filter (`system` or `custom`).

        Returns:
            Matching skill definition or `None` if not found.
        """
        normalized_name = normalize_skill_name(skill_name).lower()
        skill_maps: List[Dict[str, SkillDefinition]] = []

        if namespace == "system":
            skill_maps = [self.system_skills]
        elif namespace == "custom":
            skill_maps = [self.custom_skills]
        else:
            skill_maps = [self.system_skills, self.custom_skills]

        for skill_map in skill_maps:
            if normalized_name in skill_map:
                return skill_map[normalized_name]

            for skill_definition in skill_map.values():
                if skill_definition.name.lower() == normalized_name:
                    return skill_definition

        return None

    def extract_custom_skill_names(self, text: str) -> List[str]:
        """
        Extract `${skill_name}` references from user text.

        Args:
            text: Raw user or query text.

        Returns:
            Ordered unique list of requested custom skill names.
        """
        requested_names: List[str] = []
        seen_names = set()

        for match in SKILL_REFERENCE_PATTERN.findall(text):
            normalized_name = normalize_skill_name(match)
            if normalized_name in seen_names:
                continue
            seen_names.add(normalized_name)
            requested_names.append(normalized_name)

        return requested_names

    def lookup_custom_skill(self, skill_name: str) -> Dict[str, Any]:
        """
        Resolve a custom skill by raw skill name or `${skill_name}` token.

        Args:
            skill_name: Raw skill reference.

        Returns:
            Structured lookup payload for the `skills` tool.
        """
        normalized_name = normalize_skill_name(skill_name)
        if not normalized_name:
            return {
                "status": "error",
                "error": "skill_name is required",
                "skill_name": skill_name,
            }

        if not VALID_SKILL_NAME_PATTERN.match(normalized_name):
            return {
                "status": "error",
                "error": "invalid skill name",
                "skill_name": normalized_name,
            }

        if not self.enable_custom_skill_tool:
            return {
                "status": "error",
                "error": "custom skill tool is disabled",
                "skill_name": normalized_name,
            }

        skill_definition = self.custom_skills.get(normalized_name.lower())
        if not skill_definition:
            return {
                "status": "not_found",
                "skill_name": normalized_name,
                "available_skills": sorted(skill.name for skill in self.custom_skills.values()),
            }

        return {
            "status": "ok",
            "skill_name": normalized_name,
            "name": skill_definition.name,
            "description": skill_definition.description,
            "namespace": skill_definition.namespace,
            "path": skill_definition.directory,
            "skill_file": skill_definition.skill_file,
            "content": skill_definition.content,
        }

    def build_system_skills_prompt(self) -> str:
        """
        Render the default-loaded system skills as prompt text.

        Args:
            None.

        Returns:
            Markdown-style prompt block for enabled system skills.
        """
        enabled_skills = self.get_enabled_system_skills()
        if not enabled_skills:
            return "No default system skills loaded."

        prompt_sections = []
        for skill_definition in enabled_skills:
            prompt_sections.append(
                "\n".join(
                    [
                        f"### System Skill: {skill_definition.name}",
                        f"Description: {skill_definition.description}",
                        f"Source: {skill_definition.directory}",
                        skill_definition.content,
                    ]
                ).strip()
            )

        return "\n\n".join(prompt_sections)

    def build_custom_skill_hint(self, text: str) -> str:
        """
        Render guidance for `${skill_name}` references found in the current query.

        Args:
            text: Raw query text.

        Returns:
            Prompt hint describing how to use the `skills` tool.
        """
        requested_skill_names = self.extract_custom_skill_names(text)
        if not requested_skill_names:
            return ""

        rendered_tokens = ", ".join(f"${{{name}}}" for name in requested_skill_names)
        return (
            "The user referenced custom skills "
            f"{rendered_tokens}. Use the `skills` tool with `skill_name` set to the token content "
            "to load the matching skill from `skills/custom` before answering."
        )

    def build_skills_tool(self) -> Dict[str, Any]:
        """
        Build the dynamic model-facing `skills` tool definition.

        Args:
            None.

        Returns:
            Tool definition dictionary compatible with `QuarkAgent.add_tool`.
        """
        def skills(skill_name: str) -> Dict[str, Any]:
            """
            Load one custom skill by name.

            Args:
                skill_name: Skill directory name or `${skill_name}` token.

            Returns:
                Structured custom skill lookup result.
            """
            return self.lookup_custom_skill(skill_name)

        return {
            "name": "skills",
            "description": (
                "Load a custom skill from `skills/custom`. "
                "When the user references `${skill_name}`, call this tool with `skill_name` set to that value."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "Custom skill name or `${skill_name}` token."
                    }
                },
                "required": ["skill_name"]
            },
            "executor": skills
        }
