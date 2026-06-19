#!/usr/bin/env bash
# Daily code audit wrapper. A skill is model-invoked context and cannot schedule
# or scope itself; this script is the scheduler's hands.
set -euo pipefail
REPO_DIR="${REPO_DIR:-$(git rev-parse --show-toplevel)}"
SPEC="${SPEC:-}"
OUT_DIR="${OUT_DIR:-$REPO_DIR/audits}"
STATE_FILE="${STATE_FILE:-$REPO_DIR/.claude/state/code-auditor-last-sha}"
LOCK_FILE="${LOCK_FILE:-/tmp/code-auditor.lock}"
MODEL="${MODEL:-sonnet}"
MAX_TURNS="${MAX_TURNS:-25}"
MAX_BUDGET_USD="${MAX_BUDGET_USD:-2}"
ALLOWED_TOOLS="${ALLOWED_TOOLS:-Read,Grep,Glob,Bash(git diff:*),Bash(git log:*),Bash(git show:*),Bash(git rev-parse:*),Bash(git diff-tree:*)}"
cd "$REPO_DIR"; mkdir -p "$OUT_DIR" "$(dirname "$STATE_FILE")"
exec 9>"$LOCK_FILE"; if ! flock -n 9; then echo "another audit holds the lock; exiting" >&2; exit 0; fi
HEAD_SHA="$(git rev-parse HEAD)"
if [[ -f "$STATE_FILE" ]] && git cat-file -e "$(cat "$STATE_FILE")^{commit}" 2>/dev/null; then
  LAST_SHA="$(cat "$STATE_FILE")"; RANGE="${LAST_SHA}..${HEAD_SHA}"
else
  LAST_SHA="$(git rev-list -1 --before='24 hours ago' HEAD || true)"; RANGE="${LAST_SHA:+$LAST_SHA..}${HEAD_SHA}"
fi
if [[ "${LAST_SHA:-}" == "$HEAD_SHA" ]] || [[ -z "$(git diff --name-only "$RANGE")" ]]; then
  echo "no changes since last audit"; echo "$HEAD_SHA" > "$STATE_FILE"; exit 0
fi
PROMPT="Use the code-auditor skill. RANGE=${RANGE}. SPEC=${SPEC:-<none>}.
Audit only the changes in RANGE. Output only the JSON report per the skill's schema."
REPORT_JSON="$OUT_DIR/$(date +%F).json"; RUN_LOG="$OUT_DIR/$(date +%F).log"
set +e
RAW="$(claude -p "$PROMPT" --model "$MODEL" --allowedTools "$ALLOWED_TOOLS" --permission-mode dontAsk --max-turns "$MAX_TURNS" --max-budget-usd "$MAX_BUDGET_USD" --output-format json 2>"$RUN_LOG")"
STATUS=$?; set -e
if [[ $STATUS -ne 0 ]]; then echo "claude run failed (exit $STATUS); see $RUN_LOG" >&2; exit $STATUS; fi
echo "$RAW" | jq -r '.result' > "$REPORT_JSON"
if ! jq empty "$REPORT_JSON" 2>/dev/null; then echo "auditor returned non-JSON; state NOT advanced; see $REPORT_JSON" >&2; exit 1; fi
echo "$HEAD_SHA" > "$STATE_FILE"
echo "audit written: $REPORT_JSON"
jq -r '.findings | group_by(.severity)[] | "\(.[0].severity): \(length)"' "$REPORT_JSON" || true
