"""
Pure, safety-critical application of SEARCH/REPLACE blocks to a target
string. No I/O, no model calls — this file's only job is to apply blocks
exactly or reject the whole patch untouched.

Reviewer note: every guard below exists to prevent one specific way this
function could silently corrupt the target. Read each comment before
touching the logic.
"""
from __future__ import annotations

from app.models import ApplyResult, BlockFailure, SearchReplaceBlock


def apply_patch(target: str, blocks: list[SearchReplaceBlock]) -> ApplyResult:
    """
    Apply `blocks` to `target` sequentially. ATOMIC: if any block fails to
    validate, return the ORIGINAL `target` unchanged plus a BlockFailure
    naming the first bad block — never a half-applied result.

    Why atomic all-or-nothing: a caller that gets back a partially-applied
    patch has no way to know which edits landed without diffing the result
    itself. "Fully applied" or "fully untouched" is the only contract simple
    enough to trust without re-verifying it.
    """
    # We mutate `current`, not `target`, while walking the blocks. `target`
    # itself is never touched, so returning it on failure is always correct
    # by construction — there's no "undo" step to get wrong.
    current = target

    for index, block in enumerate(blocks):
        # Guard 1: reject empty SEARCH outright. An empty string is a
        # substring of every string at every position, so "exactly one
        # match" is undefined for it — allowing it would silently become a
        # blind insertion at a position we didn't actually validate. Out of
        # scope for this MVP (spec: "no blind insertions yet").
        if block.search == "":
            return ApplyResult(
                ok=False,
                content=target,
                blocks=blocks,
                error=BlockFailure(
                    block_index=index,
                    search=block.search,
                    replace=block.replace,
                    reason="empty SEARCH is not allowed (no blind insertions in this MVP)",
                ),
            )

        match_count = current.count(block.search)

        # Guard 2: zero matches means the model's SEARCH text isn't
        # actually present in the target as it currently stands (it may
        # have hallucinated text, or be targeting text already changed by
        # an earlier block in this same patch). Applying nothing is safer
        # than guessing what was meant.
        if match_count == 0:
            return ApplyResult(
                ok=False,
                content=target,
                blocks=blocks,
                error=BlockFailure(
                    block_index=index,
                    search=block.search,
                    replace=block.replace,
                    reason="SEARCH not found in target (0 matches)",
                ),
            )

        # Guard 3: more than one match means we cannot know which
        # occurrence the model intended. Picking "the first one" would be
        # exactly the kind of silent corruption this module exists to
        # prevent, so we reject as ambiguous instead of guessing.
        if match_count > 1:
            return ApplyResult(
                ok=False,
                content=target,
                blocks=blocks,
                error=BlockFailure(
                    block_index=index,
                    search=block.search,
                    replace=block.replace,
                    reason=f"SEARCH is ambiguous: matched {match_count} times, expected exactly 1",
                ),
            )

        # Exactly one match proven above — the only mutation this module
        # performs. The `count=1` argument is not a safety mechanism here
        # (there is no second occurrence for it to skip past); it documents
        # the invariant we just proved.
        current = current.replace(block.search, block.replace, 1)

        # Sequential application: the NEXT iteration's `current.count(...)`
        # runs against this already-patched text, not the original target.
        # This lets a later block target text that only exists once an
        # earlier block in the same patch has been applied.

    return ApplyResult(ok=True, content=current, blocks=blocks, error=None)
