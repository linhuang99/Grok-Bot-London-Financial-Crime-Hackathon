"""Conservative bridge from Lane A Person dictionaries to Lane B quality V1.

This module does not resolve customers, attest investigation completeness,
change its input, or decide identity. Caller scope must be explicit.
"""
from copy import deepcopy
from common import country_name, fold, parse_date
from names import name_parts

_FIELDS = ('names', 'births', 'countries', 'entity_type')


def adapt_person(person, *, complete_fields=()):
    """Return a copy with V1 parsing diagnostics and a births alias for dob.

    Default coverage is unknown. Only the producer/caller can attest complete
    investigation of a field; an empty unreadable_countries list proves no such
    thing. Existing versioned metadata is preserved, never silently upgraded.
    """
    if not isinstance(person, dict):
        raise TypeError('person must be a dictionary')
    if isinstance(complete_fields, str):
        raise ValueError('complete_fields must be an iterable of field names')
    complete = set(complete_fields)
    if complete - set(_FIELDS):
        raise ValueError('unsupported complete field')
    result = deepcopy(person)
    if person.get('quality_version') is not None:
        return result
    counts = {f: {'parsed': 0, 'unparsed': 0, 'ignored': 0} for f in _FIELDS}
    issues = []
    record = person.get('record_id')
    record = record if isinstance(record, str) else ''

    def issue(field, code, source, path, *, parse_failure=True):
        if parse_failure:
            counts[field]['unparsed'] += 1
        item = {'field': field, 'code': code, 'source': source,
                'path': path, 'blocking': True}
        if item not in issues:
            issues.append(item)

    def fact(value, field, path):
        if not isinstance(value, dict) or not isinstance(value.get('source'), str) or not value['source'].strip():
            issue(field, 'INVALID_FACT', record, path)
            return None
        return value

    names = person.get('names', [])
    if not isinstance(names, list):
        issue('names', 'INVALID_TYPE', record, 'names'); names = []
    for raw in names:
        f = fact(raw, 'names', 'names')
        if f is None:
            continue
        value = f.get('value')
        if not isinstance(value, str):
            issue('names', 'INVALID_NAME', f['source'], 'names')
        elif not name_parts(value):
            counts['names']['ignored'] += 1
        else:
            counts['names']['parsed'] += 1
            if any(c.isalpha() and not c.isascii() for c in fold(value)):
                issue('names', 'UNREADABLE_NAME_SCRIPT', f['source'], 'names')

    birth = person.get('dob')
    result['births'] = []
    if birth is not None:
        f = fact(birth, 'births', 'dob')
        if f is not None:
            parsed = parse_date(f.get('value'))
            if parsed:
                result['births'] = [{'value': parsed, 'source': f['source']}]
                counts['births']['parsed'] += 1
            else:
                issue('births', 'INVALID_DATE', f['source'], 'dob')

    countries = person.get('countries', [])
    if not isinstance(countries, list):
        issue('countries', 'INVALID_TYPE', record, 'countries'); countries = []
    for raw in countries:
        f = fact(raw, 'countries', 'countries')
        if f is not None:
            if country_name(f.get('value')):
                counts['countries']['parsed'] += 1
            else:
                issue('countries', 'UNRECOGNISED_COUNTRY', f['source'], 'countries')
    unreadable = person.get('unreadable_countries')
    if not isinstance(unreadable, list):
        issue('countries', 'UPSTREAM_UNREADABLE_STATUS_UNKNOWN', record, 'unreadable_countries')
    else:
        for raw in unreadable:
            source = raw.get('source') if isinstance(raw, dict) else record
            source = source if isinstance(source, str) else record
            # Preserve the producer's explicit warning, even if a new alias
            # table could parse the string now. Never erase upstream doubt.
            issue('countries', 'UPSTREAM_UNREADABLE_COUNTRY', source, 'unreadable_countries')

    entity_type = person.get('entity_type')
    if entity_type in ('Individual', 'Company'):
        counts['entity_type']['parsed'] += 1
    elif entity_type is not None:
        issue('entity_type', 'UNRECOGNISED_ENTITY_TYPE', record, 'entity_type')

    quality = {}
    for field, c in counts.items():
        if field not in complete:
            issue(field, 'UPSTREAM_COVERAGE_UNKNOWN', record, field, parse_failure=False)
        p, u = c['parsed'], c['unparsed']
        state = 'PARTIAL' if p and u else 'PARSED' if p else 'UNPARSED' if u else 'MISSING'
        quality[field] = dict(status=state, coverage='COMPLETE' if field in complete else 'UNKNOWN', **c)
    result.update(quality_version=1, quality=quality,
                  issues=sorted(issues, key=lambda i: (i['field'], i['source'], i['path'], i['code'])))
    return result
