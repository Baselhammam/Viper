"""
Embeddings capability — sentence-transformers implementation.

Keeping this as its own swappable piece means RAGCapability never has to
change when you switch embedding models.  The only caller that cares about
the vector dimension is the vector store initialiser in ChromaRAG.

VRAM note: all-MiniLM-L6-v2 runs on CPU (~90 MB RAM).  Set
embeddings.device = "cuda" in config.yaml to use GPU, but CPU is fast
enough for typical RAG workloads and keeps VRAM free for the LLM.

To swap models:
  - Change embeddings.model in config.yaml (any sentence-transformers model name).
  - Nothing else changes.

To swap libraries (e.g. OpenAI text-embedding-3-small):
  - Replace this file with a new EmbeddingsCapability implementation.
  - The facade and RAGCapability are unchanged.
"""
from typing import List

from sentence_transformers import SentenceTransformer

from app.config import cfg
from capabilities.interfaces import EmbeddingsCapability


class SentenceTransformerEmbeddings(EmbeddingsCapability):
    """
    EmbeddingsCapability backed by sentence-transformers.

    Uses the model name and device from config.yaml.
    The model is downloaded on first use and cached by sentence-transformers.
    """

    def __init__(self) -> None:
        print(f"  [Embeddings] Loading {cfg.embeddings.model} on {cfg.embeddings.device}")
        self._model = SentenceTransformer(
            cfg.embeddings.model,
            device=cfg.embeddings.device,
        )

    # ── EmbeddingsCapability interface ─────────────────────────────────────────

    def embed(self, texts: List[str]) -> List[List[float]]:
        """
        Encode a list of strings into dense vectors.
        Returns a list with one float list per input string.
        """
        if not texts:
            return []
        # show_progress_bar=False keeps output clean during inference.
        return self._model.encode(texts, show_progress_bar=False).tolist()

    @property
    def dimension(self) -> int:
        """
        Size of each embedding vector.
        all-MiniLM-L6-v2 → 384 dimensions.
        Passed to ChromaDB when creating a collection.
        """
        return self._model.get_sentence_embedding_dimension()
