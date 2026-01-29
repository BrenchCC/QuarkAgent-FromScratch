from __future__ import annotations

import os
import re
import sys
import logging
import subprocess
from pathlib import Path

from typing import Any, Dict, List, Tuple, Optional    

sys.path.append(os.getcwd())

from quarkagent.tools import register_tool

logger = logging.getLogger(__name__)

def _resolve_path(path: str) -> Path:
    """Resolve a relative path to an absolute path."""
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = Path(os.getcwd()) / p
    return p

def _read_text_file(path: Path) -> str:
    """Read the content of a text file."""
    try:
        with path.open('r', encoding = 'utf-8') as f:
            return f.read().splitlines()
    except Exception as e:
        logger.error(f"Error reading file {path}: {e}", exc_info = True)
        return ""

def _write_text_file(path: Path, content: str) -> None:
    """Write content to a text file."""
    path.parent.mkdir(parents = True, exist_ok = True)
    try:
        with path.open('w', encoding = 'utf-8') as f:
            f.write(content)
    except Exception as e:
        logger.error(f"Error writing file {path}: {e}", exc_info = True)


def _iter_files(root: Path) -> List[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        return []
    return [p for p in root.rglob("*") if p.is_file()]


@register_tool
def read(path: str, offset: int = 1, limit: int = 200) -> str:
    """Read file content with line numbers.

    Args:
        path: File path.
        offset: 1-based start line number.
        limit: Max number of lines to return.

    Returns:
        A string containing the selected lines with line numbers.
    """
    file_path = _resolve_path(path)
    if not file_path.exists() or not file_path.is_file():
        error_msg = f"Error: File {path} does not exist or is not a regular file."
        logger.error(error_msg)
        return error_msg
    
    lines = _read_text_file(file_path)
    num_lines = len(lines)

    if limit <= 0:
        error_msg = f"Error: Limit must be a positive integer."
        logger.error(error_msg)
        return error_msg

    start = max(1, int(offset))
    end = min(num_lines, start + int(limit) - 1)

    if start > num_lines:
        error_msg = f"Error: Start line number {start} is out of range. The file only has {num_lines} lines."
        logger.error(error_msg)
        return error_msg
    
    width = len(str(end))
    body = "\n".join(
        f"{str(i).rjust(width)}| {lines[i-1]}" for i in range(start, end + 1)
    )

    return f"path: {file_path} \n lines: {start}-{end}/{num_lines} \n {body}"

@register_tool
# noqa: A002
def write(path: str, content: str) -> str:
    """
    Write content to a text file.

    Args:
        path: File path.
        content: Content to write.

    Returns:
        A string indicating the success or failure of the operation.
    """
    file_path = _resolve_path(path)
    try:
        _write_text_file(file_path, content)
        return f"Write {file_path} success."
    except Exception as e:
        logger.exception("write failed")
        return f"error: {e}"

@register_tool
# noqa: A002
def edit(path: str, old: str, new: str, all: bool = False) -> str:
    """
    Edit file content.

    Args:
        path: File path.
        old: Old content to replace.
        new: New content to replace with.
        all: Whether to replace all occurrences.

    Returns:
        A string indicating the success or failure of the operation.
    """ 
    file_path = _resolve_path(path)
    if not file_path.exists() or not file_path.is_file():
        error_msg = f"Error: File {path} does not exist or is not a regular file."
        logger.error(error_msg)
        return error_msg

    try:
        original = file_path.read_text(encoding = "utf-8", errors = "replace")
        if old not in original:
            error_msg = f"Error: 'old' text not found in file {path}."
            logger.error(error_msg)
            return error_msg

        updated = original.replace(old, new) if all else original.replace(old, new, 1)
        _write_text_file(file_path, updated)
        logger.info(f"Successfully edited file {file_path}.")
        return f"Edit {file_path} success."
    except Exception as e:
        logger.exception("edit failed")
        return f"error: {e}"

# noqa: A002
@register_tool
def glob(pattern: str, path: str = ".") -> List[str]:
    """
    Glob files in a directory.

    Args:
        pattern: Glob pattern.
        path: Directory path.

    Returns:
        A list of file paths.
    """
    root = _resolve_path(path)
    if not root.exists():
        return []
    try:
        matches = root.glob(pattern)
        return [str(p.resolve()) for p in matches]
    except Exception as e:
        logger.exception("glob failed")
        return [f"error: {e}"]

# noqa: A002
@register_tool
def grep(pattern: str, path: str = ".") -> List[Dict[str, Any]]:
    """
    Search for a pattern in files.

    Args:
        pattern: Regex pattern.
        path: Directory path.

    Returns:
        A list of dictionaries with file paths and matching lines.
    """
    root = _resolve_path(path)
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return [{"error": f"invalid regex: {e}"}]

    results: List[Dict[str, Any]] = []
    for file_path in _iter_files(root):
        try:
            lines = _read_text_file(file_path)
        except Exception:
            continue

        for idx, line in enumerate(lines, start=1):
            if regex.search(line):
                results.append(
                    {
                    "file": str(file_path),
                    "line": idx,
                    "text": line,
                    }
                )

    return results


@register_tool
def bash(cmd: str) -> Dict[str, Any]:
    """Execute a shell command.

    Args:
        cmd: Shell command string.

    Returns:
        Dict containing exit_code, stdout, stderr.
    """
    try:
        completed = subprocess.run(
            cmd,
            shell = True,
            text = True,
            capture_output = True,
            cwd = os.getcwd(),
            env = os.environ.copy(),
        )
        return {
            "exit_code": completed.returncode,
            "stdout": (completed.stdout or "").strip(),
            "stderr": (completed.stderr or "").strip(),
        }
    except Exception as e:
        logger.exception("bash failed")
        return {"exit_code": 1, "stdout": "", "stderr": str(e)}
