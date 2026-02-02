"""
Session Store for Chat Control Plane
=====================================
In-memory session and preview cache with TTL.

SECURITY: This module MUST NOT contain any execution logic.
          It only stores and retrieves data.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Any
import uuid
import threading

# Constants
SESSION_TTL_SECONDS = 600      # 10 minutes
PREVIEW_TTL_SECONDS = 300      # 5 minutes
MAX_PREVIEWS_PER_SESSION = 5

@dataclass
class Preview:
    """Cached preview waiting for confirmation."""
    preview_id: str
    session_id: str
    channel: str
    raw_input: str
    normalized_task: Dict[str, Any]
    created_at: datetime
    expires_at: datetime
    confirmed: bool = False

@dataclass
class Session:
    """User session with preview cache."""
    session_id: str
    channel: str
    created_at: datetime
    last_activity: datetime
    previews: Dict[str, Preview] = field(default_factory=dict)

    def is_expired(self) -> bool:
        now = datetime.now(timezone.utc)
        return (now - self.last_activity).total_seconds() > SESSION_TTL_SECONDS

    def touch(self) -> None:
        """Reset TTL on activity."""
        self.last_activity = datetime.now(timezone.utc)


class SessionStore:
    """
    Thread-safe session and preview storage.

    NO EXECUTION LOGIC - data storage only.
    """

    def __init__(self):
        self._sessions: Dict[str, Session] = {}
        self._lock = threading.RLock()

    def get_or_create_session(self, session_id: str, channel: str) -> Session:
        """Get existing session or create new one."""
        with self._lock:
            self._cleanup_expired()

            if session_id in self._sessions:
                session = self._sessions[session_id]
                session.touch()
                return session

            # Create new session
            now = datetime.now(timezone.utc)
            session = Session(
                session_id=session_id,
                channel=channel,
                created_at=now,
                last_activity=now
            )
            self._sessions[session_id] = session
            return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get session if exists and not expired."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session and not session.is_expired():
                session.touch()
                return session
            return None

    def store_preview(
        self,
        session_id: str,
        channel: str,
        raw_input: str,
        normalized_task: Dict[str, Any]
    ) -> Preview:
        """Store a preview and return it with preview_id."""
        with self._lock:
            session = self.get_or_create_session(session_id, channel)

            # Enforce max previews
            if len(session.previews) >= MAX_PREVIEWS_PER_SESSION:
                # Remove oldest
                oldest_id = min(
                    session.previews.keys(),
                    key=lambda k: session.previews[k].created_at
                )
                del session.previews[oldest_id]

            # Create preview
            now = datetime.now(timezone.utc)
            preview = Preview(
                preview_id=str(uuid.uuid4()),
                session_id=session_id,
                channel=channel,
                raw_input=raw_input,
                normalized_task=normalized_task,
                created_at=now,
                expires_at=now + timedelta(seconds=PREVIEW_TTL_SECONDS)
            )

            session.previews[preview.preview_id] = preview
            return preview

    def get_preview(self, preview_id: str, session_id: str) -> Optional[Preview]:
        """Get preview if valid and belongs to session."""
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return None

            preview = session.previews.get(preview_id)
            if not preview:
                return None

            # Check expiry
            if datetime.now(timezone.utc) > preview.expires_at:
                del session.previews[preview_id]
                return None

            # Check already confirmed
            if preview.confirmed:
                return None

            return preview

    def mark_confirmed(self, preview_id: str, session_id: str) -> bool:
        """Mark preview as confirmed (can't be used again)."""
        with self._lock:
            session = self.get_session(session_id)
            if not session:
                return False

            preview = session.previews.get(preview_id)
            if not preview or preview.confirmed:
                return False

            preview.confirmed = True
            return True

    def _cleanup_expired(self) -> None:
        """Remove expired sessions (called internally)."""
        expired = [
            sid for sid, session in self._sessions.items()
            if session.is_expired()
        ]
        for sid in expired:
            del self._sessions[sid]

    def stats(self) -> Dict[str, Any]:
        """Return store statistics."""
        with self._lock:
            self._cleanup_expired()
            total_previews = sum(
                len(s.previews) for s in self._sessions.values()
            )
            return {
                "active_sessions": len(self._sessions),
                "total_previews": total_previews
            }


# Global singleton
_store: Optional[SessionStore] = None

def get_store() -> SessionStore:
    """Get or create the global session store."""
    global _store
    if _store is None:
        _store = SessionStore()
    return _store
