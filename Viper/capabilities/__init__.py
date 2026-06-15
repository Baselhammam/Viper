"""
Backend capabilities facade.

This is the ONLY surface the pipeline layer (or any other caller) should
import from.  It exposes one getter per capability; each getter is lazily
initialised and returns a singleton.

Typical pipeline usage:
    from capabilities import get_llm, get_rag, get_mcp

    answer = get_llm().generate("Explain VRAM.", system="You are a tutor.")
    chunks = get_rag().retrieve("How do I reset the device?")
    time_  = get_mcp().call("get_current_datetime", {})

Dependency rule (enforced by convention):
    pipeline layer → capabilities (this file)
    capabilities   → app/config.py  (shared config)
    capabilities   NEVER imports from the pipeline layer

Swapping an implementation:
    Replace the import inside the relevant get_xxx() function.
    No callers change.
"""
from typing import Optional

from capabilities.interfaces import (
    EmbeddingsCapability,
    LLMCapability,
    MCPCapability,
    RAGCapability,
    VisionCapability,
)

# ── Lazy singletons ───────────────────────────────────────────────────────────
# Each starts as None and is created on first access.  Heavy initialisations
# (loading a model, connecting to ChromaDB) happen only when actually needed.

_llm:        Optional[LLMCapability]        = None
_vision:     Optional[VisionCapability]     = None
_embeddings: Optional[EmbeddingsCapability] = None
_rag:        Optional[RAGCapability]        = None
_mcp:        Optional[MCPCapability]        = None


def get_llm() -> LLMCapability:
    """
    Return the LLM capability singleton.
    Default: OllamaLLM (Mistral 7B Q4, ~4.5 GB VRAM).
    Swap: replace OllamaLLM with any LLMCapability implementation.
    """
    global _llm
    if _llm is None:
        from capabilities.llm import OllamaLLM
        _llm = OllamaLLM()
    return _llm


def get_vision() -> VisionCapability:
    """
    Return the vision capability singleton.
    Default: OllamaVision (LLaVA 7B, ~4.5 GB VRAM, evicted when idle).
    Swap: replace OllamaVision with any VisionCapability implementation.
    """
    global _vision
    if _vision is None:
        from capabilities.vision import OllamaVision
        _vision = OllamaVision()
    return _vision


def get_embeddings() -> EmbeddingsCapability:
    """
    Return the embeddings capability singleton.
    Default: SentenceTransformerEmbeddings (all-MiniLM-L6-v2, CPU, ~90 MB RAM).
    Swap: replace with any EmbeddingsCapability (e.g. OpenAI text-embedding-3-small).
    """
    global _embeddings
    if _embeddings is None:
        from capabilities.embeddings import SentenceTransformerEmbeddings
        _embeddings = SentenceTransformerEmbeddings()
    return _embeddings


def get_rag() -> RAGCapability:
    """
    Return the RAG capability singleton.
    Default: ChromaRAG (ChromaDB + injected embeddings, persistent to disk).
    Swap: replace ChromaRAG with any RAGCapability implementation.

    Note: ChromaRAG depends on EmbeddingsCapability — get_embeddings() is
    initialised first and injected automatically.
    """
    global _rag
    if _rag is None:
        from capabilities.rag import ChromaRAG
        _rag = ChromaRAG(embeddings=get_embeddings())
    return _rag


def get_mcp() -> MCPCapability:
    """
    Return the MCP client singleton.
    Comes pre-loaded with two built-in tools:
      get_current_datetime — current date/time string
      calculate            — safe arithmetic evaluator

    Register your own tools on the returned instance:
        get_mcp().register_tool(...)(my_function)
    or:
        get_mcp().register("name", fn, description, parameters)
    """
    global _mcp
    if _mcp is None:
        from capabilities.mcp import MCPClient
        _mcp = MCPClient()
    return _mcp


def reset_all() -> None:
    """
    Force all singletons to be re-created on next access.
    Useful in tests to get a fresh state between test cases.
    """
    global _llm, _vision, _embeddings, _rag, _mcp
    _llm = _vision = _embeddings = _rag = _mcp = None
