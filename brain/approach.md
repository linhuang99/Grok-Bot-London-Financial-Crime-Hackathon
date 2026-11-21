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

## Module ownership

See `brain/status.md` for who holds what right now.
