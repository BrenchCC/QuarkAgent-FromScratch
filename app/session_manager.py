import uuid
import copy
import logging

from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SessionRecord:
    """In-memory session state record."""

    session_id: str
    created_at: datetime
    expires_at: datetime
    history: List[Dict[str, str]] = field(default_factory = list)


class SessionManager:
    """Manage in-memory chat sessions with TTL."""

    def __init__(self, ttl_seconds: int = 1800):
        """
        Initialize the session manager.

        Args:
            ttl_seconds: Session time-to-live in seconds.
        """
        self.ttl_seconds = ttl_seconds
        self._sessions: Dict[str, SessionRecord] = {}
        self._lock = RLock()

    @staticmethod
    def _utcnow() -> datetime:
        """
        Return timezone-aware UTC timestamp.

        Args:
            None.

        Returns:
            Current UTC datetime.
        """
        return datetime.now(timezone.utc)

    def _build_expiry(self) -> datetime:
        """
        Build a new expiry timestamp.

        Args:
            None.

        Returns:
            Expiry datetime.
        """
        return self._utcnow() + timedelta(seconds = self.ttl_seconds)

    def _cleanup_locked(self) -> int:
        """
        Remove expired sessions while lock is held.

        Args:
            None.

        Returns:
            Count of deleted sessions.
        """
        now = self._utcnow()
        expired_ids = [
            session_id
            for session_id, record in self._sessions.items()
            if record.expires_at <= now
        ]

        for session_id in expired_ids:
            del self._sessions[session_id]

        if expired_ids:
            logger.info("Cleaned %s expired sessions", len(expired_ids))

        return len(expired_ids)

    def cleanup_expired(self) -> int:
        """
        Remove expired sessions.

        Args:
            None.

        Returns:
            Count of deleted sessions.
        """
        with self._lock:
            return self._cleanup_locked()

    def create_session(self) -> SessionRecord:
        """
        Create a new session.

        Args:
            None.

        Returns:
            Created SessionRecord.
        """
        with self._lock:
            self._cleanup_locked()
            now = self._utcnow()
            session_id = uuid.uuid4().hex
            record = SessionRecord(
                session_id = session_id,
                created_at = now,
                expires_at = self._build_expiry(),
            )
            self._sessions[session_id] = record
            return copy.deepcopy(record)

    def get_session(self, session_id: str, touch: bool = True) -> Optional[SessionRecord]:
        """
        Get a session by ID.

        Args:
            session_id: Target session ID.
            touch: Whether to refresh session expiry on read.

        Returns:
            Session record if found, otherwise None.
        """
        with self._lock:
            self._cleanup_locked()
            record = self._sessions.get(session_id)
            if not record:
                return None

            if touch:
                record.expires_at = self._build_expiry()

            return copy.deepcopy(record)

    def delete_session(self, session_id: str) -> bool:
        """
        Delete a session by ID.

        Args:
            session_id: Target session ID.

        Returns:
            True if deleted, False if missing.
        """
        with self._lock:
            self._cleanup_locked()
            if session_id not in self._sessions:
                return False

            del self._sessions[session_id]
            return True

    def get_history(self, session_id: str) -> Optional[List[Dict[str, str]]]:
        """
        Get session history.

        Args:
            session_id: Target session ID.

        Returns:
            Session history copy if found, otherwise None.
        """
        with self._lock:
            self._cleanup_locked()
            record = self._sessions.get(session_id)
            if not record:
                return None

            record.expires_at = self._build_expiry()
            return copy.deepcopy(record.history)

    def append_message(self, session_id: str, role: str, content: str) -> bool:
        """
        Append a message to session history.

        Args:
            session_id: Target session ID.
            role: Message role (user/assistant).
            content: Message content.

        Returns:
            True if appended, False if session missing.
        """
        if not content:
            return False

        with self._lock:
            self._cleanup_locked()
            record = self._sessions.get(session_id)
            if not record:
                return False

            record.history.append({"role": role, "content": content})
            record.history = record.history[-80:]
            record.expires_at = self._build_expiry()
            return True
