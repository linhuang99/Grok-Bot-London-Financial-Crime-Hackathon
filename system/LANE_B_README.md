# Lane B: identity facts and parse-quality contract / 身份事实与解析质量约定

**Owner: linhuang. Contract version: 1.**

Lane A resolves the customer; Lane B resolves the watchlist profile. Both pass facts to the shared rule-based decision layer. This document is the handoff contract, not a claim that the full screening system is finished. `system/run` currently remains the all-REVIEW baseline.

中文：已识别的信息照常保留；没有提供的信息、提供了但无法解析的信息必须分开表达。请先接入下面的质量检查，再把这些事实用于身份判断。旧代码如果忽略新增字段，不会自动获得这些保护。

## 1. Files and responsibilities

| File | Responsibility |
|---|---|
| `common.py` | Partial-date parsing, country normalisation, `country_parse_status`, `field_is_complete` |
| `countries.json` | Bundled public code/name vocabulary; territories stay distinct; no participant records |
| `names.py` | Policy rule 8; individual and company helpers; no identity decisions |
| `hitfacts.py` | Names, birthdays/incorporation dates, countries, dated reports, death, provenance and parse-quality metadata |
| `../tests/test_lane_b.py` | Synthetic functional and boundary cases; no development answers |

Dependencies: Python 3 standard library only. No model or network calls. No API key is needed for these modules. Any future model fallback must follow AGENTS.md: OpenRouter only, pinned model, temperature 0, validated extraction only.

```text
Lane A: alert -> linked/merged customer -> Person + source IDs
                                                        \
                                                         shared rules -> official output
                                                        /
Lane B: hit + supplied search index -> facts + quality + issues
```

## 2. Existing interfaces stay callable

```python
parse_date(text)                    # (year, month_or_None, day_or_None) or None
country_name(text)                  # canonical country/territory or None
names_agree(name_a, name_b, variants) # bool: personal name-part agreement
hit_facts(hit, data)                # dictionary below
```

Additional helpers:

```python
company_names_agree(a, b, variants)  # remove policy-listed company legal forms
usable_individual_name(name)        # >= 2 real customer name parts
country_parse_status(value, address=False) # (MISSING/PARSED/IGNORED/UNPARSED, country)
field_is_complete(facts, field)     # V1 parsing gate; NOT an identity verdict
```

`name_variants.json` is passed by the caller. Do not replace its groups with development-specific exceptions. A single-part hit alias may match; this does not remove the policy's customer-name sufficiency gate. Company-only legal forms must not be stripped from personal names.

## 3. HitFacts V1

Original fields are retained:

```python
{
    "hit_id": "...",
    "entity_type": "Individual",  # "Company" or None when unknown
    "names": ["..."],
    "births": [{"value": (1984, None, None), "source": "..."}],
    "countries": [{"value": "United Kingdom", "source": "..."}],
    "earliest_report": None,      # Fact with PartialDate when available
    "death": None,                # Fact with PartialDate when available

    "quality_version": 1,
    "quality": {
        "countries": {"status": "PARTIAL", "parsed": 1, "unparsed": 1, "ignored": 0},
        # also names, births, earliest_report, death, entity_type
    },
    "issues": [{
        "field": "countries",
        "code": "UNRECOGNISED_COUNTRY",
        "source": "...#countries",
        "path": "countries",
        "blocking": True,
    }],
    "name_sources": {"...": ["...#name", "...#aliases"]},
    "birth_source": "structured",  # profile / search / None also possible
}
```

Examples are synthetic. Do not copy participant records into this README or tests.

`source` identifies a supplied record or hit field; `path` identifies the field/expression to inspect in that source. Issues deliberately omit raw notes and raw unparsed values. Consumers can look up the referenced original record locally. `name_sources` provides provenance for unchanged string-valued names.

Counts describe parsing candidates, not unique facts. One age expression can yield two birth-year facts, so `parsed` is not necessarily the length of `births`. Deduplication and output ordering are deterministic.

## 4. Four states: absence is not failure

| State | Meaning | Country example | May it support a full-set contradiction? |
|---|---|---|---|
| `MISSING` | No eligible value was supplied | empty list, or only policy-excluded regions | No |
| `PARSED` | At least one eligible candidate parsed; none failed | only recognisable countries | Potentially, after policy checks |
| `PARTIAL` | Some eligible candidates parsed and some failed | `GB` plus an unrecognised value | No for that field |
| `UNPARSED` | Eligible information exists but none could be used, or a required investigation was not performed | only unrecognised values | No |

`International` and `Europe` are deliberately ignored by policy. They increment `ignored`, not `unparsed`. An unknown value is not silently mapped to a country. Territories such as Hong Kong and Macao remain distinct from China.

A year-only date **is PARSED**, not PARTIAL. Missing month/day retain `None`; they are not mismatches. Invalid dates remain unparsed rather than being silently reduced to their year.

A malformed value or failed earlier source remains visible even if fallback produces a fact. For example an invalid structured birthday plus a readable profile birthday yields retained birthday facts and PARTIAL birth quality.

## 5. Caller obligations before deciding

```python
from common import field_is_complete
from hitfacts import hit_facts

facts = hit_facts(hit, data)
if not field_is_complete(facts, "countries"):
    # Do not make LOCATION_MISMATCH from the remaining parsed countries.
    # Consider independent, sufficient grounds; otherwise REVIEW.
    pass
```

`field_is_complete` requires a recognised V1 envelope, PARSED status, positive parsed count, zero unparsed count and no blocking issue for that field. Missing/unknown metadata versions fail closed. PARSED means syntactically usable, not verified, correct, or identical to the customer.

| Decision ground | Required quality and policy checks |
|---|---|
| DOB mismatch | Complete, trusted customer birthday and complete hit birthday alternatives; every alternative must contradict under the SOP |
| Location mismatch | Complete countries on **both** sides; all disjoint; obey the name+birthday agreement exception; unresolved facts that could affect that exception require review |
| Verified name mismatch | Complete hit names/aliases, trusted verified customer name and sufficient real name parts; compare every eligible name |
| Type mismatch | Known, parsed type on both sides; missing type is not a different type |
| Temporal impossibility | Complete relevant birth/incorporation and report dates; apply conservative partial-date bounds and the exact policy threshold |
| Deceased | Complete death and screening dates; prove death was before screening, not the current date |
| Same entity | Required positive agreement **and** no unresolved identity-relevant contradiction; PARSED alone never proves agreement |

An issue is field-specific. An unreadable country does not by itself invalidate an independent, fully supported birthday contradiction. Conversely, a positive match must not ignore unresolved facts that could hide a contradiction. When the remaining evidence cannot settle identity, REVIEW.

Lane A currently returns its existing Person dictionary. It must adopt equivalent V1 metadata, or have the shared comparison layer explicitly validate completeness. Do not simply label every Lane A field PARSED. Legacy objects passed to `field_is_complete` intentionally fail closed. The current all-REVIEW runner does not consume this contract yet.

## 6. Alternatives, conflicts and skipped sources

- Multiple birthdays supplied by the watchlist are alternatives, not automatically a conflict. Preserve all of them.
- An age at a date gives two possible birth years, without invented month/day. Guard every alternative before clearing on DOB mismatch.
- A duplicate search `result_id` with differing content is an unresolved source conflict: skip that result and emit blocking `UNRESOLVED_SOURCE_CONFLICT` for births. Identical duplicates do not duplicate facts.
- Other genuine conflicts should use the same issue shape and set `blocking=True` for the affected field. Do not invent a preferred fact to suppress a conflict.
- Birth source order is structured `dobs`, first profile paragraph, then supplied search results. Companies use only structured `dobs` for incorporation.
- Search birth results require a matching query, policy listing phrase and a country tied to the hit. Namesakes that fail these filters contribute no birth facts.
- `data["search_by_query"] = {}` means an available index with no matching results. An omitted index means search was not performed: `SEARCH_NOT_PROVIDED`, not proof that no birthday exists.
- Report dates count only in the exact policy-defined English report-line format. Other wordings are outside this extraction rule. Invalid dates within the exact format are reported as unparsed, and can prevent a trustworthy earliest-date comparison.

## 7. Internal metadata vs official output

Quality, issues and name-source maps are internal handoff data. Do not add them indiscriminately to `output/dev.jsonl`. The shared decision layer emits only the organiser's output fields and cites only decisive evidence. No final identity decision is generated by Lane B alone.

Before integration, teammate acceptance checks:

1. Existing Fact values and sources still reach the comparison layer.
2. Partial countries or birthdays cannot be used for a full-set mismatch.
3. Unknown entity type does not become an individual/company mismatch.
4. A conflict blocks the affected rule; independent sufficient evidence can still be considered.
5. Old objects without quality metadata are not silently treated as complete.
6. Final reason codes, evidence IDs and output schema still pass the official checker.

## 8. Run the required checks

From repository root after every system edit:

```sh
system/run dev output/dev.jsonl
python3 validate.py --data dev --output output/dev.jsonl --score dev/practice_labels.jsonl
python3 -m unittest discover tests
```

`output/dev.jsonl` must be generated by `system/run`, never edited by hand. Do not commit `dev/`, `validate.py`, credentials or private raw diagnostics. Unit tests validate the contract; an all-REVIEW score of zero is not proof of end-to-end identity accuracy. Final architecture/runtime/cost documentation remains a separate deliverable.
