"""
Anthropic-backed implementation of EditProvider.

This is the ONLY file that knows about the Anthropic SDK or the
`propose_patch` tool contract. Callers only ever see `EditProvider`.

Verified against docs.claude.com (redirects to platform.claude.com) on
2026-06-19, against the `anthropic` Python SDK, Messages API:
  - tool definitions / `input_schema`: /docs/en/agents-and-tools/tool-use/define-tools
  - forcing tool use (`tool_choice={"type": "tool", "name": ...}`): same page
  - current model ids (Sonnet/Haiku-class): /docs/en/about-claude/models/overview

Non-streaming by design: atomic all-or-nothing validation (app/applier.py)
needs every block before any of them can be safely applied, so there is
nothing to usefully stream — a single `messages.create()` call returns the
already-parsed tool `.input`, which is simpler and removes an entire class
of partial-JSON-reconstruction bugs that streaming would otherwise require.
"""
from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

from app.models import SearchReplaceBlock, Target
from app.settings import settings

logger = logging.getLogger("edit_stream.anthropic_provider")

TOOL_NAME = "propose_patch"

_BLOCK_SCHEMA = {
    "type": "object",
    "properties": {
        "search": {
            "type": "string",
            "description": "Exact, verbatim substring of the CURRENT target text to locate.",
        },
        "replace": {
            "type": "string",
            "description": "Text to put in place of `search`.",
        },
    },
    "required": ["search", "replace"],
}

_TOOL_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": _BLOCK_SCHEMA,
            "description": (
                "Ordered list of SEARCH/REPLACE blocks. Apply in order; "
                "each `search` must be an exact, unique substring of the "
                "target at the point it is applied."
            ),
        },
    },
    "required": ["blocks"],
}


def _build_system_prompt() -> str:
    # The marker strings are config (app/settings.py), not hardcoded here,
    # so the visual block grammar shown to the model has exactly one source
    # of truth even though the actual wire format is the structured tool
    # call below, not raw delimited text.
    return (
        "You are a precise text/code editing engine. You receive a target "
        "text buffer and an instruction. Respond by calling the "
        f"`{TOOL_NAME}` tool exactly once with one or more SEARCH/REPLACE "
        "blocks that implement the instruction, conceptually shaped like:\n\n"
        f"{settings.search_marker}\n"
        "<exact existing text from the target>\n"
        f"{settings.divider_marker}\n"
        "<replacement text>\n"
        f"{settings.replace_marker}\n\n"
        "Rules:\n"
        "- `search` MUST be an exact, verbatim substring of the target — "
        "copy real text, never compute character offsets or line numbers.\n"
        "- `search` MUST be unique in the target at the point this block "
        "applies; if the text you want to change appears more than once, "
        "include enough surrounding context in `search` to make it unique.\n"
        "- Never regenerate or repeat the whole document — emit only the "
        "minimal blocks needed.\n"
        "- Never respond with prose."
    )


class AnthropicEditProvider:
    """EditProvider backed by the Anthropic Messages API."""

    def __init__(self, client: AsyncAnthropic | None = None) -> None:
        # The API key never passes through our own code as a plain str —
        # `.get_secret_value()` is called here and only here, right at the
        # SDK boundary, and the resulting client object is never logged.
        self._client = client or AsyncAnthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.request_timeout_s,
        )

    async def propose_patch(self, target: Target, prompt: str) -> list[SearchReplaceBlock]:
        # Two cache breakpoints, preserved from the previous design: the
        # system prompt (static across all calls) and the target content
        # (static across repeated calls on the SAME target — only `prompt`
        # varies). Keeping `prompt` in its own, uncached block after the
        # target means changing the prompt never invalidates the cached
        # target prefix.
        message = await self._client.messages.create(
            model=settings.model,
            max_tokens=settings.max_output_tokens,
            system=[
                {
                    "type": "text",
                    "text": _build_system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[
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
            ],
            tools=[
                {
                    "name": TOOL_NAME,
                    "description": (
                        "Propose one or more SEARCH/REPLACE blocks to apply to the target text."
                    ),
                    "input_schema": _TOOL_INPUT_SCHEMA,
                    # Guarantees the model's tool call conforms to the schema
                    # exactly, reducing how often we have to reject a
                    # malformed block downstream.
                    "strict": True,
                }
            ],
            # Force the model to always call propose_patch — never prose.
            tool_choice={"type": "tool", "name": TOOL_NAME},
        )

        usage = message.usage
        logger.info(
            "usage: input=%s cache_creation=%s cache_read=%s output=%s",
            usage.input_tokens,
            getattr(usage, "cache_creation_input_tokens", None),
            getattr(usage, "cache_read_input_tokens", None),
            usage.output_tokens,
        )

        tool_use = next((b for b in message.content if b.type == "tool_use"), None)
        if tool_use is None:
            raise ValueError("model response contained no tool_use block")

        raw_blocks = tool_use.input.get("blocks")
        if not isinstance(raw_blocks, list):
            raise ValueError("model tool input missing a 'blocks' array")

        # Reject the WHOLE patch if any single block is malformed — same
        # atomic-all-or-nothing principle as the applier: we never want to
        # silently drop one bad block and proceed with the rest, since the
        # caller has no way to know a block went missing.
        blocks: list[SearchReplaceBlock] = []
        for i, raw in enumerate(raw_blocks):
            try:
                blocks.append(SearchReplaceBlock.model_validate(raw))
            except Exception as exc:
                raise ValueError(f"malformed block at index {i}: {exc}") from exc

        return blocks
