"""
backend/utils/validators.py
────────────────────────────
Input / output validation helpers.
Guards against prompt-injection, PII leakage, and oversized payloads.
"""

from __future__ import annotations

import re
from typing import Final

# ── Constants ─────────────────────────────────────────────────────────────────
MAX_QUERY_LENGTH: Final[int] = 1_000   # characters
MIN_QUERY_LENGTH: Final[int] = 3

# Patterns considered prompt-injection attempts
INJECTION_PATTERNS: Final[list[str]] = [
    r"ignore\s+(previous|all|above)\s+instructions?",
    r"(you\s+are\s+now|act\s+as|pretend\s+(you\s+are|to\s+be))",
    r"forget\s+(your|all)\s+(safety|guidelines?|rules?|instructions?)",
    r"disregard\s+(the\s+above|previous|all)\s+",
    r"system\s+prompt",
    r"<\|.*?\|>",  # special tokens
    r"\[\[.*?\]\]",  # double bracket injection
]

# Patterns that indicate PII in a response (should be scrubbed)
PII_PATTERNS: Final[list[str]] = [
    r"\b\d{3}-\d{2}-\d{4}\b",           # SSN
    r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",  # credit card
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
    r"\b(\+\d{1,3}[- ]?)?\d{10}\b",     # phone numbers
]


def validate_user_query(query: str) -> tuple[bool, str]:
    """
    Validate a raw user query.

    Returns
    -------
    (is_valid, reason)
        is_valid – True if the query passes all checks
        reason   – human-readable rejection message (empty string when valid)
    """
    if not query or not query.strip():
        return False, "Query cannot be empty."

    stripped = query.strip()

    if len(stripped) < MIN_QUERY_LENGTH:
        return False, f"Query is too short (minimum {MIN_QUERY_LENGTH} characters)."

    if len(stripped) > MAX_QUERY_LENGTH:
        return False, (
            f"Query exceeds the maximum allowed length of {MAX_QUERY_LENGTH} characters."
        )

    # Prompt-injection detection
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return False, (
                "Your message appears to contain instructions that override the assistant. "
                "Please ask a genuine election-related question."
            )

    return True, ""


def sanitize_output(text: str) -> str:
    """
    Scrub PII from an agent response before it reaches the user.
    Replaces detected PII with a placeholder.
    """
    for pattern in PII_PATTERNS:
        text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
    return text


def contains_pii(text: str) -> bool:
    """Return True if the text contains any PII pattern."""
    return any(
        re.search(p, text, re.IGNORECASE) for p in PII_PATTERNS
    )


def is_election_related(query: str) -> bool:
    """
    Lightweight heuristic check: does the query mention election topics?
    Used as a pre-filter before calling the agent.
    """
    election_keywords = [
        "vote", "voting", "voter", "election", "ballot", "polling",
        "register", "registration", "candidate", "campaign", "primary",
        "general election", "mail-in", "absentee", "id", "identification",
        "deadline", "polling place", "polling station", "election day",
        "early voting", "provisional ballot", "electoral", "poll",
    ]
    lower = query.lower()
    return any(kw in lower for kw in election_keywords)
