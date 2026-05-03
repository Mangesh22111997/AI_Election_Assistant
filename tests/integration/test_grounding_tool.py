"""
tests/test_grounding_tool.py
──────────────────────────────
Unit tests for the GroundingTool.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.services.grounding_tool import GroundingTool


@pytest.fixture
def mock_grounding() -> GroundingTool:
    tool = GroundingTool()
    tool._collection = MagicMock()
    return tool


class TestGroundingTool:

    def test_retrieve_calls_vector_search(self, mock_grounding: GroundingTool) -> None:
        mock_grounding._vector_search = MagicMock(return_value=[{"content": "a", "source": "s", "score": "1.0"}])
        mock_grounding._faq_search = MagicMock(return_value=[])
        results = mock_grounding.retrieve("test query")
        assert len(results) == 1
        assert results[0]["content"] == "a"

    def test_retrieve_calls_faq_search(self, mock_grounding: GroundingTool) -> None:
        mock_grounding._vector_search = MagicMock(return_value=[])
        mock_grounding._faq_search = MagicMock(return_value=[{"content": "b", "source": "s", "score": "1.0"}])
        results = mock_grounding.retrieve("test query")
        assert len(results) == 1
        assert results[0]["content"] == "b"

    def test_retrieve_deduplicates(self, mock_grounding: GroundingTool) -> None:
        mock_grounding._vector_search = MagicMock(return_value=[{"content": "duplicate", "source": "s", "score": "1.0"}])
        mock_grounding._faq_search = MagicMock(return_value=[{"content": "duplicate", "source": "f", "score": "0.8"}])
        results = mock_grounding.retrieve("test query")
        assert len(results) == 1
        assert results[0]["content"] == "duplicate"
        assert results[0]["source"] == "s" # Kept the first one

    def test_format_context_empty(self, mock_grounding: GroundingTool) -> None:
        context = mock_grounding.format_context([])
        assert "No specific documents" in context

    def test_format_context_with_results(self, mock_grounding: GroundingTool) -> None:
        context = mock_grounding.format_context([{"content": "Test data", "source": "Test Source"}])
        assert "Source 1: Test Source" in context
        assert "Test data" in context

    @patch("backend.services.grounding_tool.requests.get")
    def test_live_search_no_api_key(self, mock_get, mock_grounding: GroundingTool) -> None:
        with patch("backend.services.grounding_tool.settings.google_cse_api_key", ""):
            results = mock_grounding.live_search("query")
            assert len(results) == 0
            mock_get.assert_not_called()

    @patch("backend.services.grounding_tool.requests.get")
    def test_live_search_success(self, mock_get, mock_grounding: GroundingTool) -> None:
        with patch("backend.services.grounding_tool.settings.google_cse_api_key", "test_key"), \
             patch("backend.services.grounding_tool.settings.google_cse_id", "test_id"):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"items": [{"title": "Test Title", "snippet": "Test Snippet", "link": "http://test"}]}
            mock_get.return_value = mock_resp
            
            results = mock_grounding.live_search("query")
            assert len(results) == 1
            assert "Test Title: Test Snippet" in results[0]["content"]

    @patch("backend.services.grounding_tool.requests.get")
    def test_live_search_exception(self, mock_get, mock_grounding: GroundingTool) -> None:
        with patch("backend.services.grounding_tool.settings.google_cse_api_key", "test_key"), \
             patch("backend.services.grounding_tool.settings.google_cse_id", "test_id"):
            mock_get.side_effect = Exception("Test Exception")
            results = mock_grounding.live_search("query")
            assert len(results) == 0

    def test_vector_search_exception(self, mock_grounding: GroundingTool) -> None:
        mock_grounding._collection.query.side_effect = Exception("Test Error")
        results = mock_grounding._vector_search("test", 1, 0.5)
        assert len(results) == 0
