# StyleClone Studio — in-browser AI page editor

Type a prompt, get a single self-contained HTML page rendered live in a sandboxed
iframe, then edit it by **clicking elements**: only the clicked element + your
instruction go to the model, and only its replacement is swapped back in — the
whole document is never re-sent or regenerated. That scoped-edit loop is the
product's core cost lever.

## What's here
| Path | What it is |
|---|---|
| `src/`, `index.html`, `vite.config.ts` | **The product** — Vite + React + TS frontend (scoped-edit MVP). |
| `scripts/verify_access.py` | One-off check that Anthropic access works (tool use + prompt caching). |
| `docs/metrics-and-gates.md` | Milestone pass/fail targets and kill thresholds (M0–M4). |
| `Viper/` | Separate, older Ollama "screen-helper" project — **not** part of the editor. |
| `automation/`, `.claude/skills/code-auditor/`, `.github/workflows/` | Dev tooling: daily report + code audit. |

## Run the editor (local dev)
```bash
npm install
cp .env.example .env        # then set ANTHROPIC_API_KEY
npm run dev                 # open the printed http://localhost:5173
```
The page render, click-to-select, and Before/After panel work without a key; only
the model edit needs one. The key stays server-side — the Vite dev server proxies
`/api/anthropic` → `api.anthropic.com` and injects the key, so it never ships to the
browser. (Behind a TLS-intercepting corporate proxy? See `ANTHROPIC_PROXY_INSECURE_TLS`
in `.env.example`.)

## Verify Anthropic access
After setting `ANTHROPIC_API_KEY` in your environment:
```bash
pip install -r requirements.txt
python scripts/verify_access.py
```
Prints `tool-use: OK` and `caching: OK (write N, read M)` and exits 0 when both checks
pass; exits non-zero otherwise. The key is never printed.
