"""
tests/test_metrics.py
──────────────────────
Unit tests for the MetricsCollector.
"""

from __future__ import annotations

import pytest
from backend.utils.metrics import MetricsCollector, LatencyTracker


@pytest.fixture
def metrics() -> MetricsCollector:
    collector = MetricsCollector()
    return collector


class TestLatencyTracker:

    def test_initial_state(self) -> None:
        tracker = LatencyTracker()
        assert tracker.count == 0
        assert tracker.avg_ms == 0.0

    def test_record_updates_count(self) -> None:
        tracker = LatencyTracker()
        tracker.record(100.0)
        assert tracker.count == 1

    def test_record_updates_avg(self) -> None:
        tracker = LatencyTracker()
        tracker.record(100.0)
        tracker.record(200.0)
        assert tracker.avg_ms == 150.0

    def test_record_tracks_min_max(self) -> None:
        tracker = LatencyTracker()
        tracker.record(50.0)
        tracker.record(200.0)
        assert tracker.min_ms == 50.0
        assert tracker.max_ms == 200.0

    def test_to_dict_keys(self) -> None:
        tracker = LatencyTracker()
        tracker.record(100.0)
        d = tracker.to_dict()
        assert "count" in d
        assert "avg_ms" in d
        assert "min_ms" in d
        assert "max_ms" in d
        assert "total_ms" in d


class TestMetricsCollector:

    def test_initial_total_requests_zero(self, metrics: MetricsCollector) -> None:
        assert metrics.total_requests == 0

    def test_record_request_increments_total(self, metrics: MetricsCollector) -> None:
        metrics.record_request(
            intent="registration_inquiry",
            safety_passed=True,
            violation_type=None,
            guide_latency_ms=500,
            simplifier_latency_ms=200,
            pipeline_latency_ms=750,
        )
        assert metrics.total_requests == 1

    def test_record_blocked_request(self, metrics: MetricsCollector) -> None:
        metrics.record_request(
            intent="other",
            safety_passed=False,
            violation_type="endorsement",
            guide_latency_ms=0,
            simplifier_latency_ms=0,
            pipeline_latency_ms=10,
        )
        assert metrics.blocked_inbound == 1
        assert metrics.violation_counts["endorsement"] == 1

    def test_record_gemini_call_success(self, metrics: MetricsCollector) -> None:
        metrics.record_gemini_call(success=True)
        assert metrics.gemini_calls == 1
        assert metrics.gemini_errors == 0

    def test_record_gemini_call_failure(self, metrics: MetricsCollector) -> None:
        metrics.record_gemini_call(success=False)
        assert metrics.gemini_errors == 1

    def test_record_rag_vector_hit(self, metrics: MetricsCollector) -> None:
        metrics.record_rag_retrieval(vector_hit=True)
        assert metrics.rag_vector_hits == 1
        assert metrics.rag_web_fallbacks == 0

    def test_record_rag_web_fallback(self, metrics: MetricsCollector) -> None:
        metrics.record_rag_retrieval(vector_hit=False)
        assert metrics.rag_web_fallbacks == 1

    def test_snapshot_structure(self, metrics: MetricsCollector) -> None:
        snap = metrics.snapshot()
        assert "uptime_seconds" in snap
        assert "requests" in snap
        assert "gemini" in snap
        assert "rag" in snap
        assert "latency" in snap

    def test_snapshot_success_rate(self, metrics: MetricsCollector) -> None:
        metrics.record_request(
            intent="registration_inquiry",
            safety_passed=True,
            violation_type=None,
            guide_latency_ms=500,
            simplifier_latency_ms=200,
            pipeline_latency_ms=750,
        )
        snap = metrics.snapshot()
        assert snap["requests"]["success_rate"] == 100.0

    def test_intent_distribution_tracked(self, metrics: MetricsCollector) -> None:
        metrics.record_request(
            intent="registration_inquiry",
            safety_passed=True,
            violation_type=None,
            guide_latency_ms=300,
            simplifier_latency_ms=100,
            pipeline_latency_ms=450,
        )
        snap = metrics.snapshot()
        assert snap["intent_distribution"]["registration_inquiry"] == 1
