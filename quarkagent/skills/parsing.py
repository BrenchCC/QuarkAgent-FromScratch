import os
import re
import sys

from typing import Dict, List, Tuple

sys.path.append(os.getcwd())

SKILL_REFERENCE_PATTERN = re.compile(r"\$\{([A-Za-z0-9][A-Za-z0-9._-]*)\}")
VALID_SKILL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def strip_wrapping_quotes(value: str) -> str:
    """
    Remove a single layer of wrapping quotes from a string.

    Args:
        value: Raw string value.

    Returns:
        Unwrapped string value.
    """
    cleaned_value = value.strip()
    if len(cleaned_value) >= 2 and cleaned_value[0] == cleaned_value[-1] and cleaned_value[0] in {'"', "'"}:
        return cleaned_value[1:-1]
    return cleaned_value


def split_frontmatter(raw_text: str) -> Tuple[Dict[str, str], str]:
    """
    Split a markdown file into frontmatter and body sections.

    Args:
        raw_text: Full markdown text.

    Returns:
        Tuple of parsed frontmatter dictionary and remaining markdown body.
    """
    if not raw_text.startswith("---\n"):
        return {}, raw_text

    lines = raw_text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, raw_text

    frontmatter_lines: List[str] = []
    body_start_index = 0

    for index, line in enumerate(lines[1:], start = 1):
        if line.strip() == "---":
            body_start_index = index + 1
            break
        frontmatter_lines.append(line)
    else:
        return {}, raw_text

    metadata: Dict[str, str] = {}
    for line in frontmatter_lines:
        if ":" not in line:
            continue

        key, value = line.split(":", 1)
        metadata[key.strip()] = strip_wrapping_quotes(value)

    body = "\n".join(lines[body_start_index:]).strip()
    return metadata, body


def normalize_skill_name(skill_name: str) -> str:
    """
    Normalize a raw skill name or `${skill_name}` token.

    Args:
        skill_name: Raw skill name input.

    Returns:
        Normalized skill name.
    """
    normalized_name = skill_name.strip()
    if normalized_name.startswith("${") and normalized_name.endswith("}"):
        normalized_name = normalized_name[2:-1].strip()
    return normalized_name
