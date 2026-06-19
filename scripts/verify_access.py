#!/usr/bin/env python3
"""
Verify our Anthropic API access works, once the key is set.

Reads ANTHROPIC_API_KEY from the environment (never printed) and runs two
checks against model claude-sonnet-4-6:
  1. TOOL USE      -- force a tool call and confirm a tool_use block comes back.
  2. PROMPT CACHING -- confirm a cached prefix is written, then read back.

Run:  python scripts/verify_access.py
Exits 0 only if BOTH checks pass; non-zero otherwise. The API key is never printed.
"""
from __future__ import annotations

import os
import sys

MODEL = "claude-sonnet-4-6"

# claude-sonnet-4-6's minimum cacheable prefix is 2048 tokens; a shorter prefix
# silently won't cache (cache_creation stays 0). We pad well past that so the
# caching check actually exercises the cache rather than false-failing.
_FILLER_UNIT = (
    "This sentence is filler whose only purpose is to push the cached prefix "
    "comfortably past the model's minimum cacheable size so the cache check is real. "
)
# ~22 tokens/unit * 200 -> ~4,400 tokens, safely above the 2,048 minimum.
FILLER = _FILLER_UNIT * 200


def _client():
    """Build the SDK client, or exit non-zero with a clear (key-free) message."""
    try:
        import anthropic
    except ImportError:
        print("FAIL: the 'anthropic' package is not installed (pip install -r requirements.txt)")
        sys.exit(1)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("FAIL: ANTHROPIC_API_KEY is not set in the environment")
        sys.exit(1)

    # The SDK reads ANTHROPIC_API_KEY from the environment itself — we never
    # touch, log, or print the value.
    return anthropic.Anthropic()


def check_tool_use(client) -> bool:
    tool = {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "input_schema": {
            "type": "object",
            "properties": {"city": {"type": "string", "description": "City name"}},
            "required": ["city"],
        },
    }
    try:
        resp = client.messages.create(
            model=MODEL,
            max_tokens=256,
            tools=[tool],
            # Force the model to call the tool rather than reply with prose.
            tool_choice={"type": "tool", "name": "get_weather"},
            messages=[{"role": "user", "content": "What's the weather in Paris?"}],
        )
    except Exception as exc:  # surface any failure; never expose the key
        print(f"tool-use: FAIL ({type(exc).__name__}: {exc})")
        return False

    if any(getattr(block, "type", None) == "tool_use" for block in resp.content):
        print("tool-use: OK")
        return True
    print("tool-use: FAIL (no tool_use block in response)")
    return False


def check_prompt_caching(client) -> bool:
    system = [
        {
            "type": "text",
            "text": FILLER,
            "cache_control": {"type": "ephemeral"},
        }
    ]
    messages = [{"role": "user", "content": "Reply with the single word: ok"}]

    def _call():
        # Both calls must be byte-identical so the second hits the cache the
        # first one wrote.
        return client.messages.create(
            model=MODEL, max_tokens=16, system=system, messages=messages
        )

    try:
        first = _call()
        second = _call()
    except Exception as exc:  # never expose the key
        print(f"caching: FAIL ({type(exc).__name__}: {exc})")
        return False

    write = getattr(first.usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(second.usage, "cache_read_input_tokens", 0) or 0
    if write > 0 and read > 0:
        print(f"caching: OK (write {write}, read {read})")
        return True
    print(
        f"caching: FAIL (expected write>0 then read>0; got write={write}, read={read}). "
        "If both are 0, the filler prefix may be under the 2048-token cache minimum."
    )
    return False


def main() -> int:
    client = _client()
    ok_tool_use = check_tool_use(client)
    ok_caching = check_prompt_caching(client)
    return 0 if (ok_tool_use and ok_caching) else 1


if __name__ == "__main__":
    sys.exit(main())
