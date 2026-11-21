# Status

Update this when you claim or finish a task, or when the score changes.

## Score (practice labels, `validate.py --score`)

| When | Decision score | Unsafe clearances | Notes |
|---|---|---|---|
| 21 Nov, latest Hard rules check | 0.0 | 0 | 819 lines, 0 format problems; runner still all REVIEW; 67 tests pass |

## Tasks

Plan and times: `brain/roadmap.md`. Edit only your own rows.

| Task | Owner | State |
|---|---|---|
| Repo scaffold, `brain/`, agent instructions, roadmap | garyyehhh | done |
| `common.py` (dates, countries) and stubs wired into `system/run` | linhuang | Helpers and V1 parsing gates tested; shared runner wiring pending |
| `names.py` (principle 8, with tests) | linhuang | V1 quality implementation and comprehensive tests complete; consumer integration pending |
| `hitfacts.py` (names, dobs, countries, reports, death) | linhuang | V1 quality implementation and comprehensive tests complete; consumer integration pending |
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

After the V1 batched system edit, immediately ran:

```sh
system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
python3 -m unittest discover tests
```

Results: **819 lines, 0 format problems, 0 unsafe clearances, decision score 0.0; 67 tests passed** (rewritten functional/quality tests plus retained Hard rules checks). All 819 hit extractions were also checked for deterministic repeat output and valid fact/issue source IDs. No model calls or paid API usage.

V1 contract README: [system/LANE_B_README.md](../system/LANE_B_README.md). `quality` and `issues` are implemented in Lane B; Lane A and the final decision pipeline still need to consume them. The unchanged all-REVIEW runner's score 0.0 must not be presented as an integrated result.

Earlier intermediate edits did not each run the full gate; that historical deviation remains recorded. This revision ran the complete gate immediately after its batched system edit. Future system edits require the same three-command gate.

## Sync

Command-line GitHub HTTPS authentication is unavailable. GitHub Desktop fetched origin before this edit; local laneB matched origin/laneB. Do not force push or overwrite a teammate's work.
