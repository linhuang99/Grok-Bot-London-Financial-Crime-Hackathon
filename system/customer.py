"""Build a customer's identity facts (Lane A, dev/POLICY.md principles 4 and 6).

A Person is what the decision compares with a watchlist hit: one customer's
legal name, date of birth and countries, each a Fact carrying the ID of the
record that proves it. Verified beats declared: the most recent approved
identity check gives the legal name and date of birth, and rejected or expired
checks are not evidence. Without one, the customer record's own (declared)
facts are used, and their CUS source shows it.
"""
from common import country_name, fold, parse_date
from data import id_key, phone_key, text_key
from notes import is_kyc_note, kyc_check, lived_in


def person(record_ids, data):
    """The Person for one customer, given the IDs of all their records (the first is output).

    Person = {
        "record_ids", "record_id", "entity_type",
        "verified_name": Fact | None,    latest approved check
        "legal_name": Fact,              verified name if any, else the record's full name
        "names": [Fact],                 legal name first, then every record name, no repeats
        "dob": Fact | None,              verified if readable, else declared; companies: incorporation
        "countries": [Fact],             residence and nationality of every record, every approved document
        "unreadable_countries": [Fact],  values we could not read: never clear on location while any exist
        "complete_fields": [str],        fields Lane A has fully investigated (see complete_fields below)
    }
    """
    records = [data["customers_by_id"][i] for i in map(id_key, record_ids) if i in data["customers_by_id"]]
    if not records:
        raise ValueError("no known customer record among %r" % (record_ids,))
    checks = _approved_checks(records, data)
    verified = _latest(checks)

    verified_name = None
    if verified and _text(verified.get("verified_name")):
        verified_name = _fact(_text(verified["verified_name"]), verified["check_id"])
    record_names = [_fact(_text(r.get(field)), r["record_id"])
                    for r in records for field in ("full_name", "preferred_name", "login_name") if _text(r.get(field))]
    legal_name = verified_name or (record_names[0] if record_names else None)

    countries, unreadable = _countries(records, checks, data)
    return {
        "record_ids": [r["record_id"] for r in records],
        "record_id": records[0]["record_id"],
        "entity_type": records[0].get("entity_type"),
        "verified_name": verified_name,
        "legal_name": legal_name,
        "names": _without_repeats([legal_name] + record_names),
        "dob": _dob(verified, records),
        "countries": countries,
        "unreadable_countries": unreadable,
        "complete_fields": complete_fields(records, verified, data),
    }


def complete_fields(records, verified, data):
    """Fields of this person that Lane A has fully investigated, for quality.adapt_person.

    Claimed conservatively, because a clear on an incomplete field can be unsafe.
    Table checks and notes are all read, so a field is incomplete only when:
    - names: the latest approved check's name could not be read;
    - births: the latest approved check's date of birth could not be read;
    - countries: another record may belong to the same person (merged in A7).
    """
    fields = ["entity_type"]
    if verified is None or _text(verified.get("verified_name")):
        fields.append("names")
    if verified is None or parse_date(verified.get("verified_dob")):
        fields.append("births")
    if not _may_have_other_records(records, data):
        fields.append("countries")
    return fields


def _may_have_other_records(records, data):
    """True when another record shares a phone and full date of birth, or an approved document number."""
    own = {r["record_id"] for r in records}
    for record in records:
        dob = parse_date(record.get("dob"))
        for other in data["customers_by_phone"].get(phone_key(record.get("phone")), []):
            if other["record_id"] not in own and dob and None not in dob and parse_date(other.get("dob")) == dob:
                return True
    for check in _approved_checks(records, data):
        if set(data["customers_by_document"].get(text_key(check.get("document_number")), [])) - own:
            return True
    return False


def _fact(value, source):
    return {"value": value, "source": source}


def _text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def _notes(records, data):
    """Notes filed under the records' own emails, without repeats. Never another customer's."""
    found, seen = [], set()
    for record in records:
        for note in data["notes_by_email"].get(text_key(record.get("email")), []):
            if note.get("note_id") not in seen:
                seen.add(note.get("note_id"))
                found.append(note)
    return found


def _approved_checks(records, data):
    """Approved identity checks: KYC table rows (record -> accounts -> onboarding -> checks) and KYC notes."""
    checks = [kyc_check(n) for n in _notes(records, data) if is_kyc_note(n) and n.get("note_id")]
    seen = {c["check_id"] for c in checks}
    for record in records:
        record_id = id_key(record["record_id"])
        for account in data["accounts_by_customer"].get(record_id, []):
            applicant = data["applicant_by_account_customer"].get((id_key(account.get("account_id")), record_id))
            for check in data["kyc_by_applicant"].get(applicant, []):
                approved = (check.get("result") or "").strip().lower() == "approved"
                if approved and check.get("check_id") and check["check_id"] not in seen:
                    seen.add(check["check_id"])
                    checks.append(check)
    return checks


def _latest(checks):
    """The most recent check; an unreadable date counts as oldest, and ties go to the check ID."""
    def order(check):
        date = parse_date(check.get("checked_at")) or (0, None, None)
        return tuple(part or 0 for part in date), check["check_id"]
    return max(checks, key=order) if checks else None


def _dob(verified, records):
    if verified and parse_date(verified.get("verified_dob")):
        return _fact(parse_date(verified["verified_dob"]), verified["check_id"])
    for record in records:
        if parse_date(record.get("dob")):
            return _fact(parse_date(record["dob"]), record["record_id"])
    return None


def _countries(records, checks, data):
    """Countries tied to the customer, and the values that could not be read as a country.

    Records' residence and nationality, every approved document's country, and
    every country a note says the customer lived in.
    """
    values = [(r.get(field), r["record_id"]) for r in records for field in ("residence_country", "nationality")]
    values += [(c.get("document_country"), c["check_id"]) for c in checks]
    values += [(country, c["check_id"]) for c in checks for country in c.get("note_countries", [])]
    values += [(country, n["note_id"]) for n in _notes(records, data)
               if not is_kyc_note(n) and n.get("note_id") for country in lived_in(n)]
    countries, unreadable = [], []
    for value, source in values:
        if not _text(value):
            continue
        name = country_name(value)
        if name:
            countries.append(_fact(name, source))
        else:
            unreadable.append(_fact(_text(value), source))
    return _sorted_unique(countries), _sorted_unique(unreadable)


def _without_repeats(facts):
    """Keep the first fact for each name, compared without case or accents."""
    kept, seen = [], set()
    for fact in facts:
        if fact and fold(fact["value"]) not in seen:
            seen.add(fold(fact["value"]))
            kept.append(fact)
    return kept


def _sorted_unique(facts):
    unique = {(f["value"], f["source"]): f for f in facts}
    return [unique[key] for key in sorted(unique)]
