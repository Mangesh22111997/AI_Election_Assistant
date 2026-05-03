"""
backend/agents/orchestrator.py
────────────────────────────────
Multi-Agent Pipeline Coordinator.
Responsible for orchestrating the flow between Guide, Simplifier,
and Safety Monitor agents.

Pipeline:
  1. PII scrubbing + input sanitisation
  2. Safety check (inbound) — SafetyMonitor.validate_input()
  3. Guide Agent — RAG retrieval + Gemini generation
  4. Simplifier Agent — 6th-grade plain language
  5. Safety check (outbound) — SafetyMonitor.validate()
  6. Final response assembly
"""

from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentState(Enum):
    """Lifecycle states for the orchestration pipeline."""
    INITIALIZED = "initialized"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class PipelineContext:
    """Immutable context object passed through each pipeline stage."""
    user_query: str
    sanitized_query: str
    detected_language: str
    intent: str | None = None
    retrieved_context: str | None = None
    guide_response: str | None = None
    simplified_response: str | None = None
    safety_checks_passed: bool = False
    final_response: str | None = None
    sources: list = field(default_factory=list)
    latency_ms: int = 0


class OrchestratorAgent:
    """
    Coordinates the multi-agent pipeline for election query processing.

    Agents orchestrated:
      - SafetyMonitor: inbound (query) + outbound (response) validation
      - GuideAgent: RAG retrieval + grounded Gemini generation
      - SimplifierAgent: 6th-grade plain-language conversion

    Usage
    -----
    orchestrator = OrchestratorAgent(guide_agent, simplifier_agent, safety_monitor)
    result = await orchestrator.process("How do I register to vote?")
    """

    def __init__(
        self,
        guide_agent: Any,
        simplifier_agent: Any,
        safety_monitor: Any,
    ) -> None:
        self.guide_agent = guide_agent
        self.simplifier_agent = simplifier_agent
        self.safety_monitor = safety_monitor
        self.state = AgentState.INITIALIZED

    async def process(
        self,
        user_query: str,
        language: str = "en",
    ) -> dict[str, Any]:
        """
        Execute the full multi-agent pipeline.

        Parameters
        ----------
        user_query : Raw user input string
        language   : BCP-47 language code for the response

        Returns
        -------
        dict with keys: response, sources, intent, latency_ms,
                        safety_blocked, violation_type, language
        """
        start_time = time.monotonic()
        self.state = AgentState.PROCESSING

        context = PipelineContext(
            user_query=user_query,
            sanitized_query=self._sanitize_input(user_query),
            detected_language=language,
        )

        # ── Stage 1: Inbound safety check ─────────────────────────────────────
        inbound_result = self.safety_monitor.validate_input(context.sanitized_query)
        if not inbound_result.passed:
            self.state = AgentState.BLOCKED
            return {
                "response": (
                    "I cannot answer that question because it falls outside "
                    "election procedure guidance. I'm here to help with voter "
                    "registration, ID requirements, and how to cast your ballot."
                ),
                "sources": [],
                "safety_blocked": True,
                "violation_type": inbound_result.violation_type,
                "intent": "other",
                "latency_ms": int((time.monotonic() - start_time) * 1000),
            }

        # ── Stage 2: Guide Agent (RAG + Gemini) ────────────────────────────────
        guide_result = await asyncio.to_thread(
            self.guide_agent.process_query,
            context.sanitized_query,
        )
        context.intent = guide_result.get("intent", "other")
        context.guide_response = guide_result.get("answer", "")
        context.sources = guide_result.get("sources", [])

        # ── Stage 3: Simplifier Agent ─────────────────────────────────────────
        if self._needs_simplification(context.guide_response):
            simplified_text, _ = await asyncio.to_thread(
                self.simplifier_agent.simplify,
                context.guide_response,
            )
            context.simplified_response = simplified_text
        else:
            context.simplified_response = context.guide_response

        # ── Stage 4: Outbound safety check ────────────────────────────────────
        outbound_result = self.safety_monitor.validate(
            agent_output=context.simplified_response,
            user_query=context.user_query,
        )
        if not outbound_result.passed:
            self.state = AgentState.BLOCKED
            return {
                "response": (
                    "I apologize — my response was flagged by safety filters. "
                    "Please rephrase your question or contact the Voter Helpline: 1950."
                ),
                "sources": [],
                "safety_blocked": True,
                "violation_type": outbound_result.violation_type,
                "intent": context.intent,
                "latency_ms": int((time.monotonic() - start_time) * 1000),
            }

        # ── Stage 5: Final assembly ────────────────────────────────────────────
        context.final_response = outbound_result.output  # May include injected disclaimer
        context.safety_checks_passed = True
        context.latency_ms = int((time.monotonic() - start_time) * 1000)
        self.state = AgentState.COMPLETED

        return {
            "response": context.final_response,
            "sources": context.sources,
            "intent": context.intent,
            "latency_ms": context.latency_ms,
            "safety_blocked": False,
            "violation_type": None,
            "language": language,
        }

    # ── Private helpers ────────────────────────────────────────────────────────

    def _sanitize_input(self, query: str) -> str:
        """
        Remove PII patterns and enforce length limit before processing.
        This is a first-pass scrub — SafetyMonitor does a full PII check later.
        """
        pii_patterns = [
            (r"\b\d{12}\b", "[AADHAAR-REDACTED]"),
            (r"\b\d{10}\b", "[PHONE-REDACTED]"),
            (r"\b[A-Z]{3}[A-Z0-9]{4}[A-Z]{1}\b", "[VOTER-ID-REDACTED]"),
            (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[EMAIL-REDACTED]"),
        ]
        sanitized = query
        for pattern, replacement in pii_patterns:
            sanitized = re.sub(pattern, replacement, sanitized)
        return sanitized[:500]   # Hard length cap — matches ChatRequest.query max_length

    def _needs_simplification(self, text: str) -> bool:
        """
        Heuristic: simplify if average words-per-sentence > 20 or total length > 300.
        The SimplifierAgent's Flesch-Kincaid check provides finer-grained assessment.
        """
        if not text:
            return False
        sentence_count = max(text.count(".") + text.count("!") + text.count("?"), 1)
        words_per_sentence = len(text.split()) / sentence_count
        return words_per_sentence > 20 or len(text) > 300

    def _add_disclaimer(self, response: str) -> str:
        """
        Append mandatory policy disclaimer.
        Note: SafetyMonitor._inject_disclaimer() also does this as a fallback.
        This method kept for backwards compatibility.
        """
        disclaimer = (
            "\n\n---\n"
            "🤖 *AI-generated educational content. "
            "Always verify with your local election office.*"
        )
        return response + disclaimer
