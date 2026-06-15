"""
LLM inference layer — thin wrapper around the Ollama Python SDK.

Keeping Ollama calls isolated here means swapping the runtime
(e.g. to vLLM, LM Studio, or an OpenAI-compatible endpoint) only
requires editing this single file.

Ollama docs: https://github.com/ollama/ollama-python
"""
from typing import List, Optional

import ollama

from app.config import cfg


class LLMClient:
    def __init__(self) -> None:
        self._client = ollama.Client(host=cfg.llm.base_url)
        self._model = cfg.llm.model
        self._options = {
            "temperature": cfg.llm.temperature,
            "num_predict": cfg.llm.max_tokens,
        }

    # ── Basic chat ────────────────────────────────────────────────────────────

    def chat(self, messages: List[dict]) -> str:
        """
        Send a conversation (list of {role, content} dicts) and return
        the assistant's text reply.

        Example messages:
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user",   "content": "What is 2+2?"},
            ]
        """
        response = self._client.chat(
            model=self._model,
            messages=messages,
            options=self._options,
        )
        return response.message.content or ""

    # ── Tool / function calling ───────────────────────────────────────────────

    def chat_with_tools(
        self, messages: List[dict], tools: List[dict]
    ) -> ollama.Message:
        """
        Like chat(), but attaches tool definitions so the model can request
        function calls.  Returns the raw ollama.Message so callers can inspect
        .tool_calls before deciding whether to execute anything.

        tools format (OpenAI-compatible):
            [
                {
                    "type": "function",
                    "function": {
                        "name": "my_func",
                        "description": "...",
                        "parameters": { "type": "object", ... },
                    },
                },
                ...
            ]
        """
        response = self._client.chat(
            model=self._model,
            messages=messages,
            tools=tools,
            options=self._options,
        )
        return response.message
