"""Decide one watchlist hit against the customer it was raised on (dev/POLICY.md principles 3, 6, 7).

Clear (DIFFERENT_ENTITY) only on a contradiction, confirm (SAME_ENTITY) only on
agreement, otherwise REVIEW. Every rule first checks that the fields it relies
on are complete on both sides (Lane B's quality contract, common.field_is_complete):
a rule never clears on facts that were partly unreadable or not fully investigated.
"""
import calendar

from common import dates_agree, field_is_complete, parse_date
from names import company_names_agree, names_agree, usable_individual_name
from quality import adapt_person

MIN_AGE_AT_REPORT = 16


def decide(alert, hit, persons, facts, data):
    """One output line for the hit. persons: Person dicts for everyone the alert could be."""
    if not persons:
        return _line(alert, hit, "REVIEW", "INSUFFICIENT_DATA", None,
                     "No customer record could be found for this alert, so the hit cannot be compared "
                     "with the customer. A person needs to review it.", [])
    verdicts = [_decide_person(alert, hit, p, facts, data) for p in persons]
    if len(verdicts) == 1:
        decision, code, reason, evidence = verdicts[0]
        return _line(alert, hit, decision, code, persons[0]["record_id"], reason, evidence)
    if len({v[0] for v in verdicts}) == 1:
        decision, code, reason, evidence = verdicts[0]
        return _line(alert, hit, decision, code, "AMBIGUOUS", reason, _unique([e for v in verdicts for e in v[3]]))
    ids = ", ".join(p["record_id"] for p in persons)
    return _line(alert, hit, "REVIEW", "AMBIGUOUS_CUSTOMER_RECORD", "AMBIGUOUS",
                 "More than one customer fits this alert (%s) and they lead to different decisions on hit %s. "
                 "A person needs to review it." % (ids, hit["hit_id"]), [p["record_id"] for p in persons])


def _decide_person(alert, hit, person, facts, data):
    """(decision, reason_code, reason, evidence) for one customer."""
    customer = adapt_person(person, complete_fields=person.get("complete_fields", ()))
    variants = data["name_variants"]
    company = person.get("entity_type") == "Company"
    rid = person["record_id"]
    hit_name = hit.get("name") or (facts["names"][0] if facts["names"] else hit["hit_id"])
    legal = person["legal_name"]["value"] if person.get("legal_name") else None
    dob = person.get("dob")

    def complete(field):
        return field_is_complete(customer, field) and field_is_complete(facts, field)

    # Agreement, needed both to confirm and for the location exception.
    agree_fn = company_names_agree if company else names_agree
    name_usable = bool(legal) and (company or usable_individual_name(legal))
    matched_name = next((n for n in facts["names"] if name_usable and agree_fn(legal, n, variants)), None)
    agreeing_births = [b for b in facts["births"] if dob and dates_agree(dob["value"], b["value"])]
    customer_countries = {c["value"] for c in person["countries"]}
    hit_countries = {c["value"] for c in facts["countries"]}

    # --- Contradictions: clear only on complete facts.
    if complete("entity_type") and person.get("entity_type") in ("Individual", "Company") \
            and facts["entity_type"] in ("Individual", "Company") and person["entity_type"] != facts["entity_type"]:
        return ("DIFFERENT_ENTITY", "ENTITY_TYPE_MISMATCH",
                "The customer %s (%s) is %s, but the hit %s is %s. A person and a company cannot be the same entity."
                % (legal, rid, _kind(person["entity_type"]), hit_name, _kind(facts["entity_type"])), [rid])

    screened = parse_date(alert.get("screened_at"))
    death = facts.get("death")
    if death and field_is_complete(facts, "death") and screened and _latest(death["value"]) < _earliest(screened):
        return ("DIFFERENT_ENTITY", "DECEASED",
                "The hit's profile gives a date of death of %s, before the customer %s (%s) was screened on %s. "
                "A deceased person cannot be the customer." % (_show(death["value"]), legal, rid, _show(screened)), [rid])

    report = facts.get("earliest_report")
    if report and dob and field_is_complete(facts, "earliest_report") and field_is_complete(customer, "births"):
        if company and _earliest(dob["value"]) > _latest(report["value"]):
            return ("DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY",
                    "The company %s was incorporated on %s (%s), after the hit's earliest dated report on %s. "
                    "It could not have been the subject of that report."
                    % (legal, _show(dob["value"]), dob["source"], _show(report["value"])), _unique([rid, dob["source"]]))
        age = _max_age(dob["value"], report["value"])
        if not company and age < MIN_AGE_AT_REPORT:
            return ("DIFFERENT_ENTITY", "TEMPORAL_IMPOSSIBILITY",
                    "The customer was born in %s (%s), so they were at most %d when the hit's profile reported on %s. "
                    "They could not have been the person in that report."
                    % (_show(dob["value"]), dob["source"], age, _show(report["value"])), _unique([rid, dob["source"]]))

    if dob and facts["births"] and complete("births") and all(_contradicts(dob["value"], b["value"]) for b in facts["births"]):
        return ("DIFFERENT_ENTITY", "DOB_MISMATCH",
                "The customer's %s is %s (%s) but the hit gives %s. Every date the hit gives is more than a year "
                "apart or differs in month or day." % ("incorporation date" if company else "date of birth",
                                                        _show(dob["value"]), dob["source"], _births(facts)),
                _unique([rid, dob["source"]] + _search_sources(facts["births"])))

    if customer_countries and hit_countries and complete("countries") and not customer_countries & hit_countries \
            and not (matched_name and agreeing_births):
        return ("DIFFERENT_ENTITY", "LOCATION_MISMATCH",
                "The customer is linked only to %s, but the hit is linked only to %s. No country is shared."
                % (_join(customer_countries), _join(hit_countries)),
                _unique([rid] + [c["source"] for c in person["countries"]]))

    verified = person.get("verified_name")
    if verified and name_usable and field_is_complete(facts, "names") \
            and facts["names"] and not matched_name:
        return ("DIFFERENT_ENTITY", "NAME_MISMATCH_VERIFIED",
                "The customer's verified name is %s (%s), which does not agree with any of the hit's names, "
                "including %s." % (verified["value"], verified["source"], hit_name), _unique([rid, verified["source"]]))

    # --- Agreement: confirm only when nothing above contradicted.
    shared = customer_countries & hit_countries
    if not company and matched_name and agreeing_births and field_is_complete(customer, "births"):
        disjoint = customer_countries and hit_countries and not shared
        if not disjoint:
            code = "NAME_DOB_LOCATION_MATCH" if shared else "NAME_DOB_MATCH"
            where = " Both the customer and the hit are linked to %s." % _join(shared) if shared else ""
            return ("SAME_ENTITY", code,
                    "The customer's date of birth %s (%s) agrees with the hit's %s.%s The customer's name %s agrees "
                    "with the hit's name %s." % (_show(dob["value"]), dob["source"], _births(facts), where, legal,
                                                 matched_name),
                    _unique([rid, dob["source"]] + _search_sources(agreeing_births)))
    if company and matched_name and shared:
        return ("SAME_ENTITY", "NAME_LOCATION_MATCH",
                "Both the company and the hit are linked to %s. The customer's name %s agrees with the hit's name %s."
                % (_join(shared), legal, matched_name),
                _unique([rid] + [c["source"] for c in person["countries"] if c["value"] in shared]))

    return ("REVIEW", "INSUFFICIENT_DATA",
            "Nothing on file rules hit %s out for the customer %s (%s), and there is not enough agreement to "
            "confirm it. %s" % (hit_name, legal, rid, _what_is_missing(matched_name, agreeing_births, dob, facts)), [rid])


def _line(alert, hit, decision, code, record_id, reason, evidence):
    return {"hit_id": hit["hit_id"], "alert_id": alert["alert_id"], "decision": decision, "reason_code": code,
            "customer_record_id": record_id, "reason": reason, "evidence": evidence}


def _contradicts(customer, hit):
    """True when a hit birth date contradicts the customer's (principle 6)."""
    (cy, cm, cd), (hy, hm, hd) = customer, hit
    if abs(cy - hy) > 1:
        return True
    if cy == hy and cm and hm and cm != hm:
        return True
    return cy == hy and cm == hm and cm is not None and cd and hd and cd != hd


def _earliest(date):
    year, month, day = date
    return (year, month or 1, day or 1)


def _latest(date):
    year, month, day = date
    month = month or 12
    return (year, month, day or calendar.monthrange(year, month)[1])


def _max_age(birth, report):
    """The oldest the person can have been on the report date, for partial dates too."""
    born, on = _earliest(birth), _latest(report)
    return on[0] - born[0] - ((on[1], on[2]) < (born[1], born[2]))


def _show(date):
    year, month, day = date
    return "%04d" % year + ("-%02d" % month if month else "") + ("-%02d" % day if day else "")


def _births(facts):
    return " or ".join(dict.fromkeys(_show(b["value"]) for b in facts["births"]))


def _search_sources(births):
    """Search result IDs behind hit birth dates; hit fields are named in the reason instead."""
    return [b["source"] for b in births if "#" not in b["source"]]


def _join(countries):
    return ", ".join(sorted(countries))


def _kind(entity_type):
    return "a company" if entity_type == "Company" else "a person"


def _unique(items):
    return list(dict.fromkeys(i for i in items if i))


def _what_is_missing(matched_name, agreeing_births, dob, facts):
    if matched_name and not facts["births"]:
        return "The names agree, but the hit gives no date of birth to compare."
    if matched_name and not dob:
        return "The names agree, but the customer has no readable date of birth."
    if matched_name and not agreeing_births:
        return "The names agree, but the dates of birth neither agree nor clearly contradict."
    return "The facts on file are incomplete or do not settle the comparison."
