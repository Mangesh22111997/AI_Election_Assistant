"""
backend/utils/metrics.py
─────────────────────────
In-memory Prometheus-compatible performance counters.

Tracks:
  - Total requests served
  - Safety blocks (inbound + outbound)
  - Gemini API calls and latency
  - RAG retrieval hits vs. fallbacks
  - Intent distribution

Exposed via the /api/metrics endpoint for admin monitoring.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from threading import Lock
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class LatencyTracker:
    """Running statistics for operation latency."""

    count: int = 0
    total_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0

    def record(self, latency_ms: float) -> None:
        """Record a single latency measurement."""
        self.count += 1
        self.total_ms += latency_ms
        self.min_ms = min(self.min_ms, latency_ms)
        self.max_ms = max(self.max_ms, latency_ms)

    @property
    def avg_ms(self) -> float:
        """Return average latency in milliseconds."""
        return self.total_ms / self.count if self.count > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialise to JSON-compatible dict."""
        return {
            "count": self.count,
            "avg_ms": round(self.avg_ms, 1),
            "min_ms": round(self.min_ms, 1) if self.count > 0 else 0,
            "max_ms": round(self.max_ms, 1),
            "total_ms": round(self.total_ms, 1),
        }


class MetricsCollector:
    """
    Thread-safe in-memory metrics collector.

    Provides Prometheus-compatible counter/gauge/histogram semantics
    without requiring a Prometheus server.

    All methods are thread-safe via an internal Lock.
    """

    def __init__(self) -> None:
        self._lock = Lock()
        self._start_time = time.monotonic()

        # Request counters
        self.total_requests: int = 0
        self.blocked_inbound: int = 0
        self.blocked_outbound: int = 0

        # Gemini API counters
        self.gemini_calls: int = 0
        self.gemini_errors: int = 0

        # RAG counters
        self.rag_vector_hits: int = 0
        self.rag_web_fallbacks: int = 0

        # Intent distribution
        self.intent_counts: dict[str, int] = defaultdict(int)

        # Violation type distribution
        self.violation_counts: dict[str, int] = defaultdict(int)

        # Latency trackers
        self.guide_latency = LatencyTracker()
        self.simplifier_latency = LatencyTracker()
        self.pipeline_latency = LatencyTracker()

        logger.info("MetricsCollector initialised")

    def record_request(
        self,
        intent: str,
        safety_passed: bool,
        violation_type: str | None,
        guide_latency_ms: int,
        simplifier_latency_ms: int,
        pipeline_latency_ms: int,
    ) -> None:
        """Record a completed request with all associated metrics."""
        with self._lock:
            self.total_requests += 1

            if not safety_passed:
                self.blocked_inbound += 1
                if violation_type:
                    self.violation_counts[violation_type] += 1
            else:
                self.intent_counts[intent] += 1
                self.guide_latency.record(guide_latency_ms)
                self.simplifier_latency.record(simplifier_latency_ms)

            self.pipeline_latency.record(pipeline_latency_ms)

    def record_gemini_call(self, success: bool = True) -> None:
        """Record a Gemini API call outcome."""
        with self._lock:
            self.gemini_calls += 1
            if not success:
                self.gemini_errors += 1

    def record_rag_retrieval(self, vector_hit: bool) -> None:
        """Record whether RAG retrieval succeeded or fell back to web search."""
        with self._lock:
            if vector_hit:
                self.rag_vector_hits += 1
            else:
                self.rag_web_fallbacks += 1

    def snapshot(self) -> dict[str, Any]:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            uptime_seconds = int(time.monotonic() - self._start_time)
            return {
                "uptime_seconds": uptime_seconds,
                "requests": {
                    "total": self.total_requests,
                    "blocked_inbound": self.blocked_inbound,
                    "blocked_outbound": self.blocked_outbound,
                    "success_rate": (
                        round(
                            (self.total_requests - self.blocked_inbound)
                            / max(self.total_requests, 1)
                            * 100,
                            1,
                        )
                    ),
                },
                "gemini": {
                    "calls": self.gemini_calls,
                    "errors": self.gemini_errors,
                    "error_rate": round(
                        self.gemini_errors / max(self.gemini_calls, 1) * 100, 1
                    ),
                },
                "rag": {
                    "vector_hits": self.rag_vector_hits,
                    "web_fallbacks": self.rag_web_fallbacks,
                },
                "intent_distribution": dict(self.intent_counts),
                "violation_distribution": dict(self.violation_counts),
                "latency": {
                    "guide_agent_ms": self.guide_latency.to_dict(),
                    "simplifier_ms": self.simplifier_latency.to_dict(),
                    "pipeline_ms": self.pipeline_latency.to_dict(),
                },
            }

    def reset(self) -> None:
        """Reset all counters (for testing)."""
        with self._lock:
            self.__init__()  # type: ignore[misc]


# ── Module-level singleton ────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_metrics() -> MetricsCollector:
    """Return the cached singleton MetricsCollector instance."""
    return MetricsCollector()
