"""
The provider boundary — the stable seam.

Callers depend only on `EditProvider`. All vendor-specific code (Anthropic,
or any future on-device/different-vendor implementation) must live behind
this interface and never leak upward.
"""
from __future__ import annotations

from typing import AsyncIterator, Protocol

from app.models import EditOp, Target


class EditProvider(Protocol):
    def stream_edits(self, target: Target, prompt: str) -> AsyncIterator[EditOp]:
        """
        Stream a sequence of EditOps for `prompt` applied to `target`.

        Implementations MUST only yield an EditOp once it is fully formed
        (never a partially-parsed or speculative edit) — see the Anthropic
        implementation for why this matters under cancellation.
        """
        ...
