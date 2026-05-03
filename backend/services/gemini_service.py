"""
backend/services/gemini_service.py
────────────────────────────────────
Wrapper around the Google Generative AI SDK.
Provides async inference with retry logic, temperature enforcement,
and usage tracking.
"""

from __future__ import annotations

import time
from typing import Any

import google.generativeai as genai
from tenacity import (
    RetryError,
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Configure Gemini SDK once at import time
genai.configure(api_key=settings.google_api_key)

_SAFETY_SETTINGS = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

_GENERATION_CONFIG = genai.GenerationConfig(
    temperature=settings.gemini_temperature,        # 0.2 – factual accuracy
    max_output_tokens=settings.gemini_max_output_tokens,
    top_p=0.9,
    top_k=40,
)


class GeminiService:
    """
    Singleton service for Gemini Flash inference.

    Usage
    -----
    service = GeminiService()
    result  = service.generate(prompt="...", system_instruction="...")
    """

    def __init__(self) -> None:
        self._model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config=_GENERATION_CONFIG,
            safety_settings=_SAFETY_SETTINGS,
        )
        self._usage: dict[str, int] = {"requests": 0, "tokens": 0}
        logger.info(
            "GeminiService initialised",
            model=settings.gemini_model,
            temperature=settings.gemini_temperature,
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_instruction: str | None = None,
        temperature_override: float | None = None,
    ) -> str:
        """
        Generate a response from Gemini.

        Parameters
        ----------
        prompt              : The user-facing prompt.
        system_instruction  : Optional system-level instruction injected before the prompt.
        temperature_override: Temporarily override the default temperature.
        """
        full_prompt = self._build_prompt(prompt, system_instruction)
        start = time.monotonic()

        try:
            response = self._call_with_retry(full_prompt, temperature_override)
        except RetryError as exc:
            logger.error("Gemini call failed after retries", error=str(exc))
            raise RuntimeError("Gemini API is currently unavailable. Please try again.") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        self._usage["requests"] += 1

        text = self._extract_text(response)
        logger.debug("Gemini response received", latency_ms=elapsed_ms, chars=len(text))
        return text

    def chat(self, history: list[dict[str, str]], new_message: str) -> str:
        """
        Multi-turn chat with conversation history.

        Parameters
        ----------
        history     : List of {"role": "user"|"model", "parts": "..."} dicts.
        new_message : The latest user message.
        """
        chat_session = self._model.start_chat(history=history)
        try:
            response = chat_session.send_message(new_message)
        except Exception as exc:
            logger.error("Gemini chat error", error=str(exc))
            raise

        return self._extract_text(response)

    @property
    def usage(self) -> dict[str, int]:
        return dict(self._usage)

    @property
    def api_key(self) -> str:
        """Return the configured API key (masked for security)."""
        key = settings.google_api_key
        return f"{key[:8]}...{key[-4:]}" if len(key) > 12 else "[configured]"

    @property
    def is_configured(self) -> bool:
        """Return True if the API key is set and valid."""
        key = settings.google_api_key
        return bool(key and key != "your_gemini_api_key_here")

    # ── Private Helpers ───────────────────────────────────────────────────────

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _call_with_retry(
        self, prompt: str, temperature_override: float | None
    ) -> Any:
        if temperature_override is not None:
            config = genai.GenerationConfig(
                temperature=temperature_override,
                max_output_tokens=settings.gemini_max_output_tokens,
            )
            return self._model.generate_content(prompt, generation_config=config)
        return self._model.generate_content(prompt)

    @staticmethod
    def _build_prompt(prompt: str, system_instruction: str | None) -> str:
        if system_instruction:
            return f"{system_instruction}\n\n---\n\n{prompt}"
        return prompt

    @staticmethod
    def _extract_text(response: Any) -> str:
        """Safely extract text from a GenerateContentResponse."""
        try:
            return response.text
        except (AttributeError, ValueError):
            # Response may be blocked by safety filters
            return (
                "I'm unable to respond to that question. "
                "Please contact your local election office for assistance."
            )


# ── Module-level singleton ────────────────────────────────────────────────────
_gemini_service: GeminiService | None = None


def get_gemini_service() -> GeminiService:
    """Return the module-level GeminiService singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
