import os
import sys
import json
import re

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.append(os.getcwd())

from .constants import DEFAULT_AGENT_SCOPE, LEGACY_MEMORY_FILENAME, logger
from .schemas import MemorySummary


def normalize_agent_scope(agent_scope: Optional[str]) -> str:
    """
    Normalize an agent scope string for directory and filename usage.

    Args:
        agent_scope: Raw agent scope value.

    Returns:
        Safe normalized scope name.
    """
    normalized_scope = (agent_scope or DEFAULT_AGENT_SCOPE).strip().lower()
    normalized_scope = re.sub(r"[^a-z0-9_-]+", "-", normalized_scope)
    return normalized_scope or DEFAULT_AGENT_SCOPE


def get_memory_root() -> Path:
    """
    Get the shared memory root directory.

    Args:
        None.

    Returns:
        Memory root path.
    """
    memory_root = Path(os.environ.get("QUARKAGENT_HOME", ".quarkagent")).expanduser() / "memory"
    memory_root.mkdir(parents = True, exist_ok = True)
    return memory_root


def get_memory_dir(agent_scope: str = DEFAULT_AGENT_SCOPE) -> Path:
    """
    Get the scoped memory directory from environment variable or use default location.

    Args:
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        Scoped memory directory path.
    """
    memory_dir = get_memory_root() / normalize_agent_scope(agent_scope)
    memory_dir.mkdir(parents = True, exist_ok = True)
    return memory_dir


def generate_timestamped_filename(agent_scope: str = DEFAULT_AGENT_SCOPE) -> str:
    """
    Generate a timestamped filename with scope prefix.

    Args:
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        Timestamped filename string.
    """
    normalized_scope = normalize_agent_scope(agent_scope)
    return f"{normalized_scope}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.json"


def list_memory_files(agent_scope: str = DEFAULT_AGENT_SCOPE) -> List[Path]:
    """
    List all memory files for one scope sorted by creation time.

    Args:
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        Memory file paths sorted from oldest to newest.
    """
    normalized_scope = normalize_agent_scope(agent_scope)
    scoped_dir = get_memory_dir(normalized_scope)
    memory_files = [file for file in scoped_dir.glob("*.json") if file.name != LEGACY_MEMORY_FILENAME]

    if normalized_scope == DEFAULT_AGENT_SCOPE:
        legacy_root = get_memory_root()
        memory_files.extend(
            [file for file in legacy_root.glob("*.json") if file.name != LEGACY_MEMORY_FILENAME]
        )

    return sorted(memory_files, key = lambda item: item.stat().st_ctime)


def manage_memory_files(
    max_files: int = 8,
    agent_scope: str = DEFAULT_AGENT_SCOPE
) -> None:
    """
    Manage memory files for one scope and keep only the most recent files created in
    the scoped directory. Legacy root-level files are not modified.

    Args:
        max_files: Maximum number of files to keep per scope.
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        None.
    """
    memory_dir = get_memory_dir(agent_scope)
    memory_files = sorted(
        [file for file in memory_dir.glob("*.json") if file.name != LEGACY_MEMORY_FILENAME],
        key = lambda item: item.stat().st_ctime
    )

    if len(memory_files) <= max_files:
        return

    files_to_delete = memory_files[:len(memory_files) - max_files]
    for file in files_to_delete:
        try:
            file.unlink()
            logger.info("Deleted old memory file: %s", file)
        except Exception:
            logger.exception("Failed to delete old memory file: %s", file)


def default_memory_path(agent_scope: str = DEFAULT_AGENT_SCOPE) -> Path:
    """
    Get default memory path with scoped timestamped filename.

    Args:
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        Default memory file path.
    """
    normalized_scope = normalize_agent_scope(agent_scope)
    memory_dir = get_memory_dir(normalized_scope)
    manage_memory_files(agent_scope = normalized_scope)
    return memory_dir / generate_timestamped_filename(normalized_scope)


def get_memory_path_by_index(
    index: int,
    agent_scope: str = DEFAULT_AGENT_SCOPE
) -> Optional[Path]:
    """
    Get memory file path by index (1-based). 1 = most recent, 2 = second most recent, etc.

    Args:
        index: Reverse-chronological memory index.
        agent_scope: Logical agent scope such as `main` or `subagent`.

    Returns:
        Memory file path when the index exists, otherwise `None`.
    """
    memory_files = list_memory_files(agent_scope = agent_scope)
    if 1 <= index <= len(memory_files):
        return memory_files[-index]
    return None


def list_memory_summaries(
    agent_scope: str = DEFAULT_AGENT_SCOPE,
    limit: int = 8
) -> List[MemorySummary]:
    """
    Build recent memory summaries for one agent scope.

    Args:
        agent_scope: Logical agent scope such as `main` or `subagent`.
        limit: Maximum number of summaries to return.

    Returns:
        Recent memory summaries ordered from newest to oldest.
    """
    normalized_scope = normalize_agent_scope(agent_scope)
    summaries: List[MemorySummary] = []
    recent_files = list(reversed(list_memory_files(agent_scope = normalized_scope)))[:limit]

    for index, path in enumerate(recent_files, start = 1):
        payload: Dict[str, Any] = {}

        try:
            payload = json.loads(path.read_text(encoding = "utf-8"))
        except Exception:
            logger.exception("Failed to build memory summary from %s", path)

        messages = payload.get("messages", []) or []
        facts = payload.get("facts", {}) or {}
        last_message = ""
        if messages:
            last_message = str(messages[-1].get("content", ""))

        summaries.append(
            MemorySummary(
                index = index,
                agent_scope = normalize_agent_scope(payload.get("agent_scope", normalized_scope)),
                path = path,
                updated_at = payload.get("updated_at"),
                message_count = len(messages),
                task_id = payload.get("task_id") or facts.get("task_id"),
                delegated_task = facts.get("delegated_task"),
                last_message = last_message,
                is_legacy = normalized_scope == DEFAULT_AGENT_SCOPE and path.parent == get_memory_root(),
            )
        )

    return summaries
