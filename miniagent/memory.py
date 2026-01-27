import os
import time
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from dataclasses import dataclass, field

logger = logging.getLogger("MiniAgent Memory")


def _default_memory_path() -> Path:
    """
    Get default memory path from environment variable or use default location
    """
    default_path = Path(os.environ.get("MINIAGENT_HOME", ".miniagent")).expanduser()
    default_path.mkdir(parents = True, exist_ok = True)
    return os.path.join(default_path, "memory.json")


@dataclass
class Memory:
    """
    Memory class for MiniAgent
    """
    path: Path = field(default_factory = _default_memory_path)
    preferences: Dict[str, Any] = field(default_factory = dict)
    facts: Dict[str, Any] = field(default_factory = dict)
    messages: List[Dict[str, str]] = field(default_factory = list)
    max_messages: int = 40

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            data = json.loads(self.path.read_text(encoding = "utf-8"))
            self.preferences = data.get("preferences", {}) or {}
            self.facts = data.get("facts", {}) or {}
            self.messages = data.get("messages", []) or []
        except Exception:
            logger.exception("Failed to load memory")

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents = True, exist_ok = True)
            payload = {
                "updated_at": int(time.time()),
                "preferences": self.preferences,
                "facts": self.facts,
                "messages": self.messages[-self.max_messages :],
            }
            self.path.write_text(
                json.dumps(payload, ensure_ascii = False, indent = 2),
                encoding = "utf-8"
            )
        except Exception:
            logger.exception("Failed to save memory")

    def set_preference(self, key: str, value: Any) -> None:
        self.preferences[key] = value
        self.save()

    def set_fact(self, key: str, value: Any) -> None:
        self.facts[key] = value
        self.save()

    def push(self, role: str, content: str) -> None:
        if not content:
            return
        self.messages.append({"role": role, "content": content})
        self.messages = self.messages[-self.max_messages :]
        self.save()

    def context(self) -> str:
        """Generate a compact memory context string for the LLM."""
        parts: List[str] = []
        if self.preferences:
            prefs = ", ".join(f"{k}={v}" for k, v in sorted(self.preferences.items()))
            parts.append(f"User preferences: {prefs}")
        if self.facts:
            facts = ", ".join(f"{k}={v}" for k, v in sorted(self.facts.items()))
            parts.append(f"User facts: {facts}")
        if self.messages:
            recent = self.messages[-10:]
            convo = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
            parts.append("Recent conversation:\n" + convo)
        return "\n\n".join(parts).strip()
