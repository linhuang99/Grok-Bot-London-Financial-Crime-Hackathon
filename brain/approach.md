# Approach

Rules in code do the deciding; `dev/POLICY.md` is close to an algorithm. A language model is at most a fallback for reading free text worded in ways our patterns miss, and it only extracts facts.

## Pipeline (per alert, then per hit)

```
alert ─> 1. resolve customer ─> 2. merge into people ─> 3. customer facts ─┐
                                                                           ├─> 5. compare ─> 6. decide ─> 7. explain ─> output line
hit ───> 4. hit facts ─────────────────────────────────────────────────────┘
```

1. **Resolve customer** (`system/link.py`): follow `account_ref`, `login_handle` or `email`. Joint accounts and unlinked alerts give candidates; keep those that fit the screened name, dob (every part both give), country and city.
2. **Merge into people** (`system/link.py`): same phone + same full dob, or same document number on approved checks, transitively. Several people left: decide the hit for each; same answer for all, give it; otherwise `REVIEW` + `AMBIGUOUS_CUSTOMER_RECORD`. Either way `customer_record_id = "AMBIGUOUS"`.
3. **Customer facts** (`system/link.py`): legal name, dob and document country from the latest approved check (KYC table or a KYC note); all countries from every record, the document and notes.
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

`system/common.py` (lane B)

```python
parse_date(text) -> PartialDate | None    # every format in brain/data-model.md; None if unparseable
country_name(text) -> str | None          # "GB" or "United Kingdom" -> "United Kingdom"; None for "International", "Europe"
```

`system/data.py` (lane A)

```python
load(data_dir) -> Data   # dict with the raw tables plus indexes:
# customers_by_id, customers_by_email, accounts_by_id (list: joint accounts), accounts_by_login (list),
# applicant_by_account_customer, kyc_by_applicant (list), notes_by_email (list),
# search_by_query (list), hits_by_id, name_variants
```

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
