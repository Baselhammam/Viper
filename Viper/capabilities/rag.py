"""
RAG capability — ChromaDB implementation.

Composes two things:
  1. Document loading + chunking  (reuses app/rag/ingestor.py)
  2. Embedding + vector store     (ChromaDB, injected EmbeddingsCapability)

The EmbeddingsCapability is injected at construction time so the vector
store never hard-codes a specific model.  To swap embedding models, change
only embeddings.py — this file and its callers are unaffected.

To swap the vector store (FAISS, Weaviate, Qdrant):
  - Replace this file with a new RAGCapability implementation.
  - The facade and any pipeline code that calls get_rag() are unchanged.

Storage note: ChromaDB is persistent — data survives restarts.  The index
grows every time you call ingest().  If you want a fresh index, delete the
directory at config.rag.chroma_persist_dir.
"""
from typing import List, Optional

import chromadb
from chromadb.config import Settings

from app.config import cfg
from app.rag.ingestor import ingest_documents   # pure function, no state — safe to reuse
from capabilities.interfaces import EmbeddingsCapability, RAGCapability


class ChromaRAG(RAGCapability):
    """
    RAGCapability backed by ChromaDB + a swappable EmbeddingsCapability.

    Args:
        embeddings: any EmbeddingsCapability implementation.
                    The facade injects SentenceTransformerEmbeddings by default.
    """

    def __init__(self, embeddings: EmbeddingsCapability) -> None:
        self._embeddings = embeddings

        # PersistentClient writes to disk — data survives restarts.
        self._db = chromadb.PersistentClient(
            path=cfg.rag.chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        # get_or_create: safe to call multiple times; returns existing collection.
        self._collection = self._db.get_or_create_collection(
            name=cfg.rag.collection_name,
            # cosine is the right metric for sentence-transformer embeddings.
            metadata={"hnsw:space": "cosine"},
        )
        print(f"  [RAG] ChromaDB ready — {self._collection.count()} chunks already indexed")

    # ── RAGCapability interface ────────────────────────────────────────────────

    def ingest(self, file_paths: List[str]) -> int:
        """
        Load, chunk, embed, and index every file.
        Supported: .md, .txt, .pdf (anything ingestor.py handles).
        Returns the number of new chunks stored this call.
        """
        docs = ingest_documents(file_paths)
        if not docs:
            return 0

        texts     = [d.page_content for d in docs]
        metadatas = [d.metadata for d in docs]
        vectors   = self._embeddings.embed(texts)

        # IDs must be unique strings.  Offset by current count so multiple
        # ingest() calls don't overwrite each other.
        offset = self._collection.count()
        ids    = [str(offset + i) for i in range(len(texts))]

        self._collection.add(
            ids=ids,
            embeddings=vectors,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"  [RAG] Stored {len(texts)} chunks (total: {self._collection.count()})")
        return len(texts)

    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[str]:
        """
        Return the top_k most semantically similar chunks for query.
        Returns [] if the index is empty.
        """
        total = self._collection.count()
        if total == 0:
            return []

        k = top_k if top_k is not None else cfg.rag.top_k
        results = self._collection.query(
            query_embeddings=self._embeddings.embed([query]),
            n_results=min(k, total),
        )
        # results["documents"] is a list-of-lists; [0] = first (only) query.
        return results["documents"][0]

    def count(self) -> int:
        """Total indexed chunks in the store."""
        return self._collection.count()
