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
# Options and system prompt resolved via app.model_options — same as
# capabilities/llm.py.  Do not build inline options dicts here.
from app.model_options import maybe_inject_system, resolve_llm_options


class LLMClient:
    def __init__(self) -> None:
        self._client = ollama.Client(host=cfg.llm.base_url)
        self._model = cfg.llm.model
        # Options are resolved per-call (not stored on the instance) so that
        # per-call overrides and Modelfile baked-in defaults compose correctly.

    # ── Basic chat ────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: List[dict],
        temperature: Optional[float] = None,
        num_predict: Optional[int] = None,
    ) -> str:
        """
        Send a conversation (list of {role, content} dicts) and return
        the assistant's text reply.

        Example messages:
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user",   "content": "What is 2+2?"},
            ]
        """
        messages = maybe_inject_system(messages, cfg.llm.system_prompt)
        options = resolve_llm_options(cfg.llm, temperature=temperature, num_predict=num_predict)

        kwargs: dict = {"model": self._model, "messages": messages, "options": options}
        if cfg.llm.format is not None:
            # NOTE: format constrains JSON *syntax*, not content correctness.
            kwargs["format"] = cfg.llm.format

        response = self._client.chat(**kwargs)
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
        messages = maybe_inject_system(messages, cfg.llm.system_prompt)
        options = resolve_llm_options(cfg.llm)

        response = self._client.chat(
            model=self._model,
            messages=messages,
            tools=tools,
            options=options,
        )
        return response.message
