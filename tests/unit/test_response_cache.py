from __future__ import annotations

import json

from backend.services.response_cache import ResponseCache


def test_hash_query_ignores_extra_internal_spacing(tmp_path) -> None:
    faq = tmp_path / "faq.json"
    faq.write_text(json.dumps([]), encoding="utf-8")
    cache = ResponseCache(faq_path=str(faq))

    key1 = cache._hash_query("Where   do I vote?")
    key2 = cache._hash_query("where do i vote?")

    assert key1 == key2


def test_get_returns_cached_item_for_spacing_variants(tmp_path) -> None:
    faq = tmp_path / "faq.json"
    faq.write_text(json.dumps([]), encoding="utf-8")
    cache = ResponseCache(faq_path=str(faq))

    payload = {"simplified": "Use your state portal."}
    cache.set("Where   do I vote?", payload)

    assert cache.get("where do i vote?") == payload


def test_faq_match_uses_normalized_query(tmp_path) -> None:
    faq = tmp_path / "faq.json"
    faq.write_text(
        json.dumps([
            {"question": "where do i vote", "answer": "Check your county office."}
        ]),
        encoding="utf-8",
    )
    cache = ResponseCache(faq_path=str(faq))

    result = cache.get("  WHERE   DO I VOTE   ")

    assert result is not None
    assert result["intent"] == "faq_match"
