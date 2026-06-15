"""
Vector store layer (ChromaDB + sentence-transformers).

Public interface:
    retriever.add_documents(docs)  — embed and persist a list of Documents
    retriever.retrieve(query)      — return top-k relevant text chunks

Swap ChromaDB for FAISS or Weaviate by replacing this file only.
Swap the embedding model by changing config.yaml — no code changes needed.
"""
from typing import List

import chromadb
from chromadb.config import Settings
from langchain.schema import Document
from sentence_transformers import SentenceTransformer

from app.config import cfg


class Retriever:
    def __init__(self) -> None:
        # Embedding model — CPU inference keeps VRAM free for the LLM.
        print(f"  Loading embedding model: {cfg.embeddings.model}")
        self._embedder = SentenceTransformer(
            cfg.embeddings.model, device=cfg.embeddings.device
        )

        # Persistent ChromaDB — survives restarts, no external service needed.
        self._client = chromadb.PersistentClient(
            path=cfg.rag.chroma_persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
        self._collection = self._client.get_or_create_collection(
            name="viper_docs",
            # Cosine similarity is standard for sentence-transformer embeddings.
            metadata={"hnsw:space": "cosine"},
        )
        print(f"  ChromaDB ready ({self._collection.count()} chunks already stored)")

    # ── Internal ──────────────────────────────────────────────────────────────

    def _embed(self, texts: List[str]) -> List[List[float]]:
        return self._embedder.encode(texts, show_progress_bar=False).tolist()

    # ── Public API ────────────────────────────────────────────────────────────

    def add_documents(self, docs: List[Document]) -> None:
        """Embed and store a list of LangChain Document objects."""
        if not docs:
            return

        texts = [d.page_content for d in docs]
        metadatas = [d.metadata for d in docs]
        embeddings = self._embed(texts)

        # IDs must be unique strings; offset by current count to avoid collisions
        # when calling add_documents multiple times.
        offset = self._collection.count()
        ids = [str(offset + i) for i in range(len(texts))]

        self._collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )
        print(f"  Stored {len(texts)} chunks  (total in DB: {self._collection.count()})")

    def retrieve(self, query: str, top_k: int | None = None) -> List[str]:
        """Return the top-k most similar text chunks for a query string."""
        k = top_k or cfg.rag.top_k
        total = self._collection.count()
        if total == 0:
            return []

        results = self._collection.query(
            query_embeddings=self._embed([query]),
            n_results=min(k, total),
        )
        # results["documents"] is a list-of-lists; [0] is the first (only) query.
        return results["documents"][0]
