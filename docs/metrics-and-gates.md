# Metrics & Gates

Pass/fail numbers and **kill** conditions per milestone. **All numbers are `v1 default — confirm/adjust`.**
Columns: **Metric** · **How it's measured** · **Target (pass)** · **Kill threshold (stop/pivot)**.

## M0 — Foundations (brief)
| Metric | How it's measured | Target (pass) | Kill threshold |
|---|---|---|---|
| Forks locked | Target type + owned surface written down & agreed | Yes | No |
| Proxy returns a real diff | Hit the proxy with a sample target+prompt; inspect response | Yes — a real, parseable diff | No diff after the integration spike |

## M1 — Incremental edit beats regeneration *(the make-or-break milestone)*
| Metric | How it's measured | Target (pass) | Kill threshold |
|---|---|---|---|
| Edit-size distribution | Log every accepted edit; classify each as *tweak* vs *full rewrite* (changed-region ÷ doc size) over real usage | **≥40%** of real edits are tweaks | **<25%** |
| Patch-validity | % of patches that apply cleanly after **≤1** repair retry, over a representative sample | **≥95%** | **<80%** |
| Output-token reduction vs full regeneration | Same edits done two ways; compare output tokens of the incremental slice vs regenerating the whole doc | **60–80% fewer** | **<40% fewer** |
| Quality (applied diff vs regeneration) | LLM judge rates applied-diff ≥ regeneration; human spot-check on a sample | applied diff rated **≥ regen on ≥85%** of cases | **<70%** |
| Latency to first streamed op | Time from request → first streamed edit op (p50/p95) | **≤ ~1.5s** | **>3s** |

## M2 — Takeover holds under stress (brief)
| Metric | How it's measured | Target (pass) | Kill threshold |
|---|---|---|---|
| Efficiency vs M1 baseline | Round-trips + output-tokens per completed edit | Both **beat** the M1 baseline | Regresses below M1 |
| State integrity | Takeover/abort battery (abort mid-stream, repeatedly) | **Zero** state corruption | Any corruption |

## M3 — Lands in a third-party app (brief)
| Metric | How it's measured | Target (pass) | Kill threshold |
|---|---|---|---|
| Real edit in a third-party app | End-to-end run against a real external app | Edit lands; consent + data-egress documented; **engine unchanged** | Can't land without changing the engine |

## M4 — iOS reach, same engine (brief)
| Metric | How it's measured | Target (pass) | Kill threshold |
|---|---|---|---|
| iOS parity | Run the **identical** engine on iOS | Reaches iOS; loop metrics (M1) still hold | Needs a forked engine, or M1 metrics break |
