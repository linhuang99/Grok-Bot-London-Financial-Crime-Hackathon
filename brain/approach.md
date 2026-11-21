# Approach

Rules in code do the deciding; `dev/POLICY.md` is close to an algorithm. A language model is at most a fallback for reading free text worded in ways our patterns miss, and it only extracts facts.

## Pipeline (per alert, then per hit)

```
alert ─> 1. resolve customer ─> 2. merge into people ─> 3. customer facts ─┐
                                                                           ├─> 5. compare ─> 6. decide ─> 7. explain ─> output line
hit ───> 4. hit facts ─────────────────────────────────────────────────────┘
```

1. **Resolve customer** (`system/link.py`, lane A): follow `account_ref`, `login_handle` or `email`. Joint accounts and unlinked alerts give candidates; keep those that fit the screened name, dob (every part both give), country and city.
2. **Merge into people** (`system/link.py`, lane A): same phone + same full dob, or same document number on approved checks, transitively. Several people left: decide the hit for each; same answer for all, give it; otherwise `REVIEW` + `AMBIGUOUS_CUSTOMER_RECORD`. Either way `customer_record_id = "AMBIGUOUS"`.
3. **Customer facts** (`system/customer.py`, free text read by `system/notes.py`, lane A): legal name, dob and document country from the latest approved check (KYC table or a KYC note); all countries from every record, the document and notes.
4. **Hit facts** (`system/hitfacts.py`): names and aliases; possible birth years and dates from `dobs`, profile notes, then filtered search results; countries; earliest dated report; date of death.
5. **Compare** (`system/names.py` for names): name agreement per principle 8 of the policy, dob agreement or contradiction, country overlap, entity type.
6. **Decide** (`system/decide.py`): contradictions first (time, dob, location, name, type, deceased) give `DIFFERENT_ENTITY`; then agreement (person: name + dob; company: name + country) gives `SAME_ENTITY`; otherwise `REVIEW`. A country difference never clears a hit whose name and dob agree.
7. **Explain**: reason code, 2-4 sentences with this hit's facts, and only the IDs that decided it.

## Interfaces

Agreed contracts between the lanes, so each side can build and test against them before the other side is done. Change one only after telling the other person, and update it here in the same commit.

Every fact carries the ID that proves it, so evidence falls out of the facts used:

```python
Fact = {"value": ..., "source": "KYC-00030A"}   # hit fields cite "H-XXXXXX#field", e.g. "H-2C4CE7#dobs"
PartialDate = (year, month_or_None, day_or_None)
```

`system/common.py` (lane A owns it; Lane B's functions keep their behaviour)

```python
fold(text) -> str                         # casefold, accents removed
parse_date(text) -> PartialDate | None    # one whole date string; None if invalid or the year is outside 1800-2100
dates_agree(a, b) -> bool                 # equal in every part both give: (1990, None, None) agrees with (1990, 5, 4)
country_name(text) -> str | None          # code / name / nationality -> canonical name; None for regions, placeholders ("NA") AND unknown values
country_at_end(text) -> str | None        # country at the end of an address or place ("Belgrade, Serbia")
countries_in_text(text) -> set            # full country names and nationalities found in prose
search_query(name) -> str                 # key for search_results.query (see the proposed fix in brain/status.md)
```

**Never rule out a match on location using an unrecognised country**: dropping it can invent a mismatch and clear a real match. `country_name` returns `None` for both regions and unknown values today; see the proposed fix in `brain/status.md`.

`system/data.py` (lane A, done)

```python
load(data_dir) -> dict   # raises DataError only if alerts.jsonl or hits.jsonl is missing
# Tables by file name: alerts (file order), hits, customers, accounts, onboarding, kyc_checks, notes, search_results
# Indexes (lists where one key can match several rows, in file order):
#   hits_by_id, customers_by_id                      id -> row
#   customers_by_email, notes_by_email               email -> [rows]          (case-insensitive)
#   accounts_by_id                                   account -> [rows]        (joint accounts: one row per holder)
#   accounts_by_login                                login -> [rows]          (case-insensitive)
#   accounts_by_customer                             customer -> [rows]
#   applicant_by_account_customer                    (account, customer) -> applicant
#   kyc_by_applicant                                 applicant -> [checks]    (not sorted by date: A4 picks the latest)
#   search_by_query                                  normalised query -> [results]
# name_variants = {"groups": [...], "company_legal_forms": [...]}
# warnings = [str]   skipped lines, repeated IDs, missing optional files (also printed to stderr)
id_key(value), text_key(value)       # the lookup keys: trimmed; text_key also lowercase; blank -> None
search_keys(name) -> [str]           # every possible query key: initials dropped, accents removed, sorted words
find_search_results(data, name)      # results under any key of the name: finds all 702 individual hits in dev
```

Look up with `id_key` / `text_key`, never with raw values. Records keep their original values for evidence.

`system/names.py` (lane B)

```python
names_agree(name_a, name_b, variants) -> bool   # dev/POLICY.md principle 8
```

`system/link.py` (lane A, A3 done for linked alerts)

```python
resolve(alert, data) -> list[list[str]]   # people: each a list of customer record IDs; [] = not found
search(alert, data) -> [records]          # A6: no link or a dead link: name must agree; dob, country, city, type must fit
fits_screened(alert, record, data) -> bool  # principle 2 fit: name, dob, country, city; unknown never rules out
```

**How `system/run` uses Lane A** (contract for the runner):

```python
data = data.load(folder)                  # once
people = link.resolve(alert, data)        # per alert
# until A4: customer_record_id = people[0][0] if len(people) == 1 else ("AMBIGUOUS" if people else None)
# from A4:  persons = [customer.person(record_ids, data) for record_ids in people]   -> Person below
```

`customer.person(record_ids, data)` (A4, done) builds:

```python
Person = {
    "record_ids": ["CUS-..."],            # all records of this person
    "record_id": "CUS-...",               # the one to output
    "entity_type": "Individual" | "Company",
    "verified_name": Fact | None,         # latest APPROVED check (rejected/expired never count)
    "legal_name": Fact,                   # verified_name if any, else the record's full name (CUS source)
    "names": [Fact],                      # legal name first, then every record name, no repeats
    "dob": Fact | None,                   # verified if readable, else declared; companies: incorporation date
    "countries": [Fact],                  # residence + nationality of every record, document country of every approved check
    "unreadable_countries": [Fact],       # non-empty values we could not read as a country (incl. "NA")
}
```

**`system/decide.py` (first version, 15:05):** `decide(alert, hit, persons, facts, data) -> output line`. Clears in policy order (type, deceased, temporal, dob, location, name), each only when `field_is_complete` holds on both sides for the fields it uses; then confirms; otherwise REVIEW. Several persons: same decision for all gives it, otherwise `AMBIGUOUS_CUSTOMER_RECORD`. `system/run` answers REVIEW for any alert or hit that raises, so one bad record never loses the output file.

`Person["complete_fields"]` (Lane A) is what `quality.adapt_person` receives: names/births only when verified by a table check or no KYC note exists (A5 widens this), countries only when no note mentions a country and no other record may be the same person (A5, A7 widen this).

**Rules for `decide.py` when using a Person:**
- Compare the hit's names with `legal_name`. Clear on `NAME_MISMATCH_VERIFIED` only when `verified_name` is not `None`.
- **Never clear on `LOCATION_MISMATCH` while `unreadable_countries` is not empty**: an unreadable value might be the matching country.
- A fact's `source` is the evidence ID to cite (`CUS-...` or `KYC-...`), as the practice labels do.

`system/hitfacts.py` (lane B)

```python
hit_facts(hit, data) -> HitFacts
HitFacts = {
    "hit_id": "H-...",
    "entity_type": "Individual" | "Company" | None,  # unknown stays unknown
    "names": [str],                       # name, aliases, first/middle/last combinations
    "births": [Fact],                     # every possible birth date (an age at a date gives two years)
    "countries": [Fact],
    "earliest_report": Fact | None,       # value is a PartialDate
    "death": Fact | None,
    "quality_version": 1,
    "quality": {field: {"status": "MISSING|PARSED|PARTIAL|UNPARSED", "parsed": int, "unparsed": int, "ignored": int}},
    "issues": [{"field": str, "code": str, "source": str, "path": str, "blocking": bool}],
    "name_sources": {name: [source_id]},
    "birth_source": "structured" | "profile" | "search" | None,
}
```

`system/decide.py` (shared)

```python
decide(alert, persons, facts) -> dict   # one output line, the fields in brain/brief.md
```

## Module ownership

See `brain/roadmap.md` for lanes and `brain/status.md` for who holds what right now.

## Lane B implementation notes

The agreed function signatures remain unchanged; the missing-type behaviour of `HitFacts.entity_type` is clarified below. All imports use only Python's standard library. `countries.json` is a bundled code/name table seeded from public-domain tzdata, not participant data.

Additional helpers: `company_names_agree(a,b,variants)` removes corporate legal forms; `usable_individual_name(name)` implements the two-real-parts customer gate. Keep personal and company matching separate. `names_agree` alone is NOT a complete identity decision, and a valid single-part hit alias is not the same as a sufficient customer name.

Unknown country strings return None, and unknown dates remain unknown. Consumers must not interpret missing or unparsed evidence as a contradiction. No model/API calls or practice-label reads occur in Lane B modules. The caller provides `search_by_query`; only matching-name queries with the policy's listing phrase and a tied country may supply fallback birth dates. Age-derived years remain alternatives. Every extracted fact carries its supporting record/field ID.

### Unknown values and determinism

If a hit lacks entity type, return `None` rather than defaulting to `Individual`. Downstream comparison must not treat this as a type mismatch or use person-only confirmation rules. Person-only text birth extraction is skipped when type is unknown. Structured dates retain their original evidence.

Names/aliases and evidence facts have stable output ordering. English date parsing uses a fixed English month table, independent of host locale. No model fallback is present. If one is added later it must use only the OpenRouter chat-completions endpoint, `OPENROUTER_API_KEY`, a pinned model and temperature 0, with extraction validation and no model-made identity decisions.

## Lane B quality contract V1

See [LANE_B_README.md](../system/LANE_B_README.md) for the complete teammate-facing contract. Function signatures and original Fact fields remain unchanged; extra metadata is additive but consumers MUST adopt it before relying on full-set contradictions. This is a producer-side interface update, not a claim that Lane A or the shared decision module is integrated.

`MISSING` means no eligible input, `PARSED` means all supplied eligible candidates handled, `PARTIAL` means successes plus failures, and `UNPARSED` means present but unusable/unperformed required investigation. A partial date can be fully PARSED. Policy-excluded regions are ignored; invalid country/date values remain issues with source/path, never silent omission. Duplicate search IDs with differing content produce an unresolved conflict.

`common.field_is_complete(facts, field)` rejects legacy/unknown versions, malformed metadata, missing/partial/unparsed fields and blocking issues. It is a parsing gate, not a decision. Both sides need equivalent completeness handling; unresolved unrelated fields do not globally veto independent sufficient contradictions. Positive confirmation must still exclude possible identity-relevant contradictions. Missing quality on old Person dictionaries must not be silently upgraded to PARSED.

Lane A code, the shared runner and final decision code were not changed. Teammate acceptance of this V1 contract and consumer-side tests remain required before end-to-end integration.

## Cross-lane compatibility on laneB

The user authorised importing main into laneB and resolving conflicts. Shared helpers remain owned by Lane A: keep `dates_agree`, placeholder-country handling and 1800-2100 bounds. Lane B's search extraction now imports `data.search_keys`; raw candidates remain available for duplicate-source conflict checks, and raw query validation uses equivalent normalised keys.

`quality.adapt_person(person, complete_fields=())` is a Lane B bridge, not a replacement for `customer.person`. It copies existing fields, preserves `unreadable_countries`, adds a `births` alias from readable `dob`, and emits V1 diagnostics. It never infers upstream coverage from an empty warning list. Only an explicit producer/caller attestation can mark coverage complete; validation failures still block the gate. Existing versioned metadata is not silently upgraded. See [Lane B README](../system/LANE_B_README.md) for an example.

Unsupported name scripts are preserved with blocking name issues until shared transliteration exists. No final identity decision is inferred from parser quality, and the shared runner/decision integration remains pending.
