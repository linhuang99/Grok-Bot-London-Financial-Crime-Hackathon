"""Find the customer behind an alert (Lane A, dev/POLICY.md principle 2).

An alert shows the customer as screened and often carries a link: an account,
a login or an email. resolve() follows every link to customer records. When
the links lead to more than one record (a joint account), the screened
details pick between them. A single linked record is the customer.

An alert with no link is searched for: every record whose name agrees with
the screened name and whose other details fit what was screened (checkpoint
A6). A link that leads nowhere finds nobody: a namesake found by searching is
not the customer the alert was raised on, and clearing on their facts would be unsafe.

Each record found is then grown into its person (principle 3, checkpoint A7):
records sharing a phone and the same full date of birth, or a document number
on approved checks, are one person, and so is any record linked to them.
"""
import re
import sys

from common import country_name, dates_agree, fold, parse_date
from customer import approved_checks
from data import id_key, phone_key, text_key
from names import company_names_agree, names_agree


def resolve(alert, data):
    """The people the alert could be: a list of people, each a list of customer record IDs.

    [] means no customer was found. A person's first ID is the record that was
    found; the others are their other records, in ID order.
    """
    records = linked_records(alert, data)
    if not records and _has_link(alert):
        print("link: warning: alert %s links to no customer; nobody resolved" % alert.get("alert_id"), file=sys.stderr)
        return []
    if not records:
        records = search(alert, data)
    elif len(records) > 1:
        records = [r for r in records if fits_screened(alert, r, data)]
    people = []
    for record in records:
        record_id = id_key(record["record_id"])
        if not any(record_id in p for p in people):
            people.append(same_person(record_id, data))
    return people


def same_person(record_id, data):
    """The record and every record of the same person: [record_id, others in ID order]."""
    found, todo = {record_id}, [record_id]
    while todo:
        for other in _linked_records(data["customers_by_id"][todo.pop()], data):
            if other not in found:
                found.add(other)
                todo.append(other)
    return [record_id] + sorted(found - {record_id})


def _linked_records(record, data):
    """Records sharing a phone and the same full date of birth, or an approved document number.

    A shared phone alone is not enough: family members often share one.
    """
    linked = set()
    dob = parse_date(record.get("dob"))
    if dob and None not in dob:
        for other in data["customers_by_phone"].get(phone_key(record.get("phone")), []):
            if parse_date(other.get("dob")) == dob:
                linked.add(id_key(other["record_id"]))
    for check in approved_checks([record], data):
        linked.update(data["customers_by_document"].get(text_key(check.get("document_number")), []))
    linked.discard(id_key(record["record_id"]))
    return {r for r in linked if r in data["customers_by_id"]}


def search(alert, data):
    """Records that fit an alert without a working link, in file order (principle 2).

    The screened name must agree with a record name; date of birth, country,
    city and entity type, where screened, must fit too. Cheap checks run before
    names, and a screened birth year narrows the records looked at.
    """
    screened = alert.get("customer") or {}
    name = screened.get("name")
    if not isinstance(name, str) or not name.strip():
        return []  # nothing to search by: never guess a customer
    dob = parse_date(screened.get("dob"))
    candidates = data["customers_by_birth_year"].get(dob[0], []) if dob else data["customers"]
    kind = screened.get("entity_type")
    return [r for r in candidates
            if (kind not in ("Individual", "Company") or r.get("entity_type") == kind)
            and _dob_fits(screened, r) and _country_fits(screened, r) and _city_fits(screened, r)
            and _name_fits(screened, r, data)]


def linked_records(alert, data):
    """Customer records reached through the alert's account, login and email links, without repeats."""
    ids = []
    account = id_key(alert.get("account_ref"))
    if account:
        ids += [row.get("customer_id") for row in data["accounts_by_id"].get(account, [])]
    login = text_key(alert.get("login_handle"))
    if login:
        ids += [row.get("customer_id") for row in data["accounts_by_login"].get(login, [])]
    email = text_key(alert.get("email"))
    if email:
        ids += [row.get("record_id") for row in data["customers_by_email"].get(email, [])]
    records, seen = [], set()
    for record_id in map(id_key, ids):
        if record_id and record_id not in seen and record_id in data["customers_by_id"]:
            seen.add(record_id)
            records.append(data["customers_by_id"][record_id])
    return records


def fits_screened(alert, record, data):
    """True when the record fits what was screened: name, date of birth, country and city.

    A screened detail that is missing, or that cannot be read on either side,
    never rules a record out: unknown stays unknown.
    """
    screened = alert.get("customer") or {}
    return (_name_fits(screened, record, data) and _dob_fits(screened, record)
            and _country_fits(screened, record) and _city_fits(screened, record))


def _has_link(alert):
    return bool(id_key(alert.get("account_ref")) or text_key(alert.get("login_handle")) or text_key(alert.get("email")))


def _name_fits(screened, record, data):
    name = screened.get("name")
    if not isinstance(name, str) or not name.strip():
        return True
    company = "Company" in (record.get("entity_type"), screened.get("entity_type"))
    agree = company_names_agree if company else names_agree
    record_names = [record.get(field) for field in ("full_name", "preferred_name", "login_name")]
    return any(isinstance(n, str) and n.strip() and agree(name, n, data["name_variants"]) for n in record_names)


def _dob_fits(screened, record):
    screened_dob, record_dob = parse_date(screened.get("dob")), parse_date(record.get("dob"))
    return screened_dob is None or record_dob is None or dates_agree(screened_dob, record_dob)


def _country_fits(screened, record):
    screened_country = country_name(screened.get("country"))
    if screened_country is None:
        return True
    values = [v for v in (record.get("residence_country"), record.get("nationality")) if isinstance(v, str) and v.strip()]
    countries = [country_name(v) for v in values]
    if not countries or None in countries:  # a value we cannot read might be the match
        return True
    return screened_country in countries


def _city_fits(screened, record):
    city = fold(screened.get("city")).strip()
    if not city:
        return True
    place = fold(record.get("city")) + " " + fold(record.get("address"))
    if not place.strip():
        return True
    return re.search(r"(?<!\w)" + re.escape(city) + r"(?!\w)", place) is not None
