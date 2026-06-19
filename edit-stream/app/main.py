"""
FastAPI app exposing a single endpoint: POST /edit -> a single, validated
ApplyResult (M0 scope: a proxy that returns a real, validated SEARCH/REPLACE
diff — see app/provider.py for why this isn't streamed).

ANTHROPIC_API_KEY is read once by app/settings.py; this module never touches
it, logs it, or returns it.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.anthropic_provider import AnthropicEditProvider
from app.applier import apply_patch
from app.models import ApplyResult, EditRequest
from app.provider import EditProvider

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edit_stream.main")

app = FastAPI(title="edit-stream", version="0.2.0")

# One provider instance for the process. Swapping implementations means
# changing this one line — no other code depends on AnthropicEditProvider.
_provider: EditProvider = AnthropicEditProvider()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/edit", response_model=ApplyResult)
async def edit(req: EditRequest) -> ApplyResult:
    blocks = await _provider.propose_patch(req.target, req.prompt)
    result = apply_patch(req.target.content, blocks)
    if not result.ok:
        logger.info("patch rejected: %s", result.error)
    return result
