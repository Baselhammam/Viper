"""
Anthropic-backed implementation of EditProvider.

This is the ONLY file that knows about the Anthropic SDK, the
"propose_edits" tool contract, or prompt-caching mechanics. Callers only
ever see `EditProvider`.

Verified against docs.claude.com (redirects to platform.claude.com) on
2026-06-18, against `anthropic` Python SDK 0.x (Messages API, `messages.stream`):
  - cache_control: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
  - tool use / tool_choice: https://platform.claude.com/docs/en/build-with-claude/tool-use/overview
  - streaming events (content_block_delta / input_json_delta): https://platform.claude.com/docs/en/api/messages-streaming
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, AsyncIterator

import pydantic_core
from anthropic import AsyncAnthropic

from app.models import EditOp, Target

logger = logging.getLogger("edit_stream.anthropic_provider")

# Suggested default: a fast/cheap model is enough for range-edit generation.
# Sonnet-class also has a lower prompt-cache minimum (1024 tokens) than
# Haiku-class (4096 tokens), making the cache demo easier to trigger with a
# realistically-sized target. Override via MODEL env var.
DEFAULT_MODEL = "claude-sonnet-4-6"

TOOL_NAME = "propose_edits"

_EDIT_OP_SCHEMA = {
    "type": "object",
    "properties": {
        "start": {"type": "integer", "description": "Start offset (inclusive) into target.content."},
        "end": {"type": "integer", "description": "End offset (exclusive) into target.content."},
        "replacement": {"type": "string", "description": "Text to replace the [start, end) range with."},
    },
    "required": ["start", "end", "replacement"],
}

_TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": _EDIT_OP_SCHEMA,
            "description": "Ordered list of range-based text edits to apply to target.content.",
        },
    },
    "required": ["edits"],
}

_SYSTEM_PROMPT = (
    "You are a code/text editing engine. You receive a text buffer (the target) "
    "and an instruction. You MUST respond by calling the "
    f"`{TOOL_NAME}` tool exactly once with a list of range-based edits "
    "(start, end, replacement) that implement the instruction. "
    "Never respond with prose, never repeat or regenerate the whole document — "
    "only emit the minimal set of edits needed. "
    "start/end are character offsets into the ORIGINAL target.content "
    "(end is exclusive, like a Python slice)."
)


class AnthropicEditProvider:
    """EditProvider backed by the Anthropic Messages API."""

    def __init__(self, client: AsyncAnthropic | None = None, model: str | None = None) -> None:
        # API key is read from ANTHROPIC_API_KEY by the SDK itself if not
        # passed explicitly — never read/forward it ourselves, so it can
        # never accidentally end up in a log line or response.
        self._client = client or AsyncAnthropic()
        self._model = model or os.environ.get("MODEL", DEFAULT_MODEL)

    async def stream_edits(self, target: Target, prompt: str) -> AsyncIterator[EditOp]:
        # Two separate cache breakpoints:
        #   1. The system prompt (static across all calls, all targets).
        #   2. The target content (static across repeated previews on the
        #      SAME target; only `prompt` varies call-to-call).
        # Putting `prompt` in its own, uncached block after the target means
        # changing the prompt never invalidates the cached target prefix.
        system = [
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ]
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"Target ({target.language or 'plaintext'}):\n{target.content}",
                        "cache_control": {"type": "ephemeral"},
                    },
                    {
                        "type": "text",
                        "text": f"Instruction: {prompt}",
                    },
                ],
            }
        ]
        tools = [
            {
                "name": TOOL_NAME,
                "description": "Propose a list of range-based text edits to apply to the target.",
                "input_schema": _TOOL_INPUT_SCHEMA,
            }
        ]

        # Buffer of raw partial_json text, keyed by content_block index, for
        # the (single) propose_edits tool_use block we expect.
        buffers: dict[int, str] = {}
        emitted_counts: dict[int, int] = {}
        tool_block_indexes: set[int] = set()

        async with self._client.messages.stream(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=messages,
            tools=tools,
            # Force the model to always call propose_edits — never prose.
            tool_choice={"type": "tool", "name": TOOL_NAME},
        ) as stream:
            async for event in stream:
                if event.type == "content_block_start":
                    if event.content_block.type == "tool_use" and event.content_block.name == TOOL_NAME:
                        tool_block_indexes.add(event.index)
                        buffers[event.index] = ""
                        emitted_counts[event.index] = 0

                elif event.type == "content_block_delta":
                    if event.index not in tool_block_indexes:
                        continue
                    if event.delta.type == "input_json_delta":
                        buffers[event.index] += event.delta.partial_json
                        for op in self._try_emit_complete(
                            buffers[event.index], emitted_counts[event.index], final=False
                        ):
                            emitted_counts[event.index] += 1
                            yield op

                elif event.type == "content_block_stop":
                    if event.index not in tool_block_indexes:
                        continue
                    # Stream for this block is done — every remaining edit
                    # in the buffer is now provably complete (no more bytes
                    # are coming), so flush whatever wasn't already emitted.
                    for op in self._try_emit_complete(
                        buffers[event.index], emitted_counts[event.index], final=True
                    ):
                        emitted_counts[event.index] += 1
                        yield op

                elif event.type == "message_delta":
                    usage = getattr(event, "usage", None)
                    if usage is not None:
                        logger.info(
                            "usage delta: input=%s cache_creation=%s cache_read=%s output=%s",
                            getattr(usage, "input_tokens", None),
                            getattr(usage, "cache_creation_input_tokens", None),
                            getattr(usage, "cache_read_input_tokens", None),
                            getattr(usage, "output_tokens", None),
                        )

            final_message = await stream.get_final_message()
            usage = final_message.usage
            logger.info(
                "final usage: input=%s cache_creation=%s cache_read=%s output=%s",
                usage.input_tokens,
                getattr(usage, "cache_creation_input_tokens", None),
                getattr(usage, "cache_read_input_tokens", None),
                usage.output_tokens,
            )

    @staticmethod
    def _try_emit_complete(buffer: str, already_emitted: int, *, final: bool) -> list[EditOp]:
        """
        Parse the (possibly truncated) JSON `buffer` and return any newly
        complete EditOps beyond `already_emitted`.

        Why this is safe: pydantic_core.from_json(allow_partial=True) only
        includes a key once its value's literal token is fully closed (a
        terminated string, a terminated number, etc.) — see the verification
        run that informed this implementation. The one remaining hazard is a
        JSON *number* that looks complete but is still mid-write (e.g. "1"
        about to become "10"); a number is only provably final once a
        delimiter after it (a comma or closing bracket) has also arrived. So
        we never trust the LAST array element until the array (or the whole
        block, on `final=True`) has actually closed — only elements that
        already have a successor, or the fully-closed final buffer, are
        treated as final.
        """
        try:
            parsed: Any = pydantic_core.from_json(buffer.encode(), allow_partial=True)
        except ValueError:
            return []
        if not isinstance(parsed, dict):
            return []
        edits = parsed.get("edits")
        if not isinstance(edits, list):
            return []

        # On a fully-closed buffer (block_stop), every element is final.
        # Otherwise, only elements strictly before the last one are final.
        safe_count = len(edits) if final else max(0, len(edits) - 1)

        new_ops: list[EditOp] = []
        for raw in edits[already_emitted:safe_count]:
            try:
                new_ops.append(EditOp.model_validate(raw))
            except Exception:
                # Shouldn't happen for an element pydantic_core deemed
                # complete, but never emit something that doesn't validate.
                continue
        return new_ops
