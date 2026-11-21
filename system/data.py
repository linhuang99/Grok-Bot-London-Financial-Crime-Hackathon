"""Load one data folder and index it for lookups (Lane A).

Reads only the folder it is given. alerts.jsonl and hits.jsonl are required;
any other file may be missing or damaged: it is skipped with a warning, so the
system still answers every hit and the affected hits fall back to REVIEW.

Records keep their original values, because evidence must cite IDs exactly as
they appear in the files. Only lookup keys are normalised.
"""
import json
import os
import re
import sys

from common import fold

REQUIRED = ("alerts", "hits")
OPTIONAL = ("customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results")

# Tables with one row per ID: a repeated ID keeps the first row and warns.
PRIMARY_KEYS = {
    "alerts": "alert_id", "hits": "hit_id", "customers": "record_id",
    "kyc_checks": "check_id", "notes": "note_id", "search_results": "result_id",
}


class DataError(Exception):
    """The folder cannot be used at all: a required file is missing."""


def id_key(value):
    """Lookup key for an ID: surrounding spaces removed. Blank or not text gives None."""
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def text_key(value):
    """Lookup key for an email or login handle: like id_key, and case-insensitive."""
    key = id_key(value)
    return key.lower() if key else None


def phone_key(value):
    """Lookup key for a phone number: its digits only. Fewer than 6 digits is not a usable phone."""
    digits = re.sub(r"\D", "", value) if isinstance(value, str) else ""
    return digits if len(digits) >= 6 else None


# Letters that accent removal leaves alone, written the way they are usually spelt in ASCII.
_ASCII_SPELLING = str.maketrans({"ł": "l", "ø": "o", "æ": "ae", "œ": "oe", "đ": "d", "ð": "d",
                                 "þ": "th", "ı": "i", "ħ": "h"})


def search_keys(name):
    """Possible search_results.query keys for a name, the dev data's form first.

    A query is the name's words, lowercased, without accents, one-letter words
    (initials) dropped, in alphabetical order: "Mitchell, Charlee D." is stored
    as "charlee mitchell". The dev data drops letters such as "ł" ("Paweł" is
    stored as "pawe"); the ASCII spelling ("pawel") and the letter removed
    outright are tried too, in case the unseen data differs. Names with no
    Latin letters (Arabic, Cyrillic) give no key.
    """
    if not isinstance(name, str):
        return []
    folded = fold(name)
    # Drop non-ASCII letters outright, but keep non-ASCII punctuation as a word break (O’Connor).
    letters_dropped = "".join(c if c.isascii() else "" if c.isalpha() else " " for c in folded)
    keys = []
    for variant in (folded, folded.translate(_ASCII_SPELLING), letters_dropped):
        key = " ".join(sorted(w for w in re.findall(r"[a-z0-9]+", variant) if len(w) > 1))
        if key and key not in keys:
            keys.append(key)
    return keys


def find_search_results(data, name):
    """Search results stored under any key of the name, without repeats."""
    found, seen = [], set()
    for key in search_keys(name):
        for row in data["search_by_query"].get(key, []):
            if row.get("result_id") not in seen:
                seen.add(row.get("result_id"))
                found.append(row)
    return found


def load(data_dir):
    """Read every file in data_dir into tables plus lookup indexes.

    Returns a dict: the raw tables by file name ("alerts", "customers", ...),
    the indexes below, "name_variants" and "warnings" (also printed to stderr).
    Index values are lists wherever one key can match several rows.
    """
    warnings = []
    data = {"warnings": warnings}
    for name in REQUIRED + OPTIONAL:
        path = os.path.join(data_dir, name + ".jsonl")
        if not os.path.isfile(path):
            if name in REQUIRED:
                raise DataError("missing required file %s.jsonl in %s" % (name, data_dir))
            _warn(warnings, "%s.jsonl is missing; using an empty table" % name)
            data[name] = []
            continue
        rows = _read_jsonl(path, name, warnings)
        if name in PRIMARY_KEYS:
            rows = _first_per_id(rows, name, PRIMARY_KEYS[name], warnings)
        data[name] = rows
    data["name_variants"] = _read_variants(os.path.join(data_dir, "name_variants.json"), warnings)

    data["hits_by_id"] = {id_key(r["hit_id"]): r for r in data["hits"]}
    data["customers_by_id"] = {id_key(r["record_id"]): r for r in data["customers"]}
    data["customers_by_email"] = _group(data["customers"], "email", text_key)
    data["accounts_by_id"] = _group(data["accounts"], "account_id", id_key)  # joint accounts: one row per holder
    data["accounts_by_login"] = _group(data["accounts"], "login_handle", text_key)
    data["accounts_by_customer"] = _group(data["accounts"], "customer_id", id_key)
    data["applicant_by_account_customer"] = _applicants(data["onboarding"], warnings)
    data["kyc_by_applicant"] = _group(data["kyc_checks"], "applicant_id", id_key)
    data["notes_by_email"] = _group(data["notes"], "requester_email", text_key)
    data["search_by_query"] = _group(data["search_results"], "query", _stored_query_key)
    data["customers_by_phone"] = _group(data["customers"], "phone", phone_key)
    data["customers_by_document"] = _document_owners(data)
    return data


def _warn(warnings, message):
    warnings.append(message)
    print("data: warning: " + message, file=sys.stderr)


def _read_jsonl(path, name, warnings):
    """Rows of a JSON Lines file. Blank lines are ignored; a damaged line is skipped with a warning."""
    rows = []
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        for number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                _warn(warnings, "%s.jsonl line %d is not valid JSON; skipped" % (name, number))
                continue
            if not isinstance(row, dict):
                _warn(warnings, "%s.jsonl line %d is not a JSON object; skipped" % (name, number))
                continue
            rows.append(row)
    return rows


def _first_per_id(rows, name, field, warnings):
    kept, seen = [], set()
    for row in rows:
        key = id_key(row.get(field))
        if key is None:
            _warn(warnings, "%s.jsonl has a row without %s; skipped" % (name, field))
        elif key in seen:
            _warn(warnings, "%s.jsonl repeats %s %s; kept the first" % (name, field, key))
        else:
            seen.add(key)
            kept.append(row)
    return kept


def _group(rows, field, key_fn):
    """key -> rows with that key, in file order. Rows without a usable key are left out."""
    index = {}
    for row in rows:
        key = key_fn(row.get(field))
        if key is not None:
            index.setdefault(key, []).append(row)
    return index


def _applicants(onboarding, warnings):
    """(account_id, customer_id) -> kyc_applicant_id. A conflicting repeat keeps the first."""
    index = {}
    for row in onboarding:
        key = (id_key(row.get("account_id")), id_key(row.get("customer_id")))
        applicant = id_key(row.get("kyc_applicant_id"))
        if None in key or applicant is None:
            continue
        if key in index and index[key] != applicant:
            _warn(warnings, "onboarding.jsonl gives account %s and customer %s two applicants; kept the first" % key)
            continue
        index.setdefault(key, applicant)
    return index


def _document_owners(data):
    """Document number on an approved check -> customer IDs whose onboarding leads to that check."""
    customers_by_applicant = {}
    for row in data["onboarding"]:
        applicant, customer = id_key(row.get("kyc_applicant_id")), id_key(row.get("customer_id"))
        if applicant and customer:
            customers_by_applicant.setdefault(applicant, []).append(customer)
    owners = {}
    for check in data["kyc_checks"]:
        number = text_key(check.get("document_number"))
        if number and (check.get("result") or "").strip().lower() == "approved":
            for customer in customers_by_applicant.get(id_key(check.get("applicant_id")), []):
                if customer not in owners.setdefault(number, []):
                    owners[number].append(customer)
    return owners


def _stored_query_key(query):
    keys = search_keys(query)
    return keys[0] if keys else None


def _read_variants(path, warnings):
    empty = {"groups": [], "company_legal_forms": []}
    if not os.path.isfile(path):
        _warn(warnings, "name_variants.json is missing; no name variants")
        return empty
    try:
        with open(path, encoding="utf-8-sig") as f:
            variants = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError):
        _warn(warnings, "name_variants.json is not valid JSON; no name variants")
        return empty
    if not isinstance(variants, dict):
        _warn(warnings, "name_variants.json is not a JSON object; no name variants")
        return empty
    return {"groups": variants.get("groups") or [],
            "company_legal_forms": variants.get("company_legal_forms") or []}
