# The challenge

Source: the data room `README.md` (the full brief) and `dev/POLICY.md`. Event: Saturday 21 November 2026, code freeze 17:00, top 5 demo live at 17:30 (3 minutes each).

## Objective

For every watchlist hit, decide whether it is the customer:

| Decision | Meaning |
|---|---|
| `DIFFERENT_ENTITY` | The evidence shows a different person or company. The hit is cleared. |
| `SAME_ENTITY` | The evidence shows the hit is the customer. |
| `REVIEW` | Not enough evidence, or contradictory. A human decides. |

Identity only, not policy: how serious the listing is does not matter. An alert closes only when every hit in it is `DIFFERENT_ENTITY`, but scoring is per hit.

## Deliverable

1. `system/run <data folder> <output file>`: reads only that folder, writes one JSON line per hit, under 30 minutes. Python 3 or Node standard library, or shell. Language models only through OpenRouter with `OPENROUTER_API_KEY` (they set their own key when testing).
2. `output/dev.jsonl`: the system's predictions on the dev set. They re-run the system on dev to check it.
3. `system/README.md`: architecture (with a diagram), how we find the customer and the listed person, how evidence is represented, how runs stay deterministic, model and prompts if any, time and cost of a run, and three worked cases: a clear mismatch, a match, and one left for review.

Output line fields: `hit_id`, `alert_id`, `decision`, `reason_code` (must belong to the decision), `customer_record_id` (`CUS-######`, `AMBIGUOUS` or `null`), `reason` (2-4 sentences with this hit's own facts), `evidence` (IDs that decided it). Evidence may be record IDs, URLs, or a hit field as `H-XXXXXX#field`. `validate.py` enforces all of this.

## Scoring

Cost per hit, lower is better:

| Right answer | Said DIFFERENT | Said SAME | Said REVIEW |
|---|---|---|---|
| DIFFERENT_ENTITY | 0 | 3 | 3 |
| SAME_ENTITY | **60** | 0 | 2 |
| REVIEW | **60** | 2 | 0 |

The decision score is the share of cost saved against all-`REVIEW` (all-`REVIEW` scores 0, and so does clearing everything). Clearing only pays when we are more than about 95% sure. Some hits are not scored because the files can't settle them.

| Part | Weight | What counts |
|---|---|---|
| Unseen set (~550 hits, new customers, differently worded free text) | 80% | Decisions 75%, reasons 25% |
| Dev set | 10% | Decisions 75%, reasons 25% |
| Reproducibility (5 runs) | 10% | Same decision and reason code every run, scaled by the unseen score |

Reasons are checked on right decisions only: reason code fits, evidence cites what decided it (not everything we looked at), customer record is right, reason states the real grounds with this hit's facts.

Judges (finalists) read `system/README.md` and ask about resolving both sides, evidence, determinism, and honesty about what's missing. Event-wide judging criteria: execution, solves the problem, creativity, UX.

## Submission

Public GitHub repo with `system/` and `output/` at the deadline; submit the link with the project name. Never commit `dev/` or an API key. The last commit before the deadline is scored.
