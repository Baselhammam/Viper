"""Small, stable data models shared across the provider boundary."""
from __future__ import annotations

from pydantic import BaseModel


class Target(BaseModel):
    """The text buffer a client wants edited (e.g. a code file)."""

    content: str
    language: str | None = None


class SearchReplaceBlock(BaseModel):
    """
    A single SEARCH/REPLACE block. `search` must be an exact substring of
    the (current) target — the model reproduces real text to locate an
    edit point rather than computing character offsets.
    """

    search: str
    replace: str


class EditRequest(BaseModel):
    target: Target
    prompt: str


class BlockFailure(BaseModel):
    """Identifies exactly which block failed validation/application, and why."""

    block_index: int
    search: str
    replace: str
    reason: str


class ApplyResult(BaseModel):
    """
    Outcome of applying a list of SearchReplaceBlocks to a target.

    `ok=True`  -> `content` is the fully-patched target; `error` is None.
    `ok=False` -> `content` is the ORIGINAL target, byte-for-byte unchanged;
                  `error` names the first block that failed and why. No
                  partial application ever leaks through this contract.
    """

    ok: bool
    content: str
    blocks: list[SearchReplaceBlock]
    error: BlockFailure | None = None
