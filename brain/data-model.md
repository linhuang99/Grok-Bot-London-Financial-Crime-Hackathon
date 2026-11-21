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

- `dob` comes in many formats: ISO `YYYY-MM-DD` (most), `DD/MM/YYYY`, `12 March 1990`, `March 12, 1990`, `12 Mar 1990`, `Mar 12, 1990`. Parse all of them.
- `nationality` is always a full country name. `residence_country` is a 2-letter code (`GB`, `US`, `NG`...) on about 21,600 records and a full name on the rest. Normalise both to one form.
- One person can have several records (an old account, for example). Same phone + same full dob, or the same document number on approved KYC checks, means the same person. A shared phone or address alone does not (family members).
- `status`: active, closed or dormant. A closed record still describes the person.

## Accounts and KYC

- **52 accounts have two holders** (joint accounts), one row per holder. Never assume one customer per account; pick the holder that fits the screened details.
- `kyc_checks.result`: approved, rejected or expired. Only approved checks are evidence; the most recent approved one wins for legal name, dob and document country.
- `verified_dob` uses the same mix of formats as customer dobs.

## Notes

- `channel`: kyc (22,575), phone, app, email. KYC-channel notes can record an identity verification done outside the KYC provider table (name, dob, document country), which counts like an approved check.
- Other notes can mention where the customer used to live, which adds countries tied to them.

## Hits

- Names: `name`, plus `first_name`, `middle_name`, `last_name`, `best_matching_name`, and `aliases` (list).
- `dobs` is a list of `YYYY`, `YYYY-MM-DD` or `YYYY-MM` strings. **667 of 819 hits have no `dobs`**: look in the first paragraph of `profile_notes` (age at a date gives two possible years), then in search results.
- Countries tied to a hit: `countries`, `nationality`, `citizenship` (lists), the last part of each entry in `addresses`, and `place_of_birth`. Ignore "International" and "Europe".
- `primary_category` is missing on 345 hits; fall back to the first of `categories`. Values: PEP, Enforcement, Adverse Media, Sanctions, Registration, SOE, Other Segment.
- `life_status` is Alive, Deceased (6 hits) or missing; `deceased_date` gives the date.
- `details` is an object (for example `{"pep": "..."}`), `identifiers` and `relationships` are lists.
- 273 hits have dated reports in `profile_notes` of the form `According to ...; Month D, YYYY: ...`. Only this form counts as a dated report.
- 117 hits are companies; for companies only `dobs` is an incorporation date.

## Search results

- `query` is the name's lowercase words in alphabetical order. Most results are about namesakes: a result is about the hit only if it describes the same kind of listing in a country tied to the hit (see `dev/POLICY.md` principle 5 for the phrases).

## Practice labels

28 `DIFFERENT_ENTITY`, 12 `SAME_ENTITY`, 10 `REVIEW`. The most common reason is `LOCATION_MISMATCH` (15+). `reason_codes` lists every accepted code; `customer_record_ids` lists every accepted record (`AMBIGUOUS` in 2 labels); `path` shows the route through the files.

## Checked during Lane B implementation

- Country strings may have trailing bracketed role labels such as `[Associated]` or `[PEP]`; strip the label before exact country normalisation. Address countries are taken from the final comma/semicolon-delimited component. Territories remain distinct.
- Some profile report dates do not use the exact English `According to ...; Month D, YYYY:` line specified by the policy. These are intentionally excluded from earliest-report extraction.
- Birth-date source precedence: structured `dobs`, then the first profile paragraph, then supplied search results. Company incorporation dates use only `dobs`.

- Defensive missing-value behaviour is tested on synthetic input: a missing entity type remains unknown. This is not a claim that official dev hits are missing type.

## Checked V1 quality audit

All 819 dev hits extracted without exceptions, repeated outputs identical, and fact/issue source references resolve to supplied hit/search records. Country quality: 698 PARSED, 23 PARTIAL, 11 UNPARSED, 87 MISSING. Birth quality: 176 PARSED, 2 UNPARSED, 641 MISSING. These are parser states, not accuracy labels or evidence of correct identity decisions. No participant values were copied into docs or tests.
