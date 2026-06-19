"""
Property tests for app/applier.py.

The goal here isn't covering specific examples — it's the invariant: for
ANY target and ANY list of blocks, apply_patch() either (a) returns the
exact, fully-patched result, or (b) rejects and returns the ORIGINAL target
untouched. It must never return something in between.
"""
from __future__ import annotations

from hypothesis import given, strategies as st

from app.applier import apply_patch
from app.models import SearchReplaceBlock

# Small alphabet -> short strings collide often, which is exactly what we
# want: it forces both the "unique match" and "ambiguous match" code paths
# to actually get exercised by the fuzzer instead of almost always landing
# on "0 matches" for arbitrary unrelated random text.
_ALPHABET = "abc"
_short_text = st.text(alphabet=_ALPHABET, min_size=0, max_size=12)


@st.composite
def _target_and_real_substring(draw):
    """A target string plus a SEARCH that is guaranteed to occur in it."""
    target = draw(st.text(alphabet=_ALPHABET, min_size=1, max_size=20))
    start = draw(st.integers(min_value=0, max_value=len(target) - 1))
    end = draw(st.integers(min_value=start + 1, max_value=len(target)))
    return target, target[start:end]


@given(_target_and_real_substring(), _short_text)
def test_single_block_real_substring_never_corrupts(pair, replace):
    target, search = pair
    block = SearchReplaceBlock(search=search, replace=replace)
    result = apply_patch(target, [block])

    match_count = target.count(search)
    if match_count == 1:
        assert result.ok is True
        assert result.content == target.replace(search, replace, 1)
    else:
        # 0 matches is impossible here (search is drawn from target), so
        # this branch is the ambiguous (>1 match) case.
        assert match_count > 1
        assert result.ok is False
        assert result.content == target  # untouched, byte-for-byte
        assert result.error is not None
        assert "ambiguous" in result.error.reason


@given(st.text(alphabet=_ALPHABET, min_size=0, max_size=20), _short_text)
def test_unrelated_search_with_zero_matches_is_rejected_untouched(target, search):
    """SEARCH not derived from the target — almost always 0 matches."""
    if target.count(search) != 0:
        return  # rare collision; other tests cover the match-found paths
    block = SearchReplaceBlock(search=search, replace="anything")
    result = apply_patch(target, [block])
    assert result.ok is False
    assert result.content == target
    assert result.error is not None
    assert "0 matches" in result.error.reason


@given(st.text(alphabet=_ALPHABET, min_size=0, max_size=20), _short_text)
def test_empty_search_always_rejected_untouched(target, replace):
    block = SearchReplaceBlock(search="", replace=replace)
    result = apply_patch(target, [block])
    assert result.ok is False
    assert result.content == target
    assert result.error is not None
    assert result.error.block_index == 0
    assert "empty SEARCH" in result.error.reason


@given(
    st.text(alphabet=_ALPHABET, min_size=4, max_size=30),
    st.lists(_short_text, min_size=1, max_size=4),
)
def test_sequential_blocks_chain_against_already_patched_text(target, replacements):
    """
    Build a chain of blocks where each block's SEARCH is taken from the
    text as it stands AFTER previous blocks were (conceptually) applied,
    so each one is guaranteed unique at the point it's applied. Confirms
    sequential application matches manual step-by-step replacement.
    """
    current = target
    blocks = []
    for replacement in replacements:
        if not current:
            break
        # Pick a single unique character occurrence to search for, by
        # inserting a sentinel marker that cannot already collide.
        search = current[:1]
        if current.count(search) != 1:
            break  # not unique at this step; stop building the chain here
        blocks.append(SearchReplaceBlock(search=search, replace=replacement))
        current = current.replace(search, replacement, 1)

    if not blocks:
        return

    result = apply_patch(target, blocks)
    assert result.ok is True
    assert result.content == current


@given(
    st.text(alphabet=_ALPHABET, min_size=1, max_size=15),
    st.lists(
        st.tuples(_short_text, _short_text),
        min_size=1,
        max_size=5,
    ),
)
def test_never_returns_partial_result_on_arbitrary_block_lists(target, raw_pairs):
    """
    Fully arbitrary blocks (search/replace pairs with no relationship to
    the target). Whatever happens, the result must be self-consistent:
    ok=True implies a real, derivable transformation; ok=False implies the
    original target, untouched, byte-for-byte.
    """
    blocks = [SearchReplaceBlock(search=s, replace=r) for s, r in raw_pairs]
    result = apply_patch(target, blocks)

    if result.ok:
        # Replay the same blocks manually and confirm the result matches —
        # i.e. apply_patch did not diverge from straightforward sequential
        # single-occurrence replacement.
        current = target
        for block in blocks:
            assert current.count(block.search) == 1
            current = current.replace(block.search, block.replace, 1)
        assert result.content == current
    else:
        assert result.content == target
        assert result.error is not None
