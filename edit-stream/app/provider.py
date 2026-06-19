"""
The provider boundary — the stable seam.

Callers depend only on `EditProvider`. All vendor-specific code (Anthropic,
or any future on-device/different-vendor implementation) must live behind
this interface and never leak upward.

Note: this returns the full block list in one shot, not a stream. Atomic
all-or-nothing validation (app/applier.py) requires every block to be known
before any of them can be safely applied, so there is nothing useful to
stream incrementally to a caller — see anthropic_provider.py.
"""
from __future__ import annotations

from typing import Protocol

from app.models import SearchReplaceBlock, Target


class EditProvider(Protocol):
    async def propose_patch(self, target: Target, prompt: str) -> list[SearchReplaceBlock]:
        """
        Return the model's proposed SEARCH/REPLACE blocks for `prompt`
        applied to `target`. Does not validate or apply them — that's
        app/applier.py's job.
        """
        ...
