# The data

Counts are from the dev set, checked on 21 Nov. The unseen set has the same files and fields.

## Files and links

```
alerts ──hit_ids──────────────> hits ──name──> search_results.query
  │                                            (lowercase name words, alphabetical)
  ├─account_ref──> accounts.account_id ──customer_id──> customers.record_id
  ├─login_handle─> accounts.login_handle ─customer_id─> customers.record_id
  ├─email────────> customers.email
  └─(no link)───> search customers by the screened name, dob, country, city

accounts.(account_id, customer_id) ──> onboarding ──kyc_applicant_id──> kyc_checks.applicant_id
customers.email ──> notes.requester_email
```

| File | Rows | Key |
|---|---|---|
| `alerts.jsonl` | 440 | `alert_id` |
| `hits.jsonl` | 819 | `hit_id` |
| `customers.jsonl` | 72,265 | `record_id` |
| `accounts.jsonl` | 86,659 | `account_id` + `customer_id` |
| `onboarding.jsonl` | 72,265 | `account_id` + `customer_id`, gives `kyc_applicant_id` |
| `kyc_checks.jsonl` | 54,488 | `check_id`, joined on `applicant_id` |
| `notes.jsonl` | 31,895 | `note_id`, joined on `requester_email` |
| `search_results.jsonl` | 16,882 | `result_id`, joined on `query` |
| `practice_labels.jsonl` | 50 | `hit_id`, with `path` (list of steps to the answer) |

## Alerts

- The screened customer is nested: `customer.{name, entity_type, dob, country, city}`. Any of these can be `null`.
- Links: 170 alerts have only `account_ref`, 70 only `login_handle`, 54 only `email`, and **146 have no link at all** (search by the screened details).
- Screened `dob` is often missing (188) or a year only (34); a few are `YYYY-MM` or written out.
- Hits per alert: 344 alerts have 1 hit; some have up to 15.

## Customers (system of record)

- `dob` comes in many formats: ISO `YYYY-MM-DD` (most), `DD/MM/YYYY`, `12 March 1990`, `March 12, 1990`, `12 Mar 1990`, `Mar 12, 1990`. Slash dates are always day first (the first number exceeds 12 in 9,909 of 17,203; the second never does). `common.parse_date` reads every date value in the dev files (checked).
- `nationality` is a full country name or a nationality word (`British`, `Dutch`, `American`); `common.country_name` maps every value in the dev files (checked). `residence_country` is a 2-letter code (`GB`, `US`, `NG`...) on about 21,600 records and a full name on the rest. Normalise both to one form.
- One person can have several records (an old account, for example). Same phone + same full dob, or the same document number on approved KYC checks, means the same person. A shared phone or address alone does not (family members).
- `status`: active, closed or dormant. A closed record still describes the person.

## Loading (checked during A2)

- Dev has no duplicate IDs, broken links, case or spacing differences, damaged lines or byte-order marks. `data.load` still defends against all of them, with warnings, because the unseen set is new data.
- **The unseen folder has no `practice_labels.jsonl`**, and probably no `POLICY.md`: the system must never read either.
- 14,394 account rows have no onboarding row, and 22,691 onboarding applicants have no KYC check: missing links are normal, not errors.
- The phone on an account always equals the customer's phone, so `customers.phone` is the one source.
- Every company customer has a `dob`: it is the incorporation date. 30 individuals have no `dob`.

## Links (checked during A3)

- 294 alerts carry a link (170 account, 70 login, 54 email), never more than one kind per alert; every link leads to a customer.
- 236 links lead to one record, and that record always fits the screened details. 58 alerts link to a joint account; in every one exactly one holder fits.
- Practice labels cite `CUS`, `KYC`, `NOTE` and `SR` IDs as evidence, never account or applicant IDs.

## Accounts and KYC

- **52 accounts have two holders** (joint accounts), one row per holder. Never assume one customer per account; pick the holder that fits the screened details.
- `kyc_checks.result`: approved, rejected or expired. Only approved checks are evidence; the most recent approved one wins for legal name, dob and document country.
- `verified_dob` uses the same mix of formats as customer dobs.

## Customer identity (checked during A4)

- Every customer has exactly one KYC applicant; 22,691 individuals have no check at all (use declared facts).
- Each customer has 0, 1 (approved) or 2 checks (one approved, one rejected or expired). **1,684 customers have a newer rejected or expired check than their approved one**: always take the latest *approved* check.
- The latest approved check's verified name differs from the record's full name for 10,424 customers; 10,386 of those only add a middle name or fix a typo, but **38 are a different first name altogether** (the record name is wrong).
- The verified date of birth differs from the record's for 21 customers. Verified dates of birth are never missing.
- Company customers have a "registry extract" check: verified company name, incorporation date and country, no document number.

## Notes (checked during A5)

- **A KYC note is the only verified identity for 22,575 customers**; none of them also has an approved table check. Every KYC note records a successful check.
- Read by `notes.kyc_check`: the date of birth agrees with the record for all but 18 (verified dates that overrule the record); 38 names hold placeholders ("N/A", "0000") and stay unread.
- 3,067 non-KYC notes mention a country, essentially all "lived and worked in X", in very varied wording.


- `channel`: kyc (22,575), phone, app, email. KYC-channel notes can record an identity verification done outside the KYC provider table (name, dob, document country), which counts like an approved check.
- Other notes can mention where the customer used to live, which adds countries tied to them.

## Hits

- Names: `name`, plus `first_name`, `middle_name`, `last_name`, `best_matching_name`, and `aliases` (list).
- `dobs` is a list of `YYYY`, `YYYY-MM-DD` or `YYYY-MM` strings. **667 of 819 hits have no `dobs`**: look in the first paragraph of `profile_notes` (age at a date gives two possible years), then in search results.
- Countries tied to a hit: `countries`, `nationality`, `citizenship` (lists), the last part of each entry in `addresses`, and `place_of_birth`. Ignore "International" and "Europe". Address parts carry tags such as `Spain [Business]`; some `countries` entries and `place_of_birth` are full places (`City, Region, Country`), and `place_of_birth` can hold several places separated by `;`. Territories (Puerto Rico, Jersey, Macao, Northern Mariana Islands) are their own country. `common.country_at_end` handles tags and place prefixes; every hit country value in the dev files is recognised apart from the regions "International" and "Europe".
- `primary_category` is missing on 345 hits; fall back to the first of `categories`. Values: PEP, Enforcement, Adverse Media, Sanctions, Registration, SOE, Other Segment.
- `life_status` is Alive, Deceased (6 hits) or missing; `deceased_date` gives the date.
- `details` is an object (for example `{"pep": "..."}`), `identifiers` and `relationships` are lists.
- 273 hits have dated reports in `profile_notes` of the form `According to ...; Month D, YYYY: ...`. Only this form counts as a dated report.
- 117 hits are companies; for companies only `dobs` is an incorporation date.

## Search results

- `query` is the name's lowercase words in alphabetical order, accents removed, **one-letter initials dropped** ("Mitchell, Charlee D." -> `charlee mitchell`) and letters such as `ł` dropped ("Paweł" -> `pawe`). Apostrophes split words ("O'Connor" -> `connor`). Company hits never have search results. Use `data.find_search_results`. Most results are about namesakes: a result is about the hit only if it describes the same kind of listing in a country tied to the hit (see `dev/POLICY.md` principle 5 for the phrases).

## Practice labels

28 `DIFFERENT_ENTITY`, 12 `SAME_ENTITY`, 10 `REVIEW`. The most common reason is `LOCATION_MISMATCH` (15+). `reason_codes` lists every accepted code; `customer_record_ids` lists every accepted record (`AMBIGUOUS` in 2 labels); `path` shows the route through the files.

## Checked during Lane B implementation

- Country strings may have trailing bracketed role labels such as `[Associated]` or `[PEP]`; strip the label before exact country normalisation. Address countries are taken from the final comma/semicolon-delimited component. Territories remain distinct.
- Some profile report dates do not use the exact English `According to ...; Month D, YYYY:` line specified by the policy. These are intentionally excluded from earliest-report extraction.
- Birth-date source precedence: structured `dobs`, then the first profile paragraph, then supplied search results. Company incorporation dates use only `dobs`.

- Defensive missing-value behaviour is tested on synthetic input: a missing entity type remains unknown. This is not a claim that official dev hits are missing type.

## Checked V1 quality audit

All 819 dev hits extracted without exceptions, repeated outputs identical, and fact/issue source references resolve to supplied hit/search records. Country quality: 698 PARSED, 23 PARTIAL, 11 UNPARSED, 87 MISSING. Birth quality: 176 PARSED, 2 UNPARSED, 641 MISSING. These are parser states, not accuracy labels or evidence of correct identity decisions. No participant values were copied into docs or tests.

## Cross-lane contract clarification

The Lane A loader indexes search queries through `data.search_keys`; Lane B uses that same normalisation and retains conflicting raw source rows. Person has a singular `dob` Fact and `unreadable_countries`; the Lane B bridge preserves those and adds the V1 `births`/quality view without changing producer code. Coverage completeness is a caller attestation, not inferred from parse success.
