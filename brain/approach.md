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
3. **Customer facts** (`system/profile.py`, free text read by `system/notes.py`, lane A): legal name, dob and document country from the latest approved check (KYC table or a KYC note); all countries from every record, the document and notes.
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

`system/common.py` (lane B, done)

```python
fold(text) -> str                         # casefold, accents removed
parse_date(text) -> PartialDate | None    # one whole date string; None if invalid. Never invents missing parts
country_name(text) -> str | None          # code / name / nationality -> canonical name; None for regions AND unknown values
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

`system/link.py` (lane A)

```python
resolve(alert, data) -> list[Person]   # [] = not found, 1 = resolved, >1 = several people fit
Person = {
    "record_ids": ["CUS-..."],            # all records of this person
    "record_id": "CUS-...",               # the one to output
    "entity_type": "Individual" | "Company",
    "verified_name": Fact | None,         # latest approved check
    "names": [Fact],                      # verified first, then record, preferred and login names
    "dob": Fact | None,                   # value is a PartialDate; verified beats declared
    "countries": [Fact],                  # residence, nationality, document country, places in notes
}
```

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
