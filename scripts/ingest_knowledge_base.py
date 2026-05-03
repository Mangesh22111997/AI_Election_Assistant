"""
scripts/ingest_knowledge_base.py
──────────────────────────────────
Ingests PDF documents from data/ into ChromaDB for RAG.

Usage:
    python scripts/ingest_knowledge_base.py
    python scripts/ingest_knowledge_base.py --data-dir data/ --reset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def ingest_pdfs(data_dir: Path, reset: bool = False) -> int:
    """Ingest all PDFs from data_dir into ChromaDB. Returns count of chunks."""
    try:
        import chromadb
        from chromadb.config import Settings as ChromaSettings
    except ImportError:
        print("❌ chromadb not installed. Run: pip install chromadb")
        return 0

    try:
        from pypdf import PdfReader
    except ImportError:
        print("❌ pypdf not installed. Run: pip install pypdf")
        return 0

    from backend.config import get_settings

    settings = get_settings()
    store_path = Path(settings.vector_store_path)
    store_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(store_path),
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    if reset:
        try:
            client.delete_collection("election_knowledge")
            print("🗑️  Existing collection cleared.")
        except Exception:
            pass

    collection = client.get_or_create_collection(
        name="election_knowledge",
        metadata={"hnsw:space": "cosine"},
    )

    # Search recursively for all PDFs in the data directory and subdirectories
    pdfs = list(data_dir.rglob("*.pdf"))
    if not pdfs:
        print(f"⚠️  No PDF files found in {data_dir.resolve()}. Ensure election PDFs are in the data/ folder or its subfolders.")
        return 0

    total_chunks = 0
    for pdf_path in pdfs:
        print(f"📄 Processing: {pdf_path.name}")
        try:
            reader = PdfReader(str(pdf_path))
            for page_num, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if len(text.strip()) < 50:
                    continue

                # Chunk into ~500-char segments
                chunks = _chunk_text(text, chunk_size=500, overlap=50)
                for i, chunk in enumerate(chunks):
                    doc_id = f"{pdf_path.stem}_p{page_num}_c{i}"
                    collection.upsert(
                        ids=[doc_id],
                        documents=[chunk],
                        metadatas=[
                            {
                                "source": pdf_path.name,
                                "page": page_num + 1,
                                "chunk": i,
                            }
                        ],
                    )
                    total_chunks += 1

            print(f"   ✅ {pdf_path.name}: {total_chunks} chunks ingested")
        except Exception as exc:
            print(f"   ❌ Failed to process {pdf_path.name}: {exc}")

    # Also ingest FAQ dataset
    faq_path = data_dir / "faq_dataset.json"
    if faq_path.exists():
        print("📋 Ingesting FAQ dataset...")
        with faq_path.open("r", encoding="utf-8") as f:
            faqs = json.load(f)

        for faq in faqs:
            doc_id = faq["id"]
            content = f"Q: {faq['question']}\nA: {faq['answer']}"
            collection.upsert(
                ids=[doc_id],
                documents=[content],
                metadatas=[{"source": "faq_dataset.json", "type": "faq"}],
            )
            total_chunks += 1
        print(f"   ✅ {len(faqs)} FAQ entries ingested")

    print(f"\n✅ Total chunks in vector store: {collection.count()}")
    return total_chunks


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """Split text into overlapping chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Ingest election PDFs into the ChromaDB vector store."
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing PDF files (default: data/)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear the existing collection before ingesting",
    )
    args = parser.parse_args()

    data_path = Path(args.data_dir)
    if not data_path.exists():
        print(f"❌ Data directory not found: {data_path}")
        sys.exit(1)

    print(f"🔍 Scanning: {data_path.resolve()}")
    count = ingest_pdfs(data_path, reset=args.reset)
    print(f"\n🎉 Ingestion complete. {count} chunks stored.")
