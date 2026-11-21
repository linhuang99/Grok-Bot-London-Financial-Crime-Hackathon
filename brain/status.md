# Status

Update this when you claim or finish a task, or when the score changes.

## Score (practice labels, `validate.py --score`)

| When | Decision score | Unsafe clearances | Notes |
|---|---|---|---|
| 21 Nov, latest Hard rules check | 0.0 | 0 | 819 lines, 0 format problems; runner still all REVIEW; 32 unit tests pass |
| 21 Nov, 14:20 (A2) | 0.0 | 0 | 819 lines, 0 problems; runner still all REVIEW; 68 unit tests pass |
| 21 Nov, 14:35 (common.py fixes) | 0.0 | 0 | 79 unit tests pass |
| 21 Nov, 14:15 (A3) | 0.0 | 0 | `link.resolve` finds the accepted customer for 38/38 linked practice labels; not yet called by `run`; 102 unit tests pass |
| 21 Nov, 14:40 (A4) | 0.0 | 0 | `customer.person` picks the exact latest approved check on 30/30 label paths; not yet called by `run`; 126 unit tests pass |
| **21 Nov, 15:05 (first integrated run)** | **39.8** | **0** | 26/50 right; reason code and customer record 100% on right decisions. All 819: 155 clears, 42 confirms, 622 REVIEW. Same output every run, from `system/`, without practice labels |
| 21 Nov, 15:30 (A5 notes) | 50.0 | 0 | 30/50 right; KYC notes are the verified identity of 22,575 customers; 197 unit tests pass |
| 21 Nov, 15:10 (A6 unlinked search) | 70.4 | 0 | 38/50 right; every one of the 440 alerts finds a customer; 206 unit tests pass |
| 21 Nov, 15:15 (A7 merged people) | **81.5** | **0** | 42/50 right. All 819: 420 clears, 92 confirms, 307 REVIEW. 213 unit tests pass |
| 21 Nov, 15:30 (hit-side fixes) | **100.0** | **0** | 50/50 right. All 819: 448 clears, 121 confirms, 250 REVIEW. 225 unit tests pass. A perfect practice score is not proof for the unseen set |

## Tasks

Plan and times: `brain/roadmap.md`. Edit only your own rows.

| Task | Owner | State |
|---|---|---|
| Repo scaffold, `brain/`, agent instructions, roadmap | garyyehhh | done |
| **Lane A** (customer side): checkpoints A2-A7 in `brain/roadmap.md` | garyyehhh | **A1-A7 all done** |
| `common.py` (dates, countries) | garyyehhh (from linhuang) | Done; fixes 2 and 4 below done, 3 and 5 pending |
| `names.py` (principle 8, with tests) | linhuang | V1 extraction and compatibility tests complete; shared decision integration pending |
| `hitfacts.py` (names, dobs, countries, reports, death) | linhuang | V1 extraction and compatibility tests complete; shared decision integration pending |
| `decide.py` with reasons and evidence; `system/run` wired | garyyehhh | First version done (15:05); unit tests next |
| `system/README.md` | linhuang | Pending final architecture and worked cases |
| Reason quality pass | garyyehhh | 16:15-16:40 |
| Final run, public repo, submission, video | both | 16:40-17:00 |

## Proposed fixes to the shared helpers (from Lane A's review)

Checked against every date and country value in `dev/`: dates agree with Lane A's version on all ~180,000 values, and every customer-side country is recognised. These are gaps for the unseen set:

1. **Done in laneB compatibility update (linhuang).** `hitfacts.py` uses Lane A's `data.search_keys` for initials, accents and alternate stored spellings. It reads raw indexed rows to retain conflicting duplicate-ID detection, and validates row queries using the same normalisation. Synthetic cross-module tests cover missed initials, alternate spellings and conflicts.
2. **Done (garyyehhh).** "NA" no longer maps to Namibia: `NA`, `N/A`, `Unknown`, `None`, `TBC` and similar are not countries.
3. **Customer side done in A4 (`Person["unreadable_countries"]`); hit-side V1 `quality/issues` now implemented; final `decide.py` consumption remains pending. Unrecognised and "not a country" both return `None` from the legacy country helper.** A region ("Europe") should be ignored, but an unrecognised country ("Jamaican", "England" are not in the alias list) should block a location clear, because dropping it can invent a mismatch. Fix: a way for `decide.py` to tell them apart, for example a `NOT_COUNTRIES` set or an `unrecognised` flag in the facts.
4. **Done (garyyehhh).** Years outside 1800-2100 now parse as unknown, so a typo year cannot create a false `DOB_MISMATCH`.
5. **Transliteration remains for garyyehhh; Lane B now blocks unreadable-script name clears.** Non-Latin aliases (204 in dev, Arabic and Cyrillic) cannot be compared.** Judges: a different script is not a different name, and transliteration is expected. Cyrillic and Greek can use a fixed letter table; until then an unreadable alias must block a `NAME_MISMATCH_VERIFIED` clear.

## Open questions

- OpenRouter key: needed only if we add a model fallback. Who buys one?
- Do the event's Grok credits work through OpenRouter (bring your own key)? Ask on Discord.

## Lane B implementation (21 November 2026)

- User assigned Lane B to **linhuang**. Lane A is owned by garyyehhh.
- The Lane B modules use only the standard library. No model calls, random choices or wall-clock decisions. No participant IDs/answers are embedded in runtime code.
- Missing hit entity type stays `None`; do not infer a person, perform person-only text birth extraction, or use missing type for an entity-type contradiction. This clarification is documented in `approach.md`.
- Lane A files, `decide.py`, and `system/run` were not changed. The modules are not connected to the placeholder runner, so score 0.0 is the baseline, not evidence of correct identity decisions.
- Official inputs and validator are local ignored files. Predictions are generated only by `system/run`.

## Lane B compatibility integration

- Imported main's A2-A4 changes into **laneB**, not the other way around. `common.py` keeps `dates_agree`, the 1800-2100 protection and country-placeholder handling; Lane B's tuple validation and V1 helpers remain additive. Main ownership of the shared helper file is unchanged.
- `hitfacts.py` shares Lane A search normalisation, preserves source conflicts, and records unreadable non-Latin name scripts as blocking name issues. This does not implement transliteration.
- New Lane B `quality.adapt_person` copies a legacy Person, preserves `unreadable_countries` and maps `dob` to a provenance-preserving `births` alias. No producer code in `customer.py`, `data.py` or `link.py` was edited beyond importing their existing commits.
- Caller coverage is UNKNOWN by default. `complete_fields` may be supplied only after the producer's investigation actually covers that field; an empty unreadable list does not certify complete investigation. Existing versioned quality is never silently upgraded.
- The shared decision module remains unimplemented. The runner still returns all REVIEW; compatibility checks are not an identity accuracy claim.

## Latest checks

After the batched system merge/edit ran all three AGENTS.md commands in order. Final working-tree results: **180 tests passed with no skips, 819 output lines, 0 validator problems, 0 unsafe clearances, practice decision score 0.0**. The all-REVIEW runner is unchanged; these are compatibility results, not a scored decision implementation.

Updated the Lane B README and shared approach to document the adapter, retained helper behaviour, unsupported-script block and caller coverage obligations. Final decision integration remains pending.

## Sync

Command-line HTTPS credentials are unavailable. GitHub Desktop fetched origin; laneB and main matched their remote refs before integration. Merge target: origin/main at e149bae. Never force-push.
