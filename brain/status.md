# Status

Update this when you claim or finish a task, or when the score changes.

## Score (practice labels, `validate.py --score`)

| When | Decision score | Unsafe clearances | Notes |
|---|---|---|---|
| 21 Nov, latest Hard rules check | 0.0 | 0 | 819 lines, 0 format problems; runner still all REVIEW; 32 unit tests pass |

## Tasks

Plan and times: `brain/roadmap.md`. Edit only your own rows.

| Task | Owner | State |
|---|---|---|
| Repo scaffold, `brain/`, agent instructions, roadmap | garyyehhh | done |
| `common.py` (dates, countries) and stubs wired into `system/run` | linhuang | Helpers implemented and tested; shared runner wiring pending |
| `names.py` (principle 8, with tests) | linhuang | First implementation and unit tests complete; integration pending |
| `hitfacts.py` (names, dobs, countries, reports, death) | linhuang | First implementation and unit tests complete; integration pending |
| `decide.py` with reasons and evidence | linhuang | Not implemented; requires coordinated Lane A integration |
| `data.py` (load and index every file) | linhuang99 | next, by 12:50 |
| `link.py` (linked alerts, joint accounts, verified facts) | linhuang99 | by 14:00 |
| `link.py` (unlinked alerts, merging people) | linhuang99 | by 14:45 |
| `system/README.md` | linhuang | Pending final architecture and worked cases |
| Reason quality pass | linhuang99 | 16:15-16:40 |
| Final run, public repo, submission, video | both | 16:40-17:00 |

## Open questions

- OpenRouter key: needed only if we add a model fallback. Who buys one?
- Do the event's Grok credits work through OpenRouter (bring your own key)? Ask on Discord.

## Lane B implementation (21 November 2026)

- User assigned Lane B to **linhuang**. Lane A rows are unchanged; confirm its active owner before joint integration.
- The Lane B modules use only the standard library. No model calls, random choices or wall-clock decisions. No participant IDs/answers are embedded in runtime code.
- Missing hit entity type stays `None`; do not infer a person, perform person-only text birth extraction, or use missing type for an entity-type contradiction. This clarification is documented in `approach.md`.
- Lane A files, `decide.py`, and `system/run` were not changed. The modules are not connected to the placeholder runner, so score 0.0 is the baseline, not evidence of correct identity decisions.
- Official inputs and validator are local ignored files. Predictions are generated only by `system/run`.

## Latest checks

After the system edit, ran the three required commands in order:

```sh
system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
python3 -m unittest discover tests
```

Results: **819 lines, 0 format problems, 0 unsafe clearances, decision score 0.0; 32 unit tests passed**. New tests cover standard-library imports, no current model/network calls, no literal participant IDs/practice-label paths, unknown values, input immutability, ordering and cross-process hash-seed stability. These are guardrails, not a proof of complete policy correctness.

The earlier implementation ran full checks before upload, rather than after every intermediate edit. This is a recorded process deviation; it cannot be retroactively corrected. This revision ran full checks immediately after its batched system edit. Future system edits require the same three-command gate.

## Sync

Command-line GitHub HTTPS authentication is unavailable. GitHub Desktop fetched origin before this edit; local laneB matched origin/laneB. Do not force push or overwrite a teammate's work.
