"""
Central router — the single entry point the API and demo scripts use.

Viper ties together:
  - RAG (ingest + retrieve)
  - LLM inference
  - Vision captioning (lazy-loaded on first use)
  - Tool-assisted generation

All four components are individually swappable via their own modules.
"""
from typing import Optional

from app.config import cfg
from app.llm.inference import LLMClient
from app.rag.ingestor import ingest_documents
from app.rag.retriever import Retriever
from app.tools.executor import run_tool_loop
from app.vision.captioner import VisionCaptioner


class Viper:
    """
    Main facade.  Instantiate once at startup and reuse across requests.

    Example:
        viper = Viper()
        viper.ingest(["docs/manual.md"])
        print(viper.ask("How do I reset the device?"))
    """

    def __init__(self) -> None:
        print("Initialising Viper...")
        self.llm = LLMClient()
        self.retriever = Retriever()
        # Vision model loaded lazily — avoids occupying VRAM unless needed.
        self._vision: Optional[VisionCaptioner] = None
        print("Viper ready.")

    # ── Document management ───────────────────────────────────────────────────

    def ingest(self, file_paths: list[str]) -> int:
        """
        Ingest one or more documents into the RAG vector store.
        Returns the number of chunks stored.
        """
        docs = ingest_documents(file_paths)
        self.retriever.add_documents(docs)
        return len(docs)

    # ── RAG question answering ────────────────────────────────────────────────

    def ask(self, question: str) -> str:
        """
        Retrieve the most relevant document chunks, then answer the question
        using the LLM grounded on that context.
        """
        chunks = self.retriever.retrieve(question)

        if chunks:
            context = "\n\n---\n\n".join(chunks)
        else:
            context = "No relevant documents found in the knowledge base."

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. "
                    "Answer the question using ONLY the context provided. "
                    "If the context does not contain the answer, say so clearly — do not guess."
                ),
            },
            {
                "role": "user",
                "content": f"Context:\n{context}\n\nQuestion: {question}",
            },
        ]
        return self.llm.chat(messages)

    # ── Image description ─────────────────────────────────────────────────────

    def describe_image(
        self, image_path: str, prompt: str = "Describe this image in detail."
    ) -> str:
        """Return a text description of a local image file."""
        if self._vision is None:
            self._vision = VisionCaptioner()
        return self._vision.describe(image_path, prompt)

    # ── Tool-assisted generation ──────────────────────────────────────────────

    def run_with_tools(self, user_message: str) -> str:
        """
        Let the LLM decide which registered tools to call (if any).
        The tool loop runs until the model produces a plain-text answer.
        """
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant with access to tools. "
                    "Use tools when they help you give a more accurate answer."
                ),
            },
            {"role": "user", "content": user_message},
        ]
        return run_tool_loop(self.llm, messages)

    # ── Plain chat ────────────────────────────────────────────────────────────

    def chat(self, message: str) -> str:
        """Single-turn chat with no RAG or tool access."""
        messages = [
            {"role": "system", "content": "You are a helpful coding assistant."},
            {"role": "user", "content": message},
        ]
        return self.llm.chat(messages)
