"""Evidence-carrying watchlist facts. Does not decide or load practice labels."""
import re
from common import (parse_date, country_at_end, countries_in_text, search_query)

_MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
_DATE = rf'(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}/\d{{1,2}}/\d{{4}}|\d{{1,2}}\s+{_MONTH}\s+\d{{4}}|{_MONTH}\s+\d{{1,2}},?\s+\d{{4}}|{_MONTH}\s+\d{{4}}|\d{{4}}-\d{{1,2}}|\d{{4}})'
_BIRTH = re.compile(rf'\b(?:born|date\s+of\s+birth|d\.?o\.?b\.?)\s*(?:was\s+|is\s+)?[:=]?\s*(?:on\s+|in\s+)?(?P<date>{_DATE})(?!\d)', re.I)
_AGE = re.compile(rf'\baged?\s+(?P<age>\d{{1,3}})\b[^.;\n]{{0,90}}?\b(?:in|on|as\s+of)\s+(?P<date>{_DATE})(?!\d)', re.I)
_REPORT = re.compile(r'^According to [^;\n]+; (?P<date>(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}):', re.M)
_PHRASES = {'Sanctions': 'a sanctioned individual', 'PEP': 'a politically exposed person',
            'Enforcement': 'the subject of enforcement action', 'Adverse Media': 'named in adverse media',
            'SOE': 'a state-owned enterprise official'}


def _items(value):
    return value if isinstance(value, list) else [value] if value else []


def _fact(value, source):
    return {'value': value, 'source': source}


def _unique(facts):
    # Preserve alternatives and independent sources, with deterministic ordering.
    result = []
    for f in facts:
        if f not in result:
            result.append(f)
    return sorted(result, key=lambda f: (str(f['value']), f['source']))


def _births(text, source):
    found = []
    for match in _BIRTH.finditer(text):
        date = parse_date(match['date'])
        if date:
            found.append(_fact(date, source))
    for match in _AGE.finditer(text):
        age, date = int(match['age']), parse_date(match['date'])
        if date and 0 <= age <= 120:
            # Age at a date spans two possible years; no invented month or day.
            for year in (date[0] - age - 1, date[0] - age):
                if year > 0:
                    found.append(_fact((year, None, None), source))
    return _unique(found)


def hit_facts(hit, data):
    """Implement the agreed hit_facts(hit, data) -> dict interface.

    ``data`` needs only search_by_query. No runtime access to practice labels,
    network, customer records or mutable global caches.
    """
    hid = hit['hit_id']
    names = []
    combined = ' '.join(str(hit.get(k) or '').strip() for k in ('first_name', 'middle_name', 'last_name')).strip()
    for name in [hit.get('name'), *_items(hit.get('aliases')), combined, hit.get('best_matching_name')]:
        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())
    entity_type = hit.get('entity_type') or 'Individual'
    births = []
    for value in _items(hit.get('dobs')):
        parsed = parse_date(value)
        if parsed:
            births.append(_fact(parsed, hid + '#dobs'))
    countries = []
    for field in ('countries', 'nationality', 'citizenship', 'addresses', 'place_of_birth'):
        for value in _items(hit.get(field)):
            canonical = country_at_end(value)
            if canonical:
                countries.append(_fact(canonical, hid + '#' + field))
    countries = _unique(countries)
    notes = hit.get('profile_notes') or ''
    if not isinstance(notes, str):
        notes = ''
    reports = [parse_date(m['date']) for m in _REPORT.finditer(notes)]
    reports = [d for d in reports if d]
    earliest = _fact(min(reports), hid + '#profile_notes') if reports else None
    death = parse_date(hit.get('deceased_date'))
    if not births and entity_type != 'Company':
        first = re.split(r'\n\s*\n', notes.strip(), maxsplit=1)[0]
        # Report paragraphs describe events, not the provider's biographical lead.
        first = re.split(r'(?m)^According to ', first, maxsplit=1)[0]
        births = _births(first, hid + '#profile_notes')
        if not births:
            categories = _items(hit.get('categories'))
            category = hit.get('primary_category') or (categories[0] if categories else '')
            phrase = _PHRASES.get(category, 'named on a watchlist')
            tied = {f['value'] for f in countries}
            index = data.get('search_by_query', {})
            results = {}
            for name in names:
                for row in index.get(search_query(name), []):
                    results[row['result_id']] = row
            for rid, row in sorted(results.items()):
                text = str(row.get('title') or '') + '\n' + str(row.get('snippet') or '')
                if phrase.casefold() in text.casefold() and tied & countries_in_text(text):
                    births.extend(_births(text, rid))
    return {'hit_id': hid, 'entity_type': entity_type, 'names': names,
            'births': _unique(births), 'countries': countries, 'earliest_report': earliest,
            'death': _fact(death, hid + '#deceased_date') if death else None}
