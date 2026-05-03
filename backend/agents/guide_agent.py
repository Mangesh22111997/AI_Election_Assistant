"""
backend/agents/guide_agent.py
───────────────────────────────
Guide Agent – provides structured, step-by-step election procedures.

Pipeline:
  1. Classify intent (deadline / ID / location / procedure / other)
  2. Retrieve relevant context via RAG (GroundingTool)
  3. Optionally enrich with live Google Custom Search results
  4. Generate a step-by-step response using Gemini
  5. Return structured dict: {steps, sources, intent, latency_ms}
"""

from __future__ import annotations

import time
from typing import Any

from backend.config import get_settings
from backend.models.schemas import Intent
from backend.services.gemini_service import get_gemini_service
from backend.services.grounding_tool import get_grounding_tool
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Intent Classifier ─────────────────────────────────────────────────────────

INTENT_KEYWORDS: dict[Intent, list[str]] = {
    "deadline_inquiry": [
        "deadline", "due date", "last day", "cut-off", "cutoff", "by when",
    ],
    "registration_inquiry": [
        "register", "registration", "sign up", "enroll", "enrolled",
    ],
    "polling_location": [
        "polling place", "polling station", "where do i vote", "voting location",
        "find my polling",
    ],
    "id_requirements": [
        "id", "identification", "photo id", "driver's license", "passport",
        "proof of identity",
    ],
    "mail_in_voting": [
        "mail-in", "absentee", "vote by mail", "mail ballot", "postal vote",
    ],
    "voting_procedure": [
        "how to vote", "voting process", "steps to vote", "cast my ballot",
        "in-person voting",
    ],
    "result_timeline": [
        "when are results", "election results", "vote count", "tally",
        "when will we know",
    ],
    "general_election": [
        "general election", "midterm", "primary election", "election day",
    ],
}

GUIDE_SYSTEM_INSTRUCTION = """
You are an expert, neutral election guidance officer.
Your role is to provide accurate, step-by-step information about election procedures.

Critical rules:
- ONLY use the provided context documents – never fabricate information
- Present information as clear, numbered steps
- Cite your source after each claim using [Source N] notation
- If the context does not contain enough information, say so explicitly
- Never express political opinions or mention candidates / parties
- Always recommend verifying with local officials for jurisdiction-specific details
- Temperature is set to 0.2 – stay factual and precise
""".strip()

GUIDE_PROMPT_TEMPLATE = """
User Question: {query}

Classified Intent: {intent}

Retrieved Context:
{context}

Please provide a clear, step-by-step answer citing the sources above.
End your response with the official disclaimer.
"""


class GuideAgent:
    """
    CrewAI-style guide agent for election procedure queries.

    Usage
    -----
    agent  = GuideAgent()
    result = agent.process_query("How do I register to vote?")
    # result → {"answer": str, "sources": list[str], "intent": str, "latency_ms": int}
    """

    def __init__(self) -> None:
        self._gemini = get_gemini_service()
        self._grounding = get_grounding_tool()
        logger.info("GuideAgent ready")

    # ── Public API ────────────────────────────────────────────────────────────

    def process_query(self, query: str) -> dict[str, Any]:
        """
        Full pipeline: classify → retrieve → generate → return.

        Returns
        -------
        dict with keys: answer, sources, intent, latency_ms
        """
        start = time.monotonic()

        # Step 1: Classify intent
        intent: Intent = self.classify_intent(query)
        logger.debug("Intent classified", intent=intent)

        # Step 2: Retrieve context from RAG
        retrieved = self._grounding.retrieve(query)

        # Step 3: Enrich with live search for deadline queries
        if intent == "deadline_inquiry":
            live = self._grounding.live_search(query)
            retrieved = live + retrieved  # prefer live data for deadlines

        # Step 4: Format context and generate response
        context_str = self._grounding.format_context(retrieved)
        prompt = GUIDE_PROMPT_TEMPLATE.format(
            query=query,
            intent=intent,
            context=context_str,
        )

        try:
            answer = self._gemini.generate(
                prompt=prompt,
                system_instruction=GUIDE_SYSTEM_INSTRUCTION,
            )
        except Exception as exc:
            logger.error("GuideAgent generation failed", error=str(exc))
            answer = (
                "I was unable to retrieve specific information for your query. "
                "Please contact your local election office directly for accurate guidance."
            )

        sources = [item["source"] for item in retrieved]
        latency_ms = int((time.monotonic() - start) * 1000)

        logger.debug("GuideAgent completed", latency_ms=latency_ms, intent=intent)
        return {
            "answer": answer,
            "sources": list(dict.fromkeys(sources)),  # unique, ordered
            "intent": intent,
            "latency_ms": latency_ms,
        }

    def classify_intent(self, query: str) -> Intent:
        """Classify the user query into one of the predefined Intent categories."""
        query_lower = query.lower()
        for intent, keywords in INTENT_KEYWORDS.items():
            if any(kw in query_lower for kw in keywords):
                return intent
        return "other"
