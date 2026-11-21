# Status

Update this when you claim or finish a task, or when the score changes.

## Score (practice labels, `validate.py --score`)

| When | Decision score | Unsafe clearances | Notes |
|---|---|---|---|
| 21 Nov, latest Hard rules check | 0.0 | 0 | 819 lines, 0 format problems; runner still all REVIEW; 32 unit tests pass |
| 21 Nov, 14:20 (A2) | 0.0 | 0 | 819 lines, 0 problems; runner still all REVIEW; 68 unit tests pass |
| 21 Nov, 14:35 (common.py fixes) | 0.0 | 0 | 79 unit tests pass |

## Tasks

Plan and times: `brain/roadmap.md`. Edit only your own rows.

| Task | Owner | State |
|---|---|---|
| Repo scaffold, `brain/`, agent instructions, roadmap | garyyehhh | done |
| **Lane A** (customer side): checkpoints A2-A7 in `brain/roadmap.md` | garyyehhh | A2 done, A3 next |
| `common.py` (dates, countries) | garyyehhh (from linhuang) | Done; fixes 2 and 4 below done, 3 and 5 pending |
| `names.py` (principle 8, with tests) | linhuang | First implementation and unit tests complete; integration pending |
| `hitfacts.py` (names, dobs, countries, reports, death) | linhuang | First implementation and unit tests complete; integration pending |
| `decide.py` with reasons and evidence | both | Not started; needs Lane A's `Person` (A3-A4) |
| `system/README.md` | linhuang | Pending final architecture and worked cases |
| Reason quality pass | garyyehhh | 16:15-16:40 |
| Final run, public repo, submission, video | both | 16:40-17:00 |

## Proposed fixes to the shared helpers (from Lane A's review)

Checked against every date and country value in `dev/`: dates agree with Lane A's version on all ~180,000 values, and every customer-side country is recognised. These are gaps for the unseen set:

1. **For linhuang (`hitfacts.py`): `search_query` misses search results.** The stored queries drop single-letter initials (`Mitchell, Charlee D.` is stored as `charlee mitchell`) and drop letters such as `ł` (`Paweł` is stored as `pawe`). `search_query` keeps both, so `hitfacts` finds results for only 670 of the 702 individual hits. Fix: in `hitfacts.py`, replace the `index.get(search_query(name), [])` lookup with `data.find_search_results(data, name)`, which finds all 702 (tested in `tests/test_data.py` and `tests/test_dev_coverage.py`).
2. **Done (garyyehhh).** "NA" no longer maps to Namibia: `NA`, `N/A`, `Unknown`, `None`, `TBC` and similar are not countries.
3. **For garyyehhh (`common.py`), before `decide.py` clears on location: unrecognised and "not a country" both return `None`.** A region ("Europe") should be ignored, but an unrecognised country ("Jamaican", "England" are not in the alias list) should block a location clear, because dropping it can invent a mismatch. Fix: a way for `decide.py` to tell them apart, for example a `NOT_COUNTRIES` set or an `unrecognised` flag in the facts.
4. **Done (garyyehhh).** Years outside 1800-2100 now parse as unknown, so a typo year cannot create a false `DOB_MISMATCH`.
5. **For garyyehhh (`common.fold`), later: non-Latin aliases (204 in dev, Arabic and Cyrillic) cannot be compared.** Judges: a different script is not a different name, and transliteration is expected. Cyrillic and Greek can use a fixed letter table; until then an unreadable alias must block a `NAME_MISMATCH_VERIFIED` clear.

## Open questions

- OpenRouter key: needed only if we add a model fallback. Who buys one?
- Do the event's Grok credits work through OpenRouter (bring your own key)? Ask on Discord.

## Lane B implementation (21 November 2026)

- User assigned Lane B to **linhuang**. Lane A is owned by garyyehhh.
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
