# Status

Update this when you claim or finish a task, or when the score changes.

## Score (practice labels, `validate.py --score`)

| When | Decision score | Unsafe clearances | Notes |
|---|---|---|---|
| 21 Nov, 12:00 | 0.0 | 0 | Placeholder: `REVIEW` for every hit |

## Tasks

Plan and times: `brain/roadmap.md`. Edit only your own rows.

| Task | Owner | State |
|---|---|---|
| Repo scaffold, `brain/`, agent instructions, roadmap | garyyehhh | done |
| `common.py` (dates, countries) and stubs wired into `system/run` | linhuang | next, by 12:50 |
| `names.py` (principle 8, with tests) | linhuang | by 14:00 |
| `hitfacts.py` (names, dobs, countries, reports, death) | linhuang | by 14:00 |
| `decide.py` with reasons and evidence | linhuang | by 14:45 |
| `data.py` (load and index every file) | linhuang99 | next, by 12:50 |
| `link.py` (linked alerts, joint accounts, verified facts) | linhuang99 | by 14:00 |
| `link.py` (unlinked alerts, merging people) | linhuang99 | by 14:45 |
| `system/README.md` | linhuang | 16:15-16:40 |
| Reason quality pass | linhuang99 | 16:15-16:40 |
| Final run, public repo, submission, video | both | 16:40-17:00 |

## Open questions

- OpenRouter key: needed only if we add a model fallback. Who buys one?
- Do the event's Grok credits work through OpenRouter (bring your own key)? Ask on Discord.

## Lane B local implementation (21 November 2026)

- User explicitly assigned Lane B to **linhuang**. Lane A ownership in the table is unchanged; confirm its active owner with the teammate before joint integration.
- `common.py`, `names.py`, `hitfacts.py` and bundled country names are implemented; synthetic unit tests are in `tests/test_lane_b.py`.
- Agreed public interfaces are unchanged. Company-name matching and the customer-name sufficiency gate are separate helpers; consumers must apply them where required by policy.
- Lane A files, `decide.py`, `system/run`, and tracked `output/dev.jsonl` were not changed. Integration and decision logic remain pending; this is not a scored end-to-end implementation.
- Official data and validator were copied locally from the user's data room into ignored paths, not staged or committed.
- Command-line HTTPS credentials are unavailable. GitHub Desktop fetched origin; laneB was checked to have no incoming/outgoing commits before this change. The Lane B modules remain separate from Lane A and the placeholder runner.

## Lane B branch checks

- 24 synthetic unit tests passed. The current runner is still all REVIEW: 819 lines, 0 format problems, decision score 0.0, 0 unsafe clearances. Lane B extraction is not yet connected to the shared decision pipeline.
