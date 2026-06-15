"""
Stable contracts for every backend capability.

The pipeline layer (and anything else that calls into the backend)
must only import these ABCs — never the concrete implementations.
That way swapping a model or vector store is a one-file change.

Reading order: LLM → Vision → Embeddings → RAG → MCP
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple


# ── 1. LLM inference ──────────────────────────────────────────────────────────

class LLMCapability(ABC):
    """
    Text generation and multi-turn chat.

    Two entry points:
      generate() — single prompt in, text out  (simplest case)
      chat()     — full conversation history in, text out  (for context)

    chat_with_tool_response() is the low-level hook for MCP tool calling:
    it returns both the text AND the raw tool-call objects so the caller
    can inspect and execute them.
    """

    @abstractmethod
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Single-turn: wrap prompt in a user message and return the reply."""

    @abstractmethod
    def chat(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Multi-turn: send an OpenAI-format message list and return the reply text.

        messages format: [{"role": "system"|"user"|"assistant"|"tool", "content": "..."}]
        tools:           optional OpenAI-compatible tool schema list.
                         If the model calls a tool, the text reply may be empty —
                         use chat_with_tool_response() if you need to inspect calls.
        """

    @abstractmethod
    def chat_with_tool_response(
        self,
        messages: List[dict],
        tools: List[dict],
    ) -> Tuple[str, List[Any]]:
        """
        Like chat() but returns (reply_text, tool_calls).
        tool_calls is the raw list from the model (may be empty).
        The MCP layer uses this to execute tool calls and continue the loop.
        """


# ── 2. Vision ─────────────────────────────────────────────────────────────────

class VisionCapability(ABC):
    """
    Image understanding: natural-language description and OCR.

    describe() is the general-purpose path — pass any prompt.
    ocr() is a specialised prompt optimised for raw text extraction.
    """

    @abstractmethod
    def describe(
        self,
        image_path: str,
        prompt: str = "Describe this image in detail.",
    ) -> str:
        """Return a natural-language description of the image at image_path."""

    @abstractmethod
    def ocr(self, image_path: str) -> str:
        """
        Extract all visible text from image_path exactly as it appears.
        Useful for reading UI screenshots, scanned documents, etc.
        """


# ── 3. Embeddings ─────────────────────────────────────────────────────────────

class EmbeddingsCapability(ABC):
    """
    Dense vector embeddings for semantic similarity.

    Kept as its own capability so the vector store (RAG) is decoupled from
    the embedding model.  Swap sentence-transformers for OpenAI embeddings
    by replacing only the implementation — RAGCapability stays the same.
    """

    @abstractmethod
    def embed(self, texts: List[str]) -> List[List[float]]:
        """Return one embedding vector per input text."""

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Size of each embedding vector — needed when creating an index."""


# ── 4. RAG ────────────────────────────────────────────────────────────────────

class RAGCapability(ABC):
    """
    Document indexing and retrieval.

    ingest() is a write operation: it loads, chunks, embeds, and stores documents.
    retrieve() is pure read: returns ranked text chunks for a query.

    This capability is stateless from the caller's perspective —
    the index lives on disk; the object is just the interface to it.
    """

    @abstractmethod
    def ingest(self, file_paths: List[str]) -> int:
        """
        Load, chunk, embed, and index every file in file_paths.
        Supports .md, .txt, and .pdf.
        Returns the total number of chunks stored.
        """

    @abstractmethod
    def retrieve(self, query: str, top_k: Optional[int] = None) -> List[str]:
        """
        Return the top_k most semantically similar text chunks for query.
        Returns an empty list if the index is empty.
        """

    @abstractmethod
    def count(self) -> int:
        """Total indexed chunks currently in the store."""


# ── 5. MCP client ─────────────────────────────────────────────────────────────

class MCPCapability(ABC):
    """
    MCP tool transport: register tools and execute them by name.

    This is the TRANSPORT layer only — it executes tool calls when told to.
    Decisions about WHEN to call a tool live in the pipeline layer.

    register() / register_tool() — add a tool to the registry.
    call()                       — execute one tool call by name + args.
    list_tools()                 — return all schemas (passed to the LLM).
    has_tool()                   — existence check before deciding to use MCP.
    """

    @abstractmethod
    def register(
        self,
        name: str,
        fn: Any,
        description: str,
        parameters: dict,
    ) -> None:
        """Add a callable to the registry with its OpenAI-compatible schema."""

    @abstractmethod
    def register_tool(self, description: str, parameters: dict):
        """Decorator version of register() — mirrors the existing @register_tool pattern."""

    @abstractmethod
    def call(self, name: str, args: dict) -> Any:
        """Execute the named tool with args.  Raises ValueError if not registered."""

    @abstractmethod
    def list_tools(self) -> List[dict]:
        """Return all OpenAI-compatible tool schemas.  Pass directly to LLMCapability."""

    @abstractmethod
    def has_tool(self, name: str) -> bool:
        """True if a tool with this name is registered."""
