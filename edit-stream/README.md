# edit-stream

MVP backend proving one loop: given a text target and a prompt, stream back a
structured set of range-based edits (`EditOp`) that a client can apply
incrementally. **This is a validation harness for the loop, not a product** —
no auth, no DB, no frontend.

## SDK versions verified against (2026-06-18)

Docs checked live at `docs.claude.com` (redirects to `platform.claude.com`):
- Prompt caching (`cache_control`, minimum cacheable tokens, usage fields):
  `/docs/en/build-with-claude/prompt-caching`
- Tool use / `tool_choice`: `/docs/en/build-with-claude/tool-use/overview`
- Streaming events (`content_block_delta`, `input_json_delta`):
  `/docs/en/api/messages-streaming`
- Python SDK (`AsyncAnthropic`, `messages.stream`): `/docs/en/cli-sdks-libraries/sdks/python`

Package: `anthropic` (`pip install anthropic`, Python 3.9+). Default model:
`claude-sonnet-4-6` (Sonnet-class has a 1,024-token prompt-cache minimum vs.
4,096 for Haiku-class, making the cache demo easier to trigger).

## Architecture

- `app/provider.py` — the stable seam: `EditProvider` Protocol with one
  method, `stream_edits(target, prompt) -> AsyncIterator[EditOp]`.
- `app/anthropic_provider.py` — the ONLY file that imports the Anthropic SDK.
  Implements `EditProvider` via the Messages API: forces a single
  `propose_edits` tool call (never prose), marks the system prompt and the
  target content as cache breakpoints, and streams `EditOp`s out as the
  tool's JSON input is parsed.
- `app/models.py` — `Target`, `EditOp` (LSP-style range edit:
  `start`/`end`/`replacement`), `EditRequest`.
- `app/main.py` — FastAPI app, one endpoint: `POST /edit` -> SSE stream of
  `EditOp` events.

A future on-device or different-vendor provider implements `EditProvider`
and is dropped in by changing one line in `app/main.py` — no caller changes.

## Run

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # required; never hardcode this
export MODEL=claude-sonnet-4-6        # optional, defaults to claude-sonnet-4-6
uvicorn app.main:app --reload
```

## Try it

```bash
python test_edit_stream.py
```

This posts the same target twice with different prompts and prints each
streamed `EditOp`. Watch the **server's** stdout for lines like:

```
final usage: input=12 cache_creation=1342 cache_read=0 output=89
final usage: input=15 cache_creation=0 cache_read=1342 output=64
```

`cache_read_input_tokens > 0` on the second call confirms the target content
was served from cache rather than re-processed.

## Manual cancellation check

Start a request, then kill the client mid-stream (e.g. Ctrl-C `curl`, or
close the connection from `httpx`). The server log should show:

```
client disconnected mid-stream; aborting upstream request
```

and the process should NOT keep streaming/logging further `EditOp`s for that
request — the upstream Anthropic call is aborted, and no partially-parsed
edit is ever emitted (see `_try_emit_complete` in `anthropic_provider.py`).

## Env vars

| Var | Required | Default | Purpose |
|---|---|---|---|
| `ANTHROPIC_API_KEY` | yes | — | Read directly by the `anthropic` SDK. Never logged, never returned. |
| `MODEL` | no | `claude-sonnet-4-6` | Model used for diff generation. |

## Out of scope (intentionally)

No auth/users/sessions/DB, no multi-provider abstraction beyond
`EditProvider` + one implementation, no frontend, no per-platform document
models — target is plain text.
