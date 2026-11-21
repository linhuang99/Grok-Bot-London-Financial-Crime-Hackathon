"""Read customer notes into identity facts (Lane A, dev/POLICY.md principles 4 and 6).

Notes are free text in thousands of wordings, and the unseen set words them
differently again, so nothing here matches whole sentences. It looks for the
pieces instead:

- A KYC note records an approved identity check written up by the onboarding
  team. Its earliest date is the date of birth and its latest the check date
  (a person is born before they are checked); the name is the one run of
  capitalised words that is not a country; the country is the document's.
- Any other note can say where the customer lived. Every country it mentions
  counts: counting a country mentioned in passing costs at most a REVIEW,
  while missing one the customer lived in could invent a location mismatch.
"""
import re

from common import countries_in_text, country_name, find_dates

_BIRTH_WORDS = re.compile(r"\b(?:dob|d\.o\.b|born|birth)\b", re.IGNORECASE)
_SHORT_CODES = re.compile(r"\b(?:U\.S\.A\.|U\.K\.|U\.S\.|USA|UAE|UK)(?!\w)")
# Capitalised words that are never part of a name in these notes.
_NOT_NAME_WORDS = {"DOB", "ID", "KYC", "UK", "USA", "UAE", "US", "EU", "PEP", "AML", "N/A"}
# Document words: "UNITED KINGDOM PASSPORT" is a document, not a person's name.
_DOCUMENT_WORDS = {"PASSPORT", "LICENCE", "LICENSE", "DRIVING", "NATIONAL", "IDENTITY", "CARD",
                   "DOCUMENT", "PERMIT", "VISA", "RESIDENCE"}
# The earliest date is a date of birth only if it is this many years before the next one: a person is
# born long before any check, issue or expiry date ("expires 2031-06-30 ... verified on 2024-02-01").
MIN_YEARS_BEFORE_CHECK = 16


def is_kyc_note(note):
    return (note.get("channel") or "").strip().lower() == "kyc"


def kyc_check(note):
    """A KYC note shaped like a kyc_checks row, so it competes with table checks by date.

    Name, dates and country that cannot be found are None (unknown, never guessed).
    """
    text = note.get("text") if isinstance(note.get("text"), str) else ""
    dates = sorted(find_dates(text), key=lambda found: found[1])
    birth = checked = None
    if len(dates) >= 2:
        checked = dates[-1][0]
        if dates[1][1][0] - dates[0][1][0] >= MIN_YEARS_BEFORE_CHECK:
            birth = dates[0][0]
    elif dates and _BIRTH_WORDS.search(text):
        birth = dates[0][0]
    elif dates:
        checked = dates[0][0]
    countries = sorted(countries_in_text(text))
    return {
        "check_id": note.get("note_id"),
        "verified_name": verified_name(text),
        "verified_dob": birth,
        "checked_at": checked,
        "document_country": countries[0] if len(countries) == 1 else None,
        "note_countries": countries,
        "document_number": None,
        "result": "approved",
    }


def verified_name(text):
    """The one run of two or more capitalised words that is not a country, else None.

    "Persona validated EVA FERNÁNDEZ (DOB 17 June 1976) on 2025-12-24" gives "EVA FERNÁNDEZ".
    None when there is no such run, or more than one (ambiguous).
    """
    runs, current = [], []
    for token in text.split():
        word = token.strip("()[]{},.;:!?\"")
        opens, closes = token[:1] in "([{\"", token[-1:] in ")]},.;:!?\""
        if word[-2:] in ("'s", "’s"):  # possessive: "EVA GARCIA's identity"
            word, closes = word[:-2], True
        capital = len(word) >= 2 and word.isupper() and any(c.isalpha() for c in word) \
            and word.replace(".", "") not in _NOT_NAME_WORDS
        if opens or not capital:
            runs.append(current)
            current = []
        if capital:
            current.append(word)
        if closes:
            runs.append(current)
            current = []
    runs.append(current)
    names = [" ".join(run) for run in runs if len(run) >= 2 and not _names_a_thing(run)]
    names = list(dict.fromkeys(names))
    return names[0] if len(names) == 1 else None


def _names_a_thing(words):
    """True when capitalised words name a document or a country, not a person."""
    if any(w.upper() in _DOCUMENT_WORDS for w in words):
        return True
    return any(country_name(" ".join(words[i:i + k])) and len(" ".join(words[i:i + k])) > 3
               for k in (1, 2, 3) for i in range(len(words) - k + 1))


def lived_in(note):
    """Countries a note other than a KYC note ties to the customer."""
    text = note.get("text") if isinstance(note.get("text"), str) else ""
    found = set(countries_in_text(text))
    found.update(country_name(code.replace(".", "")) for code in _SHORT_CODES.findall(text))
    return sorted(c for c in found if c)
