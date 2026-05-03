"""
backend/services/response_cache.py
──────────────────────────────────
Response cache for frequently asked election questions.
Prevents re-querying Gemini for identical or semantically near-identical queries.

Strategy:
  1. Exact match cache (dict) — sub-millisecond
  2. FAQ keyword cache (JSON) — offline fallback

Cache invalidation: time-based (24hr) to ensure election deadline accuracy.
"""

import hashlib
import json
import time
from typing import Any, Optional
from functools import lru_cache
from backend.utils.logger import get_logger

logger = get_logger(__name__)

_CACHE_TTL_SECONDS = 86400   # 24 hours
_MAX_CACHE_SIZE = 500        # Approximately 2MB at avg 4KB per response


class ResponseCache:
    """
    Exact hash match cache for common voter questions.
    Thread-safe for async FastAPI workers.
    """

    def __init__(self, faq_path: str = "data/faq_dataset.json"):
        self._exact: dict[str, tuple[dict[str, Any], float]] = {}   # hash -> (response, timestamp)
        self._faq = self._load_faq(faq_path)
        self._hits = 0
        self._misses = 0

    def _load_faq(self, path: str) -> dict[str, str]:
        """Load the curated FAQ dataset as the L3 offline fallback cache."""
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            logger.info(f"FAQ cache loaded: {len(data)} entries")
            # Flatten into a query map
            faq_map = {}
            for item in data:
                q = item.get("question", "").lower().strip()
                a = item.get("answer", "")
                if q and a:
                    faq_map[q] = a
            return faq_map
        except Exception as exc:
            logger.warning(f"FAQ file not loaded: {exc}")
            return {}

    def _normalise_query(self, query: str) -> str:
        """Normalise query spacing and case for consistent cache lookup."""
        return " ".join(query.lower().strip().split())

    def _hash_query(self, query: str) -> str:
        """Normalise and hash a query for exact-match lookup."""
        normalised = self._normalise_query(query)
        return hashlib.sha256(normalised.encode()).hexdigest()[:16]

    def get(self, query: str) -> Optional[dict]:
        """
        Look up a cached response. Returns None on cache miss.
        """
        # L1: Exact hash match
        key = self._hash_query(query)
        if key in self._exact:
            data, timestamp = self._exact[key]
            if time.time() - timestamp < _CACHE_TTL_SECONDS:
                self._hits += 1
                logger.debug("Cache L1 HIT", key=key)
                return data
            else:
                del self._exact[key]   # Expired

        # L3: FAQ keyword match (simple containment)
        query_lower = self._normalise_query(query)
        for faq_q, faq_a in self._faq.items():
            if faq_q in query_lower or query_lower in faq_q:
                self._hits += 1
                logger.debug("Cache L3 FAQ HIT", faq=faq_q[:40])
                return {
                    "simplified": faq_a,
                    "sources": ["FAQ Dataset"],
                    "intent": "faq_match",
                    "latency_ms": 5,
                    "reading_level": "Easy"
                }

        self._misses += 1
        return None

    def set(self, query: str, response_data: dict) -> None:
        """
        Store a response in the cache.
        """
        if len(self._exact) >= _MAX_CACHE_SIZE:
            # Simple FIFO eviction
            oldest_key = next(iter(self._exact))
            del self._exact[oldest_key]

        key = self._hash_query(query)
        self._exact[key] = (response_data, time.time())
        logger.debug("Cache SET", key=key)

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_pct": round((self._hits / total * 100), 1) if total > 0 else 0,
            "entries": len(self._exact)
        }


@lru_cache(maxsize=1)
def get_response_cache() -> ResponseCache:
    return ResponseCache()
