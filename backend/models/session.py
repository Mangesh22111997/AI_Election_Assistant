"""
backend/models/session.py
──────────────────────────
Session and chat history Pydantic models.

Tracks per-user conversation state including:
  - Session metadata (ID, user, language preference)
  - Chat history (list of turns)
  - Safety audit trail per turn
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class ChatTurn(BaseModel):
    """A single question-answer turn in the conversation."""

    turn_id: str = Field(default_factory=lambda: str(uuid4()))
    query: str
    answer: str
    simplified: str
    sources: list[str] = Field(default_factory=list)
    intent: str = "other"
    safety_passed: bool = True
    violation_type: str | None = None
    guide_latency_ms: int = 0
    simplifier_latency_ms: int = 0
    total_latency_ms: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    language: str = "en"


class SessionState(BaseModel):
    """
    Full session state for a single user conversation.

    Stored in Firestore under the 'sessions' collection.
    """

    session_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "anonymous"
    language: Literal["en", "hi", "mr", "ta"] = "en"
    turns: list[ChatTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    total_queries: int = 0
    total_blocked: int = 0

    def add_turn(self, turn: ChatTurn) -> None:
        """Append a new turn and update session counters."""
        self.turns.append(turn)
        self.total_queries += 1
        if not turn.safety_passed:
            self.total_blocked += 1
        self.updated_at = datetime.utcnow()

    @property
    def is_new(self) -> bool:
        """Return True if no turns have been recorded yet."""
        return len(self.turns) == 0

    @property
    def last_query(self) -> str | None:
        """Return the most recent user query, or None."""
        return self.turns[-1].query if self.turns else None

    def to_firestore_dict(self) -> dict:
        """Serialise to a Firestore-compatible dict (datetimes as ISO strings)."""
        return self.model_dump(mode="json")
