"""
tests/unit/test_property_safety.py
───────────────────────────────────
Property-based testing for the Safety Monitor using Hypothesis.
Verifies that the monitor handles ANY string input without crashing.
"""

import pytest
from hypothesis import given, strategies as st, settings
from backend.agents.safety_monitor import SafetyMonitor

@pytest.fixture
def monitor():
    return SafetyMonitor()

@settings(max_examples=50, deadline=None)
@given(st.text(min_size=0, max_size=1000))
def test_safety_monitor_robustness(monitor, text):
    """
    Property: The Safety Monitor must handle ANY string without raising an exception.
    This includes empty strings, massive strings, and strange unicode/emoji.
    """
    try:
        # We test the core validation logic
        # We pass a dummy user_query
        result = monitor.validate(agent_output=text, user_query="How do I vote?")
        
        assert result.passed in [True, False]
        assert isinstance(result.output, str)
    except Exception as exc:
        pytest.fail(f"SafetyMonitor crashed on input: {text!r} with error: {exc}")

@settings(max_examples=50, deadline=None)
@given(st.text(min_size=0, max_size=500))
def test_pii_detection_robustness(monitor, text):
    """
    Property: PII detection should be stable across all inputs.
    """
    from backend.utils.validators import contains_pii
    try:
        result = contains_pii(text)
        assert isinstance(result, bool)
    except Exception as exc:
        pytest.fail(f"PII validator crashed on input: {text!r} with error: {exc}")

if __name__ == "__main__":
    pytest.main([__file__])
