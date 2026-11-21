"""Watchlist facts with additive, fail-closed parsing diagnostics (contract v1).

No decisions, network calls, practice answers or inferred missing date parts.
"""
import re
from common import parse_date, country_parse_status, countries_in_text, fold
from data import search_keys
from names import name_parts

_FIELDS = ('names', 'births', 'countries', 'earliest_report', 'death', 'entity_type')
_MONTH = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)'
_DAY = r'\d{1,2}(?:st|nd|rd|th)?'
_DATE = rf'(?:\d{{4}}-\d{{1,2}}-\d{{1,2}}|\d{{1,2}}/\d{{1,2}}/\d{{4}}|{_DAY}\s+{_MONTH}\s+\d{{4}}|{_MONTH}\s+{_DAY},?\s+\d{{4}}|{_MONTH},?\s+\d{{4}}|\d{{4}}-\d{{1,2}}|\d{{4}})'
_BIRTH_LABEL = r'\b(?:born|date\s+of\s+birth|d\.?o\.?b\.?)(?=\W|$)'
_BIRTH = re.compile(rf'{_BIRTH_LABEL}\s*(?:was\s+|is\s+)?[:=]?\s*(?:on\s+|in\s+)?(?P<date>{_DATE})(?![\w/-])', re.I)
_AGE_LABEL = r'\bage(?:d)?\s+\d+\b'
_AGE = re.compile(rf'\bage(?:d)?\s+(?P<age>\d{{1,3}})\b[^.;\n]{{0,90}}?\b(?:in|on|as\s+of)\s+(?P<date>{_DATE})(?![\w/-])', re.I)
_MARKER = re.compile(rf'{_BIRTH_LABEL}|{_AGE_LABEL}', re.I)
_REPORT = re.compile(r'^According to [^;\n]+; (?P<date>(?:January|February|March|April|May|June|July|August|September|October|November|December) \d{1,2}, \d{4}):', re.M)
_PHRASES = {'Sanctions': 'a sanctioned individual', 'PEP': 'a politically exposed person',
            'Enforcement': 'the subject of enforcement action', 'Adverse Media': 'named in adverse media',
            'SOE': 'a state-owned enterprise official'}


def _items(value):
    return value if isinstance(value, list) else [value] if value is not None else []


def _missing(value):
    return value is None or (isinstance(value, str) and not value.strip())


def _fact(value, source):
    return {'value': value, 'source': source}


def _unique(facts):
    result = []
    for f in facts:
        if f not in result:
            result.append(f)
    return sorted(result, key=lambda f: (str(f['value']), f['source']))


class _Quality:
    def __init__(self):
        self.counts = {f: {'parsed': 0, 'unparsed': 0, 'ignored': 0} for f in _FIELDS}
        self.issues = []

    def good(self, field):
        self.counts[field]['parsed'] += 1

    def ignore(self, field):
        self.counts[field]['ignored'] += 1

    def bad(self, field, code, source, path):
        self.counts[field]['unparsed'] += 1
        issue = {'field': field, 'code': code, 'source': source, 'path': path, 'blocking': True}
        if issue not in self.issues:
            self.issues.append(issue)

    def finish(self):
        quality = {}
        for field, counts in self.counts.items():
            p, u = counts['parsed'], counts['unparsed']
            status = 'PARTIAL' if p and u else 'PARSED' if p else 'UNPARSED' if u else 'MISSING'
            quality[field] = dict(status=status, **counts)
        return quality, sorted(self.issues, key=lambda i: (i['field'], i['source'], i['path'], i['code']))


def _text_births(text, source, q):
    found, covered = [], []
    for match in _BIRTH.finditer(text):
        covered.append(match.span())
        date = parse_date(match['date'])
        if date:
            found.append(_fact(date, source)); q.good('births')
        else:
            q.bad('births', 'INVALID_DATE', source, 'birth_expression')
    for match in _AGE.finditer(text):
        covered.append(match.span())
        age, date = int(match['age']), parse_date(match['date'])
        if date and date[0] - age - 1 > 0:
            for year in (date[0] - age - 1, date[0] - age):
                found.append(_fact((year, None, None), source))
            q.good('births')
        else:
            q.bad('births', 'INVALID_AGE_DATE', source, 'age_expression')
    for marker in _MARKER.finditer(text):
        if not any(start <= marker.start() < end for start, end in covered):
            q.bad('births', 'UNSUPPORTED_BIRTH_EXPRESSION', source, 'birth_expression')
    return _unique(found)


def _names(hit, q):
    hid = hit['hit_id']; sources = {}
    def add(value, field):
        if _missing(value):
            return
        if not isinstance(value, str):
            q.bad('names', 'INVALID_TYPE', hid + '#' + field, field); return
        if not name_parts(value):
            q.ignore('names'); return
        value = value.strip()
        sources.setdefault(value, set()).add(hid + '#' + field)
        q.good('names')
    add(hit.get('name'), 'name')
    for value in _items(hit.get('aliases')):
        add(value, 'aliases')
    parts = []
    for field in ('first_name', 'middle_name', 'last_name'):
        value = hit.get(field)
        if isinstance(value, str) and value.strip():
            parts.append((value.strip(), field))
        elif not _missing(value):
            q.bad('names', 'INVALID_TYPE', hid + '#' + field, field)
    if parts:
        combined = ' '.join(p[0] for p in parts)
        if name_parts(combined):
            sources.setdefault(combined, set()).update(hid + '#' + p[1] for p in parts)
            q.good('names')
        else:
            q.ignore('names')
    add(hit.get('best_matching_name'), 'best_matching_name')
    for value, source_ids in sources.items():
        if any(c.isalpha() and not c.isascii() for c in fold(value)):
            for source in sorted(source_ids):
                q.bad('names', 'UNREADABLE_NAME_SCRIPT', source, source.split('#')[-1])
    ordered = sorted(sources, key=lambda n: (n.casefold(), n))
    return ordered, {name: sorted(sources[name]) for name in ordered}


def _countries(hit, q):
    found = []; hid = hit['hit_id']
    for field in ('countries', 'nationality', 'citizenship', 'addresses', 'place_of_birth'):
        for value in _items(hit.get(field)):
            status, country = country_parse_status(value, address=field in ('addresses', 'place_of_birth'))
            if status == 'PARSED':
                found.append(_fact(country, hid + '#' + field)); q.good('countries')
            elif status == 'IGNORED':
                q.ignore('countries')
            elif status == 'UNPARSED':
                q.bad('countries', 'UNRECOGNISED_COUNTRY', hid + '#' + field, field)
    return _unique(found)


def _reports(notes, hid, q):
    reports = []
    for match in _REPORT.finditer(notes):
        parsed = parse_date(match['date'])
        if parsed:
            reports.append(parsed); q.good('earliest_report')
        else:
            q.bad('earliest_report', 'INVALID_DATE', hid + '#profile_notes', 'dated_report')
    # Other report wordings are outside the policy, not parser failures.
    return _fact(min(reports), hid + '#profile_notes') if reports else None


def _search_births(hit, data, names, countries, q):
    hid = hit['hit_id']
    categories = _items(hit.get('categories'))
    category = hit.get('primary_category') or (categories[0] if categories else '')
    phrase = _PHRASES.get(category, 'named on a watchlist') if isinstance(category, str) else None
    if phrase is None:
        q.bad('births', 'INVALID_CATEGORY', hid + '#categories', 'categories'); return []
    index = data.get('search_by_query')
    if index is None:
        # An omitted index is an unperformed investigation, not absence of results.
        q.bad('births', 'SEARCH_NOT_PROVIDED', hid, 'search_by_query'); return []
    if not isinstance(index, dict):
        q.bad('births', 'INVALID_SEARCH_INDEX', hid, 'search_by_query'); return []
    tied = {f['value'] for f in countries}
    rows = {}
    for name in names:
        # Share Lane A's normalisation, but inspect all rows ourselves so a
        # conflicting duplicate source ID cannot be hidden by deduplication.
        for query in sorted(set(search_keys(name))):
            results = index.get(query, [])
            if not isinstance(results, list):
                q.bad('births', 'INVALID_SEARCH_RESULTS', hid, 'search_by_query'); continue
            for row in results:
                if not isinstance(row, dict) or (not isinstance(row.get('result_id'), str) or not row['result_id'].strip()):
                    q.bad('births', 'INVALID_SEARCH_RESULT', hid, 'search_by_query'); continue
                if row.get('query') is not None and query not in search_keys(row['query']):
                    q.bad('births', 'SEARCH_QUERY_MISMATCH', row['result_id'], 'query'); continue
                rows.setdefault(row['result_id'], []).append(row)
    found = []
    for rid, versions in sorted(rows.items()):
        row = versions[0]
        if any(other != row for other in versions[1:]):
            q.bad('births', 'UNRESOLVED_SOURCE_CONFLICT', rid, 'search_result'); continue
        title = row.get('title') if row.get('title') is not None else ''
        snippet = row.get('snippet') if row.get('snippet') is not None else ''
        if not isinstance(title, str) or not isinstance(snippet, str):
            q.bad('births', 'INVALID_SEARCH_TEXT', rid, 'snippet'); continue
        text = title + '\n' + snippet
        if phrase.casefold() in text.casefold() and tied & countries_in_text(text):
            found.extend(_text_births(text, rid, q))
    return _unique(found)


def hit_facts(hit, data):
    """Agreed signature; v1 adds quality, issues, name_sources, birth_source.

    Existing value fields retain their shapes. Missing quality on legacy inputs
    is NOT complete. See LANE_B_README.md before consuming these facts.
    """
    hid = hit['hit_id']; q = _Quality()
    names, name_sources = _names(hit, q)
    raw_type = hit.get('entity_type')
    entity_type = raw_type if raw_type in ('Individual', 'Company') else None
    if entity_type:
        q.good('entity_type')
    elif not _missing(raw_type):
        q.bad('entity_type', 'UNRECOGNISED_ENTITY_TYPE', hid + '#entity_type', 'entity_type')
    countries = _countries(hit, q)
    births = []
    for value in _items(hit.get('dobs')):
        if _missing(value):
            continue
        date = parse_date(value)
        if date:
            births.append(_fact(date, hid + '#dobs')); q.good('births')
        else:
            q.bad('births', 'INVALID_DATE', hid + '#dobs', 'dobs')
    birth_source = 'structured' if births else None
    notes = hit.get('profile_notes')
    if _missing(notes):
        notes = ''
    elif not isinstance(notes, str):
        q.bad('earliest_report', 'INVALID_TYPE', hid + '#profile_notes', 'profile_notes')
        if entity_type == 'Individual' and not births:
            q.bad('births', 'INVALID_TYPE', hid + '#profile_notes', 'profile_notes')
        notes = ''
    earliest = _reports(notes, hid, q)
    raw_death = hit.get('deceased_date'); death = parse_date(raw_death)
    if death:
        q.good('death')
    elif not _missing(raw_death):
        q.bad('death', 'INVALID_DATE', hid + '#deceased_date', 'deceased_date')
    if not births and entity_type == 'Individual':
        lead = re.split(r'\n\s*\n', notes.strip(), maxsplit=1)[0]
        lead = re.split(r'(?m)^According to ', lead, maxsplit=1)[0]
        births = _text_births(lead, hid + '#profile_notes', q)
        if births:
            birth_source = 'profile'
        else:
            births = _search_births(hit, data, names, countries, q)
            if births:
                birth_source = 'search'
    quality, issues = q.finish()
    return {'hit_id': hid, 'entity_type': entity_type, 'names': names,
            'births': _unique(births), 'countries': countries, 'earliest_report': earliest,
            'death': _fact(death, hid + '#deceased_date') if death else None,
            'quality_version': 1, 'quality': quality, 'issues': issues, 'name_sources': name_sources,
            'birth_source': birth_source}
