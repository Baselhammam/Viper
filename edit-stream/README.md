# edit-stream

MVP backend proving one loop: given a text target and a prompt, return a
validated set of SEARCH/REPLACE blocks that have already been applied (or
atomically rejected) against the target. **This is a validation harness for
the loop, not a product** — no auth, no DB, no frontend.

## SDK versions verified against (2026-06-19)

Docs checked live at `docs.claude.com` (redirects to `platform.claude.com`):
- Tool use / structured output (`input_schema`, `strict`, `tool_choice`):
  `/docs/en/agents-and-tools/tool-use/define-tools`
- Forcing a specific tool call (`tool_choice={"type": "tool", "name": ...}`):
  same page
- Current model ids (Sonnet/Haiku/Opus-class aliases):
  `/docs/en/about-claude/models/overview`
- Prompt caching (`cache_control`, usage fields): `/docs/en/build-with-claude/prompt-caching`

Package: `anthropic` (`pip install anthropic`, Python 3.9+). Default model:
`claude-sonnet-4-6`, overridable via the `MODEL` env var (see Settings below).

## Diff format: SEARCH/REPLACE blocks

The model proposes one or more blocks, conceptually shaped like:

```
<<<<<<< SEARCH
<exact existing text from the target>
=======
<replacement text>
>>>>>>> REPLACE
```

On the wire this is a structured tool call (`propose_patch`, with a
`blocks: [{search, replace}, ...]` array), not raw delimited text — the
marker strings above are config (`SEARCH_MARKER`/`DIVIDER_MARKER`/
`REPLACE_MARKER` in Settings) used only to illustrate the grammar in the
system prompt.

Validation rules, enforced by `app/applier.py` (atomic, all-or-nothing):
- `search` must be an exact, verbatim substring of the **current** text
  (blocks apply sequentially, so block N searches the result of blocks
  `0..N-1`).
- 0 matches -> reject the whole patch.
- >1 matches (ambiguous) -> reject the whole patch; never guess which one.
- empty `search` -> reject (no blind insertions in this MVP).
- If any block fails any of the above, the original target is returned
  byte-for-byte unchanged, plus a structured error naming the failing block
  index and reason. There is no partial application.

There is no streaming: atomic whole-patch validation needs every block
before any of them can be safely applied, so a single non-streaming
`messages.create()` call (returning the already-parsed tool `.input`) is
both simpler and sufficient.

## Architecture

- `app/provider.py` — the stable seam: `EditProvider` Protocol with one
  method, `propose_patch(target, prompt) -> list[SearchReplaceBlock]`.
- `app/anthropic_provider.py` — the ONLY file that imports the Anthropic
  SDK. Implements `EditProvider` via the Messages API: forces a single
  `propose_patch` tool call (never prose, via `tool_choice`), marks the
  system prompt and the target content as separate cache breakpoints, and
  validates every returned block into a `SearchReplaceBlock` (rejecting the
  whole response if any block is malformed).
- `app/models.py` — `Target`, `EditRequest`, `SearchReplaceBlock`,
  `BlockFailure`, `ApplyResult`.
- `app/applier.py` — the safety-critical, pure `apply_patch(target, blocks)`
  function. No I/O, no model calls; see "Diff format" above for the
  invariants it enforces.
- `app/settings.py` — single source of truth for all configuration (see
  below).
- `app/main.py` — FastAPI app, one endpoint: `POST /edit` -> `ApplyResult`
  (already validated and, if `ok`, already applied).

A future on-device or different-vendor provider implements `EditProvider`
and is dropped in by changing one line in `app/main.py` — no caller changes.

## Settings

All configuration lives in `app/settings.py` (`pydantic-settings`
`BaseSettings`), loaded from environment variables and an optional `.env`
file. No inline `os.environ` reads or hardcoded constants live anywhere
else in the codebase.

```bash
cp .env.example .env
# edit .env and set ANTHROPIC_API_KEY
```

| Var | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | Read from env only. Never hardcoded, never logged, never returned — the settings object's `repr`/`str` redact it (`pydantic.SecretStr`). |
| `MODEL` | no | `claude-sonnet-4-6` | Model used for diff generation. |
| `MAX_OUTPUT_TOKENS` | no | `4096` | Per-request cost guard, ties to the spend cap. |
| `REQUEST_TIMEOUT_S` | no | `60.0` | Anthropic client request timeout. |
| `SEARCH_MARKER` | no | `<<<<<<< SEARCH` | Block delimiter shown to the model (illustrative only — actual wire format is the structured tool call). |
| `DIVIDER_MARKER` | no | `=======` | Block delimiter between search and replace text. |
| `REPLACE_MARKER` | no | `>>>>>>> REPLACE` | Block delimiter closing a block. |

## Run

```bash
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
uvicorn app.main:app --reload
```

## Try it

```bash
python test_edit_stream.py
```

This posts the same target to `/edit` twice with different prompts and
prints each returned `ApplyResult`. Watch the **server's** stdout for lines
like:

```
usage: input=12 cache_creation=1342 cache_read=0 output=89
usage: input=15 cache_creation=0 cache_read=1342 output=64
```

`cache_read_input_tokens > 0` on the second call confirms the target content
was served from cache rather than re-processed.

## Tests

```bash
pip install -r requirements-dev.txt
PYTHONPATH=. pytest tests/ -q
```

`tests/test_applier.py` is a Hypothesis property suite: for any target and
any list of blocks, `apply_patch` either returns the exact, fully-patched
result, or rejects and returns the original target untouched — never
anything in between.

## Out of scope (intentionally)

No auth/users/sessions/DB, no multi-provider abstraction beyond
`EditProvider` + one implementation, no frontend, no per-platform document
models (target is plain text), no streaming, no blind-insertion (empty
SEARCH) support.
