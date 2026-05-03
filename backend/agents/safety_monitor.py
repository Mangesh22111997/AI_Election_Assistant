"""
backend/agents/safety_monitor.py
──────────────────────────────────
Layer-5 Safety Monitor: validates agent output before it reaches the user.

Checks performed:
  1. Regex pattern matching for banned topics
  2. Required disclaimer presence
  3. Citation / source attribution
  4. Bias detection via Gemini (production only)
  5. PII detection
"""

from __future__ import annotations

import re
from typing import Final

from backend.config import get_settings
from backend.models.schemas import SafetyResult
from backend.models.safety_rules import SafetyRulesConfig
from backend.utils.logger import get_logger
from backend.utils.validators import contains_pii, sanitize_output

logger = get_logger(__name__)
settings = get_settings()

# ── Banned Patterns ───────────────────────────────────────────────────────────
BLOCKED_PATTERNS: Final[list[tuple[str, str]]] = [
    (r"vote\s+for\s+(the\s+)?(candidate|party|person|him|her|them)", "endorsement"),
    (r"(polling\s+place|location)\s+is\s+(best|worst|better|worse)", "opinion"),
    (r"illegal\s+to\s+vote", "voter_suppression"),
    (r"(you|your)\s+(SSN|social\s+security|bank\s+account|passport\s+number)", "pii_collection"),
    (r"(candidate|politician)\s+is\s+(corrupt|great|terrible|amazing|awful)", "political_bias"),
    (r"(don'?t|do\s+not)\s+vote", "voter_suppression"),
    (r"(rigged|stolen|fraudulent)\s+election", "misinformation"),
    (r"only\s+(democrat|republican|liberal|conservative)s?\s+"
     r"(can|should|must)\s+vote", "suppression"),
    (r"ignore\s+previous\s+instructions", "prompt_injection"),
]

REQUIRED_DISCLAIMERS: Final[list[str]] = [
    "AI-generated educational content",
    "verify with your local election office",
]




class SafetyMonitor:
    """
    Multi-layer output validator.

    Usage
    -----
    monitor = SafetyMonitor()
    result  = monitor.validate(agent_output="...", user_query="...")
    """

    def __init__(self) -> None:
        self._rules = SafetyRulesConfig.load()
        logger.info("SafetyMonitor initialised")

    # ── Public API ────────────────────────────────────────────────────────────

    def validate(self, agent_output: str, user_query: str) -> SafetyResult:
        """
        Run all safety checks on the agent output.

        Returns a SafetyResult with passed=True only if ALL checks clear.
        """
        violations: list[str] = []

        # Check 1: Regex pattern matching
        pattern_violation = self._check_patterns(agent_output)
        if pattern_violation:
            violations.append(f"banned_pattern:{pattern_violation}")

        # Check 2: Required disclaimers (Auto-inject if missing)
        if not self._has_required_disclaimers(agent_output):
            agent_output = self._inject_disclaimer(agent_output)

        # Check 3: Citation / source attribution
        if not self._has_citation(agent_output):
            violations.append("missing_source_attribution")

        # Check 4: PII detection
        if contains_pii(agent_output):
            violations.append("pii_detected")
            agent_output = sanitize_output(agent_output)

        # Check 5: Bias detection (Gemini-based, best-effort)
        if settings.is_production and not violations:
            if self._detect_bias_with_gemini(agent_output):
                violations.append("political_bias_detected")

        passed = len(violations) == 0
        if not passed:
            logger.warning(
                "Safety check FAILED",
                violations=violations,
                query_preview=user_query[:80],
            )
            self._log_violation(violations[0])
        else:
            logger.debug("Safety check PASSED")

        return SafetyResult(
            passed=passed,
            violations=violations,
            output=agent_output,
            violation_type=violations[0] if violations else None,
        )

    def validate_input(self, user_query: str) -> SafetyResult:
        """
        Pre-flight check on the raw user query (Layer 1 + 2).
        Called before sending the query to any agent.
        """
        violations: list[str] = []
        for pattern, label in BLOCKED_PATTERNS:
            if re.search(pattern, user_query, re.IGNORECASE):
                violations.append(f"input_banned_pattern:{label}")
                break

        passed = len(violations) == 0
        return SafetyResult(
            passed=passed,
            violations=violations,
            output=user_query,
            violation_type=violations[0] if violations else None,
        )

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _check_patterns(self, text: str) -> str | None:
        """Return the violation label if any banned pattern matches."""
        for pattern, label in BLOCKED_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return label
        return None

    def _has_citation(self, text: str) -> bool:
        """
        Check that the text contains at least one source citation.
        Citations can be [Source N:...] markers or explicit URL/doc references.
        """
        citation_patterns = [
            r"\[Source \d+",
            r"according to",
            r"source[:\s]",
            r"from the official",
            r"election\s+(manual|commission|office)",
            r"faq_dataset",
            r"https?://",
        ]
        return any(re.search(p, text, re.IGNORECASE) for p in citation_patterns)

    def _has_required_disclaimers(self, text: str) -> bool:
        """Check that the required disclaimer phrases are present."""
        text_lower = text.lower()
        return all(d.lower() in text_lower for d in REQUIRED_DISCLAIMERS)

    @staticmethod
    def _inject_disclaimer(text: str) -> str:
        """Append the required disclaimer if it's missing."""
        disclaimer = (
            "\n\n---\n"
            "🤖 **AI-generated educational content.** "
            "Always verify with your local election office before making decisions."
        )
        return text + disclaimer

    def _detect_bias_with_gemini(self, text: str) -> bool:
        """
        Use Gemini to detect subtle political bias.
        Returns True if bias is detected (response should be blocked).
        """
        try:
            from backend.services.gemini_service import get_gemini_service

            service = get_gemini_service()
            prompt = (
                "You are a political bias detector. "
                "Analyse the following text for any political bias, candidate preference, "
                "party promotion, or voter suppression language. "
                "Respond with ONLY 'BIASED' or 'NEUTRAL'.\n\n"
                f"Text:\n{text[:500]}"
            )
            result = service.generate(prompt, temperature_override=0.0)
            return "BIASED" in result.upper()
        except Exception as exc:
            logger.error("Gemini bias detection failed", error=str(exc))
            return False  # Fail-safe: don't block on error

    def _log_violation(self, violation: str) -> None:
        logger.warning("Policy violation logged", violation_type=violation)
