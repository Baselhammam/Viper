"""
FastAPI app exposing a single endpoint: POST /edit -> SSE stream of EditOps.

ANTHROPIC_API_KEY is read by the Anthropic SDK directly from the
environment; this module never touches it, logs it, or returns it.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

from app.anthropic_provider import AnthropicEditProvider
from app.models import EditRequest
from app.provider import EditProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edit_stream.main")

app = FastAPI(title="edit-stream", version="0.1.0")

# One provider instance for the process. Swapping implementations means
# changing this one line — no other code depends on AnthropicEditProvider.
_provider: EditProvider = AnthropicEditProvider()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/edit")
async def edit(req: EditRequest, request: Request) -> EventSourceResponse:
    async def event_generator():
        # `aclosing` guarantees `.aclose()` runs on the provider's async
        # generator no matter how we leave this block (early `return`,
        # `break`, or an exception/CancelledError from a dropped
        # connection). `.aclose()` throws GeneratorExit into the suspended
        # generator at its current `yield` inside AnthropicEditProvider,
        # which propagates out through the `async with client.messages
        # .stream(...)` block and runs its `__aexit__`, closing the HTTP
        # connection to Anthropic and aborting the in-flight request.
        # Without this, a `break` alone would leave the generator (and the
        # upstream request) suspended but never cleaned up.
        gen = _provider.stream_edits(req.target, req.prompt)
        try:
            async with contextlib.aclosing(gen):
                async for op in gen:
                    if await request.is_disconnected():
                        logger.info("client disconnected mid-stream; aborting upstream request")
                        break
                    yield {"event": "edit_op", "data": op.model_dump_json()}
        except asyncio.CancelledError:
            logger.info("stream cancelled; upstream request aborted")
            raise

    return EventSourceResponse(event_generator())
