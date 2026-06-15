"""
LLM capability — Ollama implementation.

Swap this file to use a different runtime (vLLM, LM Studio, OpenAI-compatible
endpoint).  The LLMCapability interface in interfaces.py stays the same.

VRAM note: Mistral 7B Q4_K_M ≈ 4.5 GB.  Ollama manages loading/eviction
so this never permanently occupies memory when not in use.
"""
from typing import Any, List, Optional, Tuple

import ollama

from app.config import cfg
from capabilities.interfaces import LLMCapability


class OllamaLLM(LLMCapability):
    """
    LLMCapability backed by a locally-running Ollama server.

    Ollama handles:
      - Downloading and caching models
      - 4-bit quantization (built into the model tag, e.g. "mistral:latest")
      - Loading/evicting models from VRAM on demand

    To use a different model, change llm.model in config.yaml.
    """

    def __init__(self) -> None:
        self._client = ollama.Client(host=cfg.llm.base_url)
        self._model = cfg.llm.model
        # Base options applied to every call; overridable per-call.
        self._base_options = {
            "temperature": cfg.llm.temperature,
            "num_predict": cfg.llm.max_tokens,
        }

    # ── LLMCapability interface ────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Single-prompt shortcut.  Wraps the prompt in a user message so the
        caller doesn't have to build a message list for simple use cases.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    def chat(
        self,
        messages: List[dict],
        tools: Optional[List[dict]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        Multi-turn conversation.  Returns the assistant's text reply.

        If the model wants to call tools, the text content may be empty here —
        use chat_with_tool_response() when you need to inspect tool calls.
        """
        options = {**self._base_options}
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens

        kwargs: dict = {
            "model": self._model,
            "messages": messages,
            "options": options,
        }
        if tools:
            kwargs["tools"] = tools

        response = self._client.chat(**kwargs)
        return response.message.content or ""

    def chat_with_tool_response(
        self,
        messages: List[dict],
        tools: List[dict],
    ) -> Tuple[str, List[Any]]:
        """
        Returns (text_reply, tool_calls).
        tool_calls is a list of ollama tool-call objects; may be empty.
        The pipeline layer is responsible for executing any tool calls and
        continuing the conversation loop.
        """
        response = self._client.chat(
            model=self._model,
            messages=messages,
            tools=tools,
            options=self._base_options,
        )
        msg = response.message
        return (msg.content or "", msg.tool_calls or [])
