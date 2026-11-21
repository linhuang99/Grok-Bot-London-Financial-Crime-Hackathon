# Same Person or Not? A watchlist screening resolver

For every watchlist hit, the system decides `DIFFERENT_ENTITY`, `SAME_ENTITY` or `REVIEW`, following the bank's identity SOP (`POLICY.md`). It clears a hit only on a contradiction backed by complete facts on both sides, confirms only on agreement, and sends everything else to a person. A wrong clearance lets a listed person stay a customer, so anything the system cannot read becomes `REVIEW`, never a guess.

```sh
system/run <data folder> <output file>
```

Python 3 standard library only. **No language model, no network calls, no cost.** A run over the 819 development hits takes about 3 seconds.

## Architecture

```
                         alerts.jsonl
                              │
        ┌─────────────────────┴──────────────────────┐
        ▼                                            ▼
 WHO IS THE CUSTOMER?                       WHO IS THE LISTED PERSON?
 link.py      follow account / login /      hitfacts.py  names and aliases,
              email links; pick the                      birth dates from dobs,
              joint holder that fits;                    profile notes and search
              search when there is no link;              results (same role, same
              merge records of one person                country only); countries;
 customer.py  latest APPROVED identity                   earliest dated report;
              check (table or KYC note);                 date of death
              names, date of birth, countries
 notes.py     KYC notes and "lived in" notes
        │                                            │
        └─────────────────────┬──────────────────────┘
                              ▼
                     decide.py  (POLICY.md rules)
       clear only on a contradiction whose facts are complete on both sides
       confirm only on agreement            otherwise REVIEW
                              │
                              ▼
            one line per hit: decision, reason code, customer
            record, a reason naming the facts, the evidence IDs
```

| Module | Job |
|---|---|
| `run` | Entry point. Loads the folder once, decides every hit. A failure on one alert or hit is printed and answered `REVIEW`, so one bad record never loses the output file. |
| `data.py` | Reads every file and builds the lookup indexes. Only `alerts.jsonl` and `hits.jsonl` are required; a missing file or a damaged line gives a warning, not a crash. Never reads `practice_labels.jsonl`. |
| `link.py` | Finds the customer (principle 2) and merges their records (principle 3). |
| `customer.py`, `notes.py` | The customer's verified identity and every country tied to them (principles 4 and 6). |
| `hitfacts.py`, `names.py` | The listed person's facts (principle 5) and name agreement (principle 8). |
| `common.py`, `quality.py` | Shared date, country and age helpers; the completeness gate both sides must pass before a clear. |
| `decide.py` | The decision, the reason code, the reason text and the evidence. |

## How we find the customer

1. **Follow the link** the alert carries: account (one row per holder for joint accounts), login, or email. A single linked record is the customer.
2. **Several linked records** (a joint account): keep those that fit what was screened, meaning the name agrees, the date of birth agrees in every part both give, the country is the residence or nationality, and the city is in the city or address. A missing or unreadable screened detail never rules a record out.
3. **No link:** search every record whose name agrees and whose other details fit. **A link that leads to no customer finds nobody**: a namesake found by searching is not the customer the alert was raised on.
4. **One person, one picture:** records sharing a phone and the same full date of birth, or a document number on approved checks, are merged, transitively. A shared phone alone is not enough (family members).
5. **Verified beats declared:** the most recent approved identity check, from the KYC table or a KYC note, gives the legal name and date of birth. Rejected and expired checks are not evidence. A KYC note counts as a check only if it states a name or a date of birth.
6. **Countries:** residence and nationality of every record, the country of every approved document, and every country any note says the customer lived in. More countries can only prevent a location clear, never cause one.

## How we find the listed person

- **Names:** name, aliases, first/middle/last combinations, best matching name.
- **Birth dates,** in policy order: the `dobs` field, then the first paragraph of the profile notes, then web search results. A search result counts only if it describes the same kind of listing in a country tied to the hit.
- **Ages at a date** ("a 30-year-old", "he was 46.", "Raković, 29, a politically exposed person") give two possible birth years. They count only if the text has exactly one age and one date, and **only if the age belongs to the listed person**: "a 25-year-old witness" or "his daughter was born in 2001" are someone else's, so they are dropped.
- **Countries:** `countries`, `nationality`, `citizenship`, the last part of each address and the place of birth, each read as a place ("Belgrade, Serbia" gives Serbia). "International" and "Europe" are not countries. Territories are their own country.
- **Earliest dated report** (exact "According to ...; Month D, YYYY:" lines) and **date of death**.

## How evidence is represented

Every fact carries the ID of the record that proves it: `{"value": ..., "source": "KYC-..."}`. A decision cites only the facts it used: the customer record, the approved check or note behind their date of birth or name, the records behind their countries, and any search result behind the hit's birth date. The reason states the hit's own facts in two to four sentences.

## How results stay the same every run

No randomness, no clock (only the alert's `screened_at`), no model, no network. Every list is kept in file order or sorted; ties are broken by ID. Two runs, runs from another working directory, and runs with a different `PYTHONHASHSEED` produce byte-identical output.

## Safety: clear only on complete facts

Every clearing rule first checks that the fields it relies on are complete on both sides (`common.field_is_complete`). A field is incomplete when any value in it could not be read (an unknown country, a name in a script we cannot compare, an unparseable date) or when Lane A cannot vouch for it (for example an approved check whose name could not be read). Incomplete means no clear from that field, so it ends in `REVIEW` unless another, complete fact decides.

## Three worked cases (development set)

**A clear mismatch: `H-622EDD`, `DIFFERENT_ENTITY` / `DOB_MISMATCH`.** The alert's login handle links to customer `CUS-270502`. Their latest approved identity check is a KYC note, `NOTE-CA9BBC`, giving a date of birth of 1979-04-17. The hit has no `dobs` and no age in its profile, so the system reads its search results: `SR-A88751` says a politically exposed person in Serbia of that name was 29 in May 2002, so born in 1972 or 1973 (the same role and a country tied to the hit, so it is about the hit). 1979 is more than a year from both, so every birth date the hit gives is contradicted. Evidence: `CUS-270502`, `NOTE-CA9BBC`, `SR-A88751`.

**A match: `H-582410`, `SAME_ENTITY` / `NAME_DOB_LOCATION_MATCH`.** The alert's account is joint; the screened name and date of birth pick holder `CUS-377745`. Their verified identity, KYC note `NOTE-14E25A`, gives Elvira Velasco Morillo, born 1968-03-05. The hit's profile says "November 1998 saw Elvira Velasco Morillo, a 30-year-old, face charges", so born in 1967 or 1968. The names agree, the dates of birth agree, both are linked to Spain, and nothing contradicts them. Evidence: `CUS-377745`, `NOTE-14E25A`.

**Left for review: `H-00E181`, `REVIEW` / `INSUFFICIENT_DATA`.** Customer `CUS-217055`'s name agrees with the hit "Sadiq, Abdullahi Abubakar", but the hit gives no date of birth anywhere (no `dobs`, no age in its profile, no search result about the same listing). Nothing contradicts the hit and there is not enough agreement to confirm it, so a person decides.

## Testing

- **262 unit tests** (`python3 -m unittest discover tests`), on invented records, covering every rule at its edges: birth years one versus two apart, exactly 16 at the earliest report, deceased before versus on the screening day, every clear blocked when its facts are incomplete, ages and birth dates that belong to someone else. Each key safety rule was checked by breaking it on purpose and confirming the tests fail.
- **190 labelled test hits, 0 unsafe clearances:** the 50 development practice labels, four synthetic groups (52 hits, `evaluation/`), and two adversarial sets (88 hits, `adversarial/`, `adversarial_v2/`) built by a separate agent from `POLICY.md` alone, without reading this code, to target the failure modes a wrong clearance would come from. All score 100 with the official `validate.py`.

## Known limits

- Hand-built test sets are cleaner than real data. The unseen set will contain wording none of our tests contain; when the system cannot read something, it answers `REVIEW`, which costs points but never risks a wrong clearance.
- Age and date wording is read from a set of common forms ("aged N", "a N-year-old", "N, Name", "he was N."); a new form is missed, giving `REVIEW`.
- Names in Arabic or Cyrillic script are compared only exactly; there is no transliteration, so they never support a name-based clear.
- Dates must be in the formats seen in the data (ISO, day/month/year, "4 May 1990", "May 4, 1990"); other formats are treated as unknown.
- `system/LANE_B_README.md` documents the hit-side quality contract in more detail.
