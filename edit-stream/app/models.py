"""Small, stable data models shared across the provider boundary."""
from __future__ import annotations

from pydantic import BaseModel


class Target(BaseModel):
    """The text buffer a client wants edited (e.g. a code file)."""

    content: str
    language: str | None = None


class EditOp(BaseModel):
    """
    A single range-based text edit, modeled on the LSP TextEdit shape:
    replace target.content[start:end] with `replacement`.

    Range edits (not JSON Patch) are the natural contract here because the
    target is a flat text buffer, not a tree/document with a path structure.
    """

    start: int
    end: int
    replacement: str


class EditRequest(BaseModel):
    target: Target
    prompt: str
