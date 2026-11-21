# Roadmap to 17:00

Two lanes that only meet at agreed interfaces (`brain/approach.md`, "Interfaces"). Each person owns their files; touch the other lane's files only after agreeing.

- **Lane A, customer side (linhuang99):** `system/data.py`, `system/link.py`
- **Lane B, hit side (garyyehhh):** `system/common.py`, `system/names.py`, `system/hitfacts.py`
- **Shared:** `system/decide.py`, `system/run`, `system/README.md`

## Where the points are

On the 50 practice labels, sending everything to `REVIEW` costs 108. Correctly clearing the 28 `DIFFERENT_ENTITY` hits saves 84 of that (78%), confirming the 12 `SAME_ENTITY` hits saves 24. But **one unsafe clearance costs 60**, wiping out 20 correct clears. So: clear often, but only on a hard contradiction, and anything unfinished answers `REVIEW` (worst case 2-3 per hit, never 60). `LOCATION_MISMATCH` alone is behind 15+ of the 28 clears, so countries on both sides matter most.

## Phases

| Time | Lane A (customer side) | Lane B (hit side) | Done when |
|---|---|---|---|
| **12:20-12:50** Skeleton | `data.py`: load every file, build the indexes in "Interfaces" | `common.py`: `parse_date`, `country_name`. Stub `names.py`, `hitfacts.py`, `link.py`, `decide.py` with the agreed signatures, wired into `system/run` | `system/run` runs end to end through the stubs, still all `REVIEW`; pushed |
| **12:50-14:00** Core | `link.py`: follow `account_ref` / `login_handle` / `email`, pick the joint holder that fits, build `Person` with verified facts from approved KYC checks and KYC notes | `names.py` (principle 8, with unit tests). `hitfacts.py`: names, `dobs`, countries, `deceased_date`, earliest dated report | Each module has unit tests on hand-made inputs and passes them |
| **14:00-14:45** First real score | Unlinked alerts: search customers by the screened details. Merge records into people (phone + dob, document number) | `decide.py`: contradictions, then agreement, then `REVIEW`; reason text and evidence from the facts' sources | `validate.py` shows a score above 0 with **0 unsafe clearances**; pushed |
| **14:45-15:00** Prepare | List the customer-side misses | List the hit-side misses | 3-5 hard cases written down for office hours |
| **15:00-15:30** Office hours | Ask mentors about the hard cases | Same | Answers recorded in `brain/decisions.md` |
| **15:30-16:15** Improve | Fix customer-side misses: notes that add countries, ambiguity across several people | Fix hit-side misses: dob from profile notes (age at a date), search results filtered by listing phrase and country | Score up, still 0 unsafe; two runs give identical output |
| **16:15-16:40** Write up | Reason quality pass: each reason names this hit's facts | `system/README.md`: diagram, both sides, evidence, determinism, run time, three worked cases | README complete |
| **16:40-17:00** Freeze | Final run, `validate.py`, commit `output/dev.jsonl` | Make the repo public, submit the link, record the demo video | Submitted before 17:00 |

## Sync points

Five minutes, both of you, at **12:50, 14:00, 14:45 and 16:15**: pull, run the pipeline, read the score together, adjust the plan below.

## If you fall behind (cut in this order)

1. A language model fallback for oddly worded notes: skip it.
2. Search-result dobs: skip; those hits stay `REVIEW`.
3. Unlinked alerts (146 of 440): answer `REVIEW` for them.
4. Multi-person ambiguity: if more than one person fits, answer `REVIEW` with `AMBIGUOUS_CUSTOMER_RECORD`.

Never cut: 0 unsafe clearances, a valid output file, `system/README.md`.

## Git rules

- `git pull --rebase` before you start anything and before every push. Push small commits often.
- Stay in your own files. In `brain/status.md`, edit only your own rows.
- Never push a change that breaks `system/run` or adds an unsafe clearance.
