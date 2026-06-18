# Daily progress-report automation

Every morning this gathers our **real** progress signals, asks Claude to grade
them against our pre-committed milestone gate, and posts a short, honest report
to Slack. There is no server — **GitHub Actions** is the always-on runner.

## What it does (in order)

1. **GIT (objective, mandatory)** — commits in the last ~26h (hash · author ·
   subject), `git diff --stat` for the same window, and a test result
   (`pytest -q`; exit 0 = pass, exit 5 / no tests = pass, real failure = fail).
2. **TASKS (Notion, soft)** — recurses through the tasks page (to-dos are nested
   inside column blocks), reports checked vs unchecked counts and lists the
   checked ones.
3. **SLACK (soft)** — last 24h of channel messages via `conversations.history`.
4. **GATE + PROMPT** — reads `gate.md` and `report_prompt.txt`.
5. **Claude** — `claude-sonnet-4-6`, grades the four blocks (GIT / TASKS / SLACK
   / GATE) and writes the report.
6. **Output** — dry-run prints to stdout; live POSTs `{"text": "..."}` to the
   Slack webhook.

### Honesty / safety guarantees

- **GIT and the test result are mandatory.** If either can't be collected, the
  run **aborts** and posts a short error notice — it never grades on Slack chat
  alone (which would produce confident fiction).
- **Notion and Slack are soft.** If they fail, the run continues but labels them
  `MISSING` so Claude is told not to assume unseen progress.
- **Secrets are read from environment variables only** and are never printed or
  logged.

## Run locally (dry-run)

```bash
cd automation
cp .env.example .env          # fill in at least ANTHROPIC_API_KEY
pip install -r requirements.txt pytest   # pytest needed for the test signal
python report.py --dry        # prints the report, posts nothing
```

Dry-run is also forced automatically whenever `SLACK_WEBHOOK_URL` is unset, so
you can never accidentally post from your machine. `.env` may live in the
`automation/` folder or the repo root; values already in your real environment
take precedence and are never overwritten.

> The script reads ~26h of git history, so run it from inside the repo with its
> commits present. In CI we check out with `fetch-depth: 0` for the same reason.

## Editing the gate per milestone

`gate.md` is plain markdown and is the single source of truth for grading. When
the milestone changes, edit `gate.md`, commit it, and the next run grades
against the new criteria. The seeded content is the **M1** gate. Keep each
criterion on its own `- ` bullet and measurable so Claude can mark it
met / partial / not started.

## Changing the prompt

`report_prompt.txt` is the system prompt (the skeptical chief-of-staff grader
and the exact output format). Edit it to change tone or format.

## GitHub repo secrets to add

Add these under **Settings → Secrets and variables → Actions →
New repository secret**:

| Secret | Purpose |
| --- | --- |
| `ANTHROPIC_API_KEY` | Generate the report. |
| `SLACK_WEBHOOK_URL` | Post the report to the channel. |
| `SLACK_BOT_TOKEN` | Read channel history (`xoxb-…`). |
| `SLACK_CHANNEL_ID` | Channel to read/post (e.g. `C0123456789`). |
| `NOTION_TOKEN` | Read the tasks page. |
| `NOTION_TASKS_PAGE_ID` | `3834c206-e250-8122-adc7-e04d155679d3` |

`GITHUB_TOKEN` is provided automatically by Actions — no need to add it.

## Schedule

`.github/workflows/daily-report.yml` runs on cron `0 4 * * *`
(= **07:00 Asia/Bahrain**, UTC+3) and also supports **Run workflow**
(`workflow_dispatch`) for manual runs from the Actions tab.
