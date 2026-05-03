"""
backend/models/schemas.py
────────────────────────────
Pydantic models for API request/response validation
and for Firestore conversation persistence.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


# ── Enumerations ─────────────────────────────────────────────────────────────

Role = Literal["user", "assistant", "system"]
Intent = Literal[
    "deadline_inquiry",
    "registration_inquiry",
    "polling_location",
    "id_requirements",
    "mail_in_voting",
    "voting_procedure",
    "result_timeline",
    "general_election",
    "other",
    "faq_match"
]


# ── Message Models ────────────────────────────────────────────────────────────

class ChatTurn(BaseModel):
    """A single turn in a conversation."""

    role: Role
    content: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    intent: Intent | None = None
    sources: list[str] = Field(default_factory=list)
    safety_check_passed: bool = True
    latency_ms: int = 0


class ConversationRecord(BaseModel):
    """Full conversation record stored in Firestore."""

    conversation_id: str = Field(default_factory=lambda: str(uuid4()))
    user_id: str = "anonymous"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    messages: list[ChatTurn] = Field(default_factory=list)
    safety_flags: list[str] = Field(default_factory=list)
    session_duration_seconds: int = 0
    clarification_count: int = 0

    def add_message(self, message: ChatTurn) -> None:
        self.messages.append(message)
        self.updated_at = datetime.now(timezone.utc)

    def to_firestore_dict(self) -> dict:
        """Serialise to a Firestore-compatible dict."""
        return self.model_dump(mode="json")


# ── API Request / Response Models ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Incoming request body for POST /api/chat."""

    query: str = Field(
        ...,
        min_length=3,
        max_length=500,  # Prevents long-input prompt injection
        description="The user's election-related question",
        examples=["When is the voter registration deadline?"],
    )
    conversation_id: str | None = Field(
        default=None,
        min_length=8,
        max_length=64,
        pattern=r'^[a-zA-Z0-9_-]+$',  # Alphanumeric only
        description="Existing conversation ID for multi-turn context",
    )
    user_id: str = Field(
        default="anonymous",
        max_length=64,
        description="Firebase UID or 'anonymous'",
    )
    language: str = Field(
        default="en",
        pattern=r'^(en|hi|mr|ta)$',  # Whitelist of supported languages
        description="ISO 639-1 language code for the response",
    )

    @field_validator("query")
    @classmethod
    def no_script_injection(cls, v: str) -> str:
        """Block basic XSS/HTML injection in queries."""
        suspicious = ["<script", "javascript:", "data:text/html", "onclick="]
        v_lower = v.lower()
        for pattern in suspicious:
            if pattern in v_lower:
                raise ValueError("Query contains disallowed content (script injection attempt)")
        return v.strip()


class SourceItem(BaseModel):
    """A single source citation with provenance."""
    document: str
    page: int = 0
    url: str | None = None
    score: float | None = None


class AgentResponse(BaseModel):
    """Structured response from the agent pipeline."""
    answer: str
    simplified: str
    sources: list[SourceItem] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)
    intent: Intent = "other"
    safety_passed: bool = True
    disclaimer: str = (
        "🤖 AI-generated educational content. "
        "Always verify with your local election office."
    )
    latency_ms: int = 0
    reading_level: str = ""
    cache_hit: bool = False


class ChatResponse(BaseModel):
    """Response body returned by POST /api/chat."""

    conversation_id: str
    message: AgentResponse
    clarification_attempts_remaining: int = 3


class HealthResponse(BaseModel):
    """Response body for GET /health."""

    status: str = "ok"
    version: str = "2.0.0"
    environment: str
    gemini_model: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, str] = Field(default_factory=dict)


class FeedbackRequest(BaseModel):
    """User thumbs-up / thumbs-down feedback."""

    conversation_id: str
    message_index: int = Field(..., ge=0)
    feedback: Literal["helpful", "not_helpful", "inaccurate"]
    comment: str | None = Field(default=None, max_length=500)


class SafetyResult(BaseModel):
    """Result of a safety validation pass."""

    passed: bool
    violations: list[str] = Field(default_factory=list)
    output: str = ""      # potentially sanitised output
    violation_type: str | None = None
