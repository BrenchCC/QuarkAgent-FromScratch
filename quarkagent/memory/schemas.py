from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class MemorySummary:
    """
    Summary metadata for one saved memory file.
    """

    index: int
    agent_scope: str
    path: Path
    updated_at: Optional[int] = None
    message_count: int = 0
    task_id: Optional[str] = None
    delegated_task: Optional[str] = None
    last_message: str = ""
    is_legacy: bool = False
