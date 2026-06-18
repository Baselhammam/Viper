#!/usr/bin/env python3
"""
Daily progress-report automation.

Gathers real progress signals (git commits + diffstat + tests, Notion tasks,
Slack chatter), asks Claude to grade them against a pre-committed milestone gate
(gate.md), and posts a short, honest report.

Two modes:
  * Dry-run  : `python automation/report.py --dry`  (or no SLACK_WEBHOOK_URL set)
               -> prints the report to stdout, posts nothing.
  * CI / live: run inside GitHub Actions with secrets in the environment
               -> POSTs the report to SLACK_WEBHOOK_URL.

Honesty rules baked in:
  * GIT and the test result are MANDATORY. If either cannot be collected, we
    ABORT and post a short error notice instead of a confident-but-fictional
    report. We never grade on the Slack chat alone.
  * Notion and Slack are SOFT inputs. If they fail we continue, but we label
    them clearly as MISSING so Claude is told not to assume unseen progress.
  * Secrets are read from environment variables only and are never printed or
    logged.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import requests

# ---------------------------------------------------------------------------
# Config / constants
# ---------------------------------------------------------------------------

GIT_WINDOW_HOURS = 26
SLACK_WINDOW_HOURS = 24
MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

HERE = Path(__file__).resolve().parent
PROMPT_PATH = HERE / "report_prompt.txt"
GATE_PATH = HERE / "gate.md"

NOTION_VERSION = "2022-06-28"
NOTION_API = "https://api.notion.com/v1"


# ---------------------------------------------------------------------------
# Environment / secrets
# ---------------------------------------------------------------------------

def load_dotenv() -> None:
    """Load KEY=VALUE pairs from a local .env (repo root or automation/) without
    overriding anything already present in the real environment. No-op in CI,
    where there is no .env file and secrets come from the runner environment."""
    for candidate in (HERE / ".env", HERE.parent / ".env"):
        if not candidate.exists():
            continue
        for raw in candidate.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def secret(name: str) -> str | None:
    """Read a secret from the environment. Never logged."""
    val = os.environ.get(name)
    return val if val else None


# ---------------------------------------------------------------------------
# 1. GIT — objective, mandatory
# ---------------------------------------------------------------------------

class CollectionError(Exception):
    """Raised when a MANDATORY signal (git or tests) cannot be collected."""


def _run(cmd: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def collect_git(window_hours: int = GIT_WINDOW_HOURS) -> str:
    """Return a human-readable GIT block. Raises CollectionError on failure."""
    since = f"{window_hours} hours ago"

    # Confirm we are in a working git repo with history.
    check = _run(["git", "rev-parse", "--is-inside-work-tree"])
    if check.returncode != 0:
        raise CollectionError("not inside a git work tree")

    # Commits in the window: hash, author, subject.
    log = _run([
        "git", "log", f"--since={since}",
        "--pretty=format:%h %an %s",
    ])
    if log.returncode != 0:
        raise CollectionError(f"`git log` failed: {log.stderr.strip()[:200]}")
    commits_raw = log.stdout.strip()
    commit_lines = [ln for ln in commits_raw.splitlines() if ln.strip()]
    commit_count = len(commit_lines)

    # Diffstat for the same window: diff from the last commit BEFORE the window
    # up to HEAD. If there is no such base commit (very young repo), diff the
    # whole window against the empty tree.
    base = _run(["git", "rev-list", "-1", f"--before={since}", "HEAD"]).stdout.strip()
    # Git's canonical empty-tree object — portable fallback when no commit
    # predates the window (very young repo).
    empty_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"
    diff = _run(["git", "diff", "--stat", f"{base or empty_tree}..HEAD"])
    diffstat = diff.stdout.strip() if diff.returncode == 0 else "(no diffstat available)"

    test_status, test_detail = run_tests()

    commits_block = "\n".join(commit_lines) if commit_lines else "(no commits in window)"
    return (
        f"Commits in the last ~{window_hours}h ({commit_count}):\n"
        f"{commits_block}\n\n"
        f"git diff --stat (same window):\n{diffstat or '(no changes)'}\n\n"
        f"Tests: {test_status} — {test_detail}"
    )


def run_tests() -> tuple[str, str]:
    """Run the project's test command and map the exit code to a status.

    Returns (status, detail) where status is 'pass' or 'fail'.
    Raises CollectionError if the test runner cannot be executed at all
    (a missing/broken runner means we genuinely can't collect the signal).

    Per project decision: an empty pytest suite (exit 5, "no tests collected")
    counts as PASS, not as an abort.
    """
    repo_root = HERE.parent

    # Prefer `npm test` if this is a Node project.
    if (repo_root / "package.json").exists() and shutil.which("npm"):
        try:
            proc = _run(["npm", "test"], timeout=600)
        except Exception as exc:  # noqa: BLE001 - report any execution failure
            raise CollectionError(f"could not run `npm test`: {exc}")
        if proc.returncode == 0:
            return "pass", "npm test exit 0"
        return "fail", f"npm test exit {proc.returncode}"

    # Otherwise pytest. Invoke via `python -m pytest` so it works whether or not
    # a `pytest` console script is on PATH (it just needs to be importable).
    if not _pytest_available():
        raise CollectionError(
            "pytest is not installed; cannot collect a test result "
            "(install it: `pip install pytest`)"
        )
    try:
        proc = _run([sys.executable, "-m", "pytest", "-q"], timeout=600)
    except Exception as exc:  # noqa: BLE001
        raise CollectionError(f"could not run pytest: {exc}")

    code = proc.returncode
    if code == 0:
        return "pass", "pytest exit 0"
    if code == 5:
        return "pass", "pytest exit 5 (no tests collected yet)"
    if code == 1:
        return "fail", "pytest exit 1 (tests failed)"
    # 2 = interrupted, 3 = internal error, 4 = usage error -> infra problem.
    raise CollectionError(f"pytest returned exit {code} (could not collect result)")


def _pytest_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("pytest") is not None


# ---------------------------------------------------------------------------
# 2. TASKS — Notion (SOFT input)
# ---------------------------------------------------------------------------

def _notion_children(page_or_block_id: str, token: str) -> list[dict]:
    """Fetch all child blocks of a page/block, following pagination."""
    blocks: list[dict] = []
    cursor: str | None = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
    }
    while True:
        params = {"page_size": 100}
        if cursor:
            params["start_cursor"] = cursor
        resp = requests.get(
            f"{NOTION_API}/blocks/{page_or_block_id}/children",
            headers=headers,
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        blocks.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        cursor = data.get("next_cursor")
    return blocks


def _rich_text_plain(rich_text: list[dict]) -> str:
    return "".join(rt.get("plain_text", "") for rt in rich_text).strip()


def collect_notion() -> str:
    """Recurse through the tasks page (to_do blocks live inside column blocks)
    and report checked vs unchecked counts plus the checked items.

    SOFT input: on any failure, returns a block clearly labelled MISSING."""
    token = secret("NOTION_TOKEN")
    page_id = secret("NOTION_TASKS_PAGE_ID")
    if not token or not page_id:
        return "MISSING — NOTION_TOKEN or NOTION_TASKS_PAGE_ID not set. Do not assume task progress."

    todos: list[tuple[bool, str]] = []  # (checked, text)

    def walk(block_id: str, depth: int = 0) -> None:
        if depth > 8:  # safety against pathological nesting / cycles
            return
        for block in _notion_children(block_id, token):
            btype = block.get("type")
            if btype == "to_do":
                checked = bool(block["to_do"].get("checked"))
                text = _rich_text_plain(block["to_do"].get("rich_text", []))
                todos.append((checked, text or "(empty to-do)"))
            if block.get("has_children"):
                walk(block["id"], depth + 1)

    try:
        walk(page_id)
    except Exception as exc:  # noqa: BLE001 - SOFT input, never crash
        return f"MISSING — Notion unavailable ({type(exc).__name__}). Do not assume task progress."

    if not todos:
        return "No to-do checkboxes found under the tasks page."

    checked = [t for done, t in todos if done]
    unchecked_count = len(todos) - len(checked)
    lines = [
        f"Checked: {len(checked)} · Unchecked: {unchecked_count} (total {len(todos)})",
    ]
    if checked:
        lines.append("Checked items (CLAIMS — verify against GIT):")
        lines.extend(f"  [x] {t}" for t in checked)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 3. SLACK history — last 24h (SOFT input)
# ---------------------------------------------------------------------------

def collect_slack() -> str:
    """Pull the last 24h of channel messages. SOFT input: on any failure,
    returns 'Slack unavailable' and continues."""
    token = secret("SLACK_BOT_TOKEN")
    channel = secret("SLACK_CHANNEL_ID")
    if not token or not channel:
        return "MISSING — SLACK_BOT_TOKEN or SLACK_CHANNEL_ID not set. Do not assume discussion happened."

    oldest = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=SLACK_WINDOW_HOURS)).timestamp()
    try:
        resp = requests.get(
            "https://slack.com/api/conversations.history",
            headers={"Authorization": f"Bearer {token}"},
            params={"channel": channel, "oldest": f"{oldest:.6f}", "limit": 200},
            timeout=30,
        )
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        return f"Slack unavailable ({type(exc).__name__}). Do not assume discussion happened."

    if not data.get("ok"):
        return f"Slack unavailable (error: {data.get('error', 'unknown')}). Do not assume discussion happened."

    messages = data.get("messages", [])
    texts = [m.get("text", "").strip() for m in messages if m.get("text", "").strip()]
    if not texts:
        return "No Slack messages in the last 24h."
    # Oldest-first for readability.
    return "\n".join(f"- {t}" for t in reversed(texts))


# ---------------------------------------------------------------------------
# 4/5. Gate + prompt + Claude
# ---------------------------------------------------------------------------

def read_text(path: Path, label: str) -> str:
    if not path.exists():
        raise CollectionError(f"{label} file missing: {path}")
    return path.read_text(encoding="utf-8").strip()


def build_user_message(git: str, tasks: str, slack: str, gate: str, today: str) -> str:
    return (
        f"Date: {today}\n\n"
        f"=== GIT ===\n{git}\n\n"
        f"=== TASKS ===\n{tasks}\n\n"
        f"=== SLACK ===\n{slack}\n\n"
        f"=== GATE ===\n{gate}\n"
    )


def call_claude(system_prompt: str, user_message: str) -> str:
    api_key = secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise CollectionError("ANTHROPIC_API_KEY not set")
    # Imported lazily so dry-run plumbing can be exercised without the SDK
    # present until the actual call is needed.
    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return "".join(block.text for block in resp.content if block.type == "text").strip()


# ---------------------------------------------------------------------------
# 6. Output
# ---------------------------------------------------------------------------

def post_to_slack(webhook: str, text: str) -> None:
    resp = requests.post(webhook, json={"text": text}, timeout=30)
    resp.raise_for_status()


def deliver(text: str, *, dry: bool, webhook: str | None) -> None:
    if dry or not webhook:
        print(text)
        return
    post_to_slack(webhook, text)
    print("Report posted to Slack.")


def deliver_error(message: str, *, dry: bool, webhook: str | None) -> None:
    """ABORT path: emit a short, honest error notice (never a fake report)."""
    today = dt.date.today().isoformat()
    notice = (
        f":rotating_light: Daily report ABORTED — {today}\n"
        f"No report was generated. We refuse to grade on incomplete ground-truth "
        f"or guesswork — that would produce confident fiction.\n"
        f"Reason: {message}"
    )
    if dry or not webhook:
        print(notice)
        return
    try:
        post_to_slack(webhook, notice)
        print("Error notice posted to Slack.")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to post error notice: {exc}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description="Daily progress report")
    parser.add_argument("--dry", action="store_true",
                        help="Print to stdout, post nothing (forced if no SLACK_WEBHOOK_URL).")
    args = parser.parse_args()

    # The report (and error notices) contain em-dashes and emoji; make stdout
    # UTF-8 so local dry-runs on a legacy Windows console don't crash.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001 - older/odd streams; best effort
            pass

    load_dotenv()
    webhook = secret("SLACK_WEBHOOK_URL")
    dry = args.dry or not webhook

    # --- Mandatory ground truth (abort on failure) ---
    try:
        git_block = collect_git()
        gate = read_text(GATE_PATH, "gate.md")
        prompt = read_text(PROMPT_PATH, "report_prompt.txt")
    except CollectionError as exc:
        deliver_error(str(exc), dry=dry, webhook=webhook)
        return 1
    except Exception as exc:  # noqa: BLE001 - unexpected mandatory-signal failure
        deliver_error(f"unexpected error collecting ground truth: {type(exc).__name__}",
                      dry=dry, webhook=webhook)
        return 1

    # --- Soft inputs (continue, label clearly if missing) ---
    tasks_block = collect_notion()
    slack_block = collect_slack()

    today = dt.date.today().isoformat()
    user_message = build_user_message(git_block, tasks_block, slack_block, gate, today)

    try:
        report = call_claude(prompt, user_message)
    except CollectionError as exc:
        deliver_error(str(exc), dry=dry, webhook=webhook)
        return 1
    except Exception as exc:  # noqa: BLE001
        deliver_error(f"Claude call failed: {type(exc).__name__}", dry=dry, webhook=webhook)
        return 1

    deliver(report, dry=dry, webhook=webhook)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
