"""
backend/services/grounding_tool.py
─────────────────────────────────────
RAG (Retrieval-Augmented Generation) implementation.
Uses ChromaDB as the vector store and Google Custom Search
for live grounding of deadline information.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import requests

from backend.config import get_settings
from backend.utils.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Optional Heavy Imports (lazy) ────────────────────────────────────────────
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False
    logger.warning("chromadb not installed – vector search disabled")

try:
    _EMBEDDINGS_AVAILABLE = True
except ImportError:
    _EMBEDDINGS_AVAILABLE = False
    logger.warning("langchain-google-genai not installed – embeddings disabled")


class GroundingTool:
    """
    Provides retrieval-augmented grounding for agent responses.

    Two grounding sources:
    1. Local ChromaDB vector store (offline PDFs / FAQ dataset)
    2. Google Custom Search API (live deadline data)
    """

    COLLECTION_NAME = "election_knowledge"

    def __init__(self) -> None:
        self._chroma_client: Any = None
        self._collection: Any = None
        self._embeddings: Any = None
        self._init_vector_store()

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(
        self,
        query: str,
        n_results: int | None = None,
        similarity_threshold: float | None = None,
    ) -> list[dict[str, str]]:
        """
        Retrieve the most relevant chunks for a given query.

        Returns a list of {"content": ..., "source": ..., "score": ...} dicts.
        """
        n = n_results or settings.max_retrieval_contexts
        threshold = similarity_threshold or settings.similarity_threshold
        results: list[dict[str, str]] = []

        # 1. Vector store retrieval
        if self._collection is not None:
            results.extend(self._vector_search(query, n, threshold))

        # 2. FAQ dataset fallback (always available)
        results.extend(self._faq_search(query))

        # Deduplicate and cap
        seen: set[str] = set()
        unique: list[dict[str, str]] = []
        for item in results:
            key = hashlib.md5(item["content"].encode()).hexdigest()
            if key not in seen:
                seen.add(key)
                unique.append(item)

        return unique[:n]

    def live_search(self, query: str) -> list[dict[str, str]]:
        """
        Query Google Custom Search for live election information.
        Returns up to 3 web results with title + snippet.
        """
        if not settings.google_cse_id or not settings.google_cse_api_key:
            logger.debug("Google CSE not configured – skipping live search")
            return []

        try:
            params = {
                "key": settings.google_cse_api_key,
                "cx": settings.google_cse_id,
                "q": f"official election information {query}",
                "num": 3,
            }
            resp = requests.get(
                "https://www.googleapis.com/customsearch/v1",
                params=params,
                timeout=5,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])
            return [
                {
                    "content": f"{i.get('title', '')}: {i.get('snippet', '')}",
                    "source": i.get("link", "Google Search"),
                    "score": "1.0",
                }
                for i in items
            ]
        except Exception as exc:
            logger.warning("Google Custom Search failed", error=str(exc))
            return []

    def format_context(self, retrieved: list[dict[str, str]]) -> str:
        """Format retrieved chunks into a context string for the LLM prompt."""
        if not retrieved:
            return "No specific documents retrieved. Use general election knowledge."

        parts = []
        for i, item in enumerate(retrieved, start=1):
            parts.append(
                f"[Source {i}: {item.get('source', 'Unknown')}]\n"
                f"{item['content']}"
            )
        return "\n\n".join(parts)

    # ── Private Helpers ───────────────────────────────────────────────────────

    def _init_vector_store(self) -> None:
        if not _CHROMA_AVAILABLE:
            return

        store_path = Path(settings.vector_store_path)
        store_path.mkdir(parents=True, exist_ok=True)

        try:
            self._chroma_client = chromadb.PersistentClient(
                path=str(store_path),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(
                "ChromaDB collection loaded",
                collection=self.COLLECTION_NAME,
                count=self._collection.count(),
            )
        except Exception as exc:
            logger.error("Failed to initialise ChromaDB", error=str(exc))

    def _vector_search(
        self, query: str, n: int, threshold: float
    ) -> list[dict[str, str]]:
        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=min(n, max(self._collection.count(), 1)),
                include=["documents", "metadatas", "distances"],
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            dists = results.get("distances", [[]])[0]

            output = []
            for doc, meta, dist in zip(docs, metas, dists):
                score = 1.0 - dist  # cosine distance → similarity
                if score >= threshold:
                    output.append(
                        {
                            "content": doc,
                            "source": meta.get("source", "election_manual.pdf"),
                            "score": f"{score:.3f}",
                        }
                    )
            return output
        except Exception as exc:
            logger.error("Vector search failed", error=str(exc))
            return []

    def _faq_search(self, query: str) -> list[dict[str, str]]:
        """Simple keyword search over the FAQ dataset."""
        faq_path = Path("data/faq_dataset.json")
        if not faq_path.exists():
            return []

        try:
            with faq_path.open("r", encoding="utf-8") as f:
                faqs: list[dict[str, str]] = json.load(f)

            query_lower = query.lower()
            matches = []
            for faq in faqs:
                keywords = faq.get("keywords", [])
                question = faq.get("question", "")
                if any(kw in query_lower for kw in keywords) or any(
                    kw in question.lower() for kw in query_lower.split()
                ):
                    matches.append(
                        {
                            "content": f"Q: {question}\nA: {faq.get('answer', '')}",
                            "source": "faq_dataset.json",
                            "score": "0.80",
                        }
                    )
            return matches[:3]
        except Exception as exc:
            logger.error("FAQ search failed", error=str(exc))
            return []


# ── Module-level singleton ────────────────────────────────────────────────────
_grounding_tool: GroundingTool | None = None


def get_grounding_tool() -> GroundingTool:
    global _grounding_tool
    if _grounding_tool is None:
        _grounding_tool = GroundingTool()
    return _grounding_tool
