"""
backend/agents/simplifier_agent.py
────────────────────────────────────
Simplifier Agent – converts legal / policy language
into plain, accessible text (≈ 6th-grade reading level).
Powered by Gemini Flash with a strict non-hallucination prompt.
"""

from __future__ import annotations

import re
import time

from backend.config import get_settings
from backend.services.gemini_service import get_gemini_service
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

SYSTEM_INSTRUCTION = """
You are a voter education assistant specialising in plain-language communication.
Your ONLY job is to simplify the provided technical text – do NOT add new information.

Strict rules:
- Use simple language (6th-grade reading level)
- Format as bullet points for easy scanning
- Add a real-world example where genuinely helpful
- Mark key takeaways with 📌
- Never mention candidates, parties, or political opinions
- NEVER add facts not present in the source text
- ALWAYS preserve source citations like [Source 1], [Source 2], etc.
- Always end with: "🤖 AI-generated educational content. Always verify with your local "
- "election office."
""".strip()

PROMPT_TEMPLATE = """
Convert the following technical election text into simplified, accessible language.

Technical Text:
{technical_text}

Simplified Version:
"""


class SimplifierAgent:
    """
    Converts technical / legal election language into plain text.

    Usage
    -----
    agent  = SimplifierAgent()
    simple = agent.simplify("You must present a government-issued photo ID at the polls...")
    """

    def __init__(self) -> None:
        self._gemini = get_gemini_service()
        logger.info("SimplifierAgent ready")

    def simplify(self, technical_text: str) -> tuple[str, int]:
        """
        Simplify the provided technical text.

        Returns
        -------
        (simplified_text, latency_ms)
        """
        if not technical_text or not technical_text.strip():
            return "No content provided to simplify.", 0

        prompt = PROMPT_TEMPLATE.format(technical_text=technical_text[:3_000])
        start = time.monotonic()

        try:
            result = self._gemini.generate(
                prompt=prompt,
                system_instruction=SYSTEM_INSTRUCTION,
            )
        except Exception as exc:
            logger.error("SimplifierAgent failed", error=str(exc))
            result = technical_text  # Fall back to original text

        latency_ms = int((time.monotonic() - start) * 1000)
        logger.debug("SimplifierAgent completed", latency_ms=latency_ms)
        return result, latency_ms

    def _flesch_kincaid_grade(self, text: str) -> float:
        """Calculate Flesch-Kincaid Grade Level without external library."""
        sentences = max(1, len(re.split(r'[.!?]+', text)))
        words = text.split()
        word_count = max(1, len(words))

        def syllable_count(word: str) -> int:
            word = word.lower().strip(".,!?;:")
            if not word:
                return 1
            vowels = re.findall(r'[aeiou]+', word)
            count = len(vowels)
            if word.endswith('e') and count > 1:
                count -= 1
            return max(1, count)

        total_syllables = sum(syllable_count(w) for w in words)
        grade = 0.39 * (word_count / sentences) + 11.8 * (total_syllables / word_count) - 15.59
        return round(grade, 1)

    def reading_level_label(self, text: str) -> str:
        """Return a human-readable label for the current reading level."""
        grade = self._flesch_kincaid_grade(text)
        if grade <= 6:   return "Easy to Read"
        if grade <= 8:   return "Moderate"
        if grade <= 12:  return "Advanced"
        return "Complex"
