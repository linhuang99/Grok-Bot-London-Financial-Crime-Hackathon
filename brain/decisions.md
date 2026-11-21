# Decisions

Newest first. One line for the choice, one for why.

**21 Nov: Lane A fixed two hit-side bugs in `hitfacts.py`, agreed with linhuang: every country field is read as a place, and a text with exactly one age and one date gives two birth years (`common.ages_at_dates`).**
`nationality` and `countries` hold places like "Belgrade, Serbia" (34 hits were flagged unrecognised, blocking location clears and search births). Profiles and search results state age in many wordings ("a 30-year-old", "he was 46.", "Fiorani, 52,"). Two dates or two ages are ambiguous and give nothing; numbers such as "Vol. 74, No. 11" or "was 4,600" are not ages (found by auditing every new birth year on dev, not just the labels).

**21 Nov: KYC notes are read by pieces, not sentences: earliest date = date of birth, latest = check date, the one run of capitalised words that is not a country = the name. Every country a non-KYC note mentions counts as lived in.**
22,575 KYC notes come in about 20,000 wordings and the unseen set words them differently again; the pieces rule reads all of them (38 have placeholder names, correctly unread). A residence-word filter would drop 113 real residence countries, and a dropped country can invent a location mismatch.

**21 Nov: Integrate main into laneB and bridge the existing customer contract instead of overwriting it.**
User authorised conflict repair on laneB. Preserve Lane A shared helpers and producer code; share search normalisation while retaining duplicate-source conflict checks. A separate Lane B adapter adds conservative V1 quality with explicit upstream-coverage attestation. Unreadable scripts block name clears until transliteration is available.

**21 Nov: Keep V1 quality additive and fail closed.**
Missing, partial and unparsed fields do not support full-set contradictions. Legacy Person metadata is not automatically complete, and the comparison layer still decides according to the SOP.


**21 Nov: Customer facts live in `system/customer.py`, not `profile.py`.**
Python's standard library has a `profile` module; ours would hide it (and break `cProfile`) depending on import order.

**21 Nov: Every approved check's document country counts, not only the latest one's.**
More countries can only remove location mismatches, so a wrong call costs at most a REVIEW. In dev the document country is always already one of the record's countries.

**21 Nov: The decision compares the customer's `legal_name` and clears on name only when `verified_name` exists.**
The verified name outranks the record and screened names (principle 4); 38 dev customers have a record name that the verified name overrules entirely.

**21 Nov: A link that leads to no customer is treated as no link (searched by screened details in A6); a joint account where no holder fits gives nobody (REVIEW).**
The policy's "without a link, find the records that fit" covers a dead link. A joint account where nobody fits is not covered; nobody found costs at most a REVIEW. Neither case occurs in dev.

**21 Nov: A single linked record is the customer, even if the screened details differ; the screened details only choose between several linked records.**
Principle 2 uses the screened details to pick between the people a link leads to. In dev every single-record link fits anyway (236 of 236).

**21 Nov: `common.py` has one owner, Lane A; Lane B no longer edits it.**
Both lanes wrote date and country helpers in parallel and collided. Lane B's version was merged first and its modules depend on it, so it stays; Lane A owns it from now on and only adds to it, keeping every function Lane B uses (and `tests/test_lane_b.py`) unchanged. Lane B asks for changes in `brain/status.md`.

**21 Nov: Lanes: garyyehhh owns Lane A (customer side: `common.py`, `data.py`, `link.py`, `notes.py`, `customer.py`), linhuang owns Lane B (hit side: `names.py`, `hitfacts.py`).**

**21 Nov: An unrecognised or ambiguous country value never supports a location clear.**
A wrong guess ("Korea" as South Korea, "NA" as Namibia) can invent a location mismatch and clear a real match, costing 60; leaving it unknown only costs a `REVIEW`.

**21 Nov: Missing hit type stays unknown; output ordering and English month parsing are explicit.**
Avoid unsupported assumptions and environment-dependent extraction. Add standard-library-only regression guardrails; keep final identity decisions pending shared pipeline integration.

**21 Nov: The official data room replaces the version rebuilt from the browse workbook.**
The content was the same, but the shapes differ (nested alert `customer`, extra hit name fields, joint accounts), and the unseen set uses the official shapes.

**21 Nov: The organisers' `validate.py` is our only checker.**
It scores exactly as they do; a second scorer would drift.

**21 Nov: Rules decide, a language model is at most a fallback for extracting facts.**
The policy is precise enough to code; rules are deterministic (10% of the score is reproducibility) and explainable to the judges. The unseen set has differently worded free text, which is where a model may help.

**21 Nov: Track 2 over Track 1.**
We are a pair. Track 2 has 50 labelled hits to measure against and a near-algorithmic policy; Track 1 has no labels and needs heavy LLM judgement under a tight budget.

## Lane B first implementation

Use deterministic policy code first; no LLM fallback in this change. Bundle country code/name data so the submitted program does not depend on host locale files or installed packages. Preserve fact provenance and all possible birth years instead of collapsing uncertainty. Leave shared runner/decision integration to the next coordinated change, so Lane A work is not overwritten.
