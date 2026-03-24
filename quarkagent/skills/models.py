import os
import sys

from dataclasses import dataclass

sys.path.append(os.getcwd())


@dataclass
class SkillDefinition:
    """
    Structured metadata for a discovered skill.

    Args:
        name: User-facing skill name.
        description: Short description from frontmatter.
        namespace: Skill namespace, usually `system` or `custom`.
        directory: Directory path containing the skill.
        skill_file: Full path to the `SKILL.md` file.
        content: Markdown body of the skill file.
        enabled: Whether the skill is enabled by default.
    """

    name: str
    description: str
    namespace: str
    directory: str
    skill_file: str
    content: str
    enabled: bool = False
