"""Policy helpers. Standard library only; no participant data embedded.

Owned by Lane A (see brain/roadmap.md). Lane B's code depends on fold,
parse_date, country_name, country_at_end, countries_in_text and search_query:
keep their behaviour, and their tests in tests/test_lane_b.py, unchanged.
"""
import calendar
import json
import re
import unicodedata
from pathlib import Path


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '')).casefold()
                   if not unicodedata.combining(c))


# Provider dates are English; do not depend on the process locale.
_ENGLISH_MONTHS = ('January', 'February', 'March', 'April', 'May', 'June',
                   'July', 'August', 'September', 'October', 'November', 'December')
MONTHS = {fold(n): i for i, month in enumerate(_ENGLISH_MONTHS, 1)
          for n in (month, month[:3])}
MONTHS['sept'] = 9

# Plausible years for birth, incorporation, report and death dates. A typo year
# ("0099") stays unknown rather than creating a false date-of-birth mismatch.
MIN_YEAR, MAX_YEAR = 1800, 2100


def parse_date(text):
    """Return (year, month|None, day|None); never invent missing parts."""
    if isinstance(text, (tuple, list)):
        if len(text) != 3:
            return None
        y, m, d = text
        if any(v is not None and (not isinstance(v, int) or isinstance(v, bool)) for v in text):
            return None
    elif isinstance(text, str):
        s = text.strip()
        iso = re.fullmatch(r'(\d{4})(?:-(\d{1,2})(?:-(\d{1,2}))?)?', s)
        slash = re.fullmatch(r'(\d{1,2})/(\d{1,2})/(\d{4})', s)
        if iso:
            y, m, d = [int(x) if x else None for x in iso.groups()]
        elif slash:
            d, m, y = map(int, slash.groups())
        else:
            words = re.sub(r'(\d)(?:st|nd|rd|th)\b', r'\1', fold(s))
            words = words.replace(',', '').split()
            if len(words) == 3 and words[1] in MONTHS:
                d, m, y = words[0], MONTHS[words[1]], words[2]
            elif len(words) == 3 and words[0] in MONTHS:
                m, d, y = MONTHS[words[0]], words[1], words[2]
            elif len(words) == 2 and words[0] in MONTHS:
                y, m, d = words[1], MONTHS[words[0]], None
            else:
                return None
    else:
        return None
    try:
        y = int(y)
        m = int(m) if m is not None else None
        d = int(d) if d is not None else None
        if not MIN_YEAR <= y <= MAX_YEAR or (m is None and d is not None):
            return None
        if m is not None and not 1 <= m <= 12:
            return None
        if d is not None and not 1 <= d <= calendar.monthrange(y, m)[1]:
            return None
        return y, m, d
    except (ValueError, TypeError, OverflowError):
        return None


_MONTH_WORD = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?'
_DAY_WORD = r'\d{1,2}(?:st|nd|rd|th)?'
_DATE_IN_TEXT = re.compile(
    r'(?<![\w/-])(?:\d{4}-\d{1,2}-\d{1,2}|\d{1,2}/\d{1,2}/\d{4}|'
    r'%s %s,? \d{4}|%s %s,? \d{4}|%s \d{4})(?![\w/-])' % (_DAY_WORD, _MONTH_WORD, _MONTH_WORD, _DAY_WORD, _MONTH_WORD),
    re.IGNORECASE)


def find_dates(text):
    """Every date written in free text, as (the text matched, parsed date), in reading order.

    Formats are the ones parse_date reads: 1990-05-04, 04/05/1990, 4 May 1990,
    May 4, 1990 and May 1990. A bare year is not taken as a date in free text.
    """
    found = []
    for match in _DATE_IN_TEXT.finditer(text if isinstance(text, str) else ''):
        raw = match.group(0).replace('.', '')
        parsed = parse_date(raw)
        if parsed:
            found.append((match.group(0), parsed))
    return found


# Ways an age is written next to a person: "a 30-year-old", "33 year old",
# "aged 52", "at the age of 38", "he was 46." (the number must end the phrase,
# so "was 3 times" and "was 4,600" are not ages), "Fiorani, 52, who..." and
# "with 26, Maria Miller".
_AGE_IN_TEXT = re.compile(
    r"\b(\d{1,3})[- ]years?[- ]old\b"
    r"|\baged? (?:of )?(\d{1,3})\b"
    r"|\bage of (\d{1,3})\b"
    r"|\b(?:was|is|turned|reached|then) (\d{1,3})(?=[.,;:](?!\d)|\s*$)"
    r"|(?<!\d), (\d{1,3}),(?!\d)"
    r"|\b(\d{1,3}), (?=[^\W\d_]+ [^\W\d_])",  # "26, Maria Miller": checked for capitals below
    re.IGNORECASE)
MAX_AGE = 120


def ages_at_dates(text):
    """[(age, date)] when the text states exactly one age and exactly one date, else [].

    "In February 2010, at the age of 33, ..." gives [(33, (2010, 2, None))]: the
    person was born in 1976 or 1977. Two dates or two ages are ambiguous and give
    nothing, as do ages above MAX_AGE: a wrong age would invent a birth year.
    """
    if not isinstance(text, str):
        return []
    dates = [parsed for _, parsed in find_dates(text)]
    ages = []
    for match in _AGE_IN_TEXT.finditer(text):
        if match.group(6) and not all(w[:1].isupper() for w in text[match.end():].split()[:2]):
            continue  # "N, x y" counts only before a capitalised name: "26, Maria Miller", not "12, plus costs"
        ages.append(int(next(g for g in match.groups() if g)))
    if len(dates) == 1 and len(ages) == 1 and 0 < ages[0] <= MAX_AGE:
        return [(ages[0], dates[0])]
    return []


def dates_agree(a, b):
    """True when two parsed dates are equal in every part both give.

    (1990, None, None) agrees with (1990, 5, 4); (1990, 5, None) does not agree
    with (1990, 6, 1). Unknown stays unknown: a missing part never disagrees.
    """
    return all(x is None or y is None or x == y for x, y in zip(a, b))


def _country_key(text):
    text = re.sub(r'\[[^\]]*\]', '', str(text))
    return re.sub(r'[^\w]+', ' ', fold(text)).strip()


# ISO code/name seed from the public-domain tzdata iso3166.tab, bundled so
# behaviour is independent of the machine running the submitted program.
_COUNTRIES = json.loads(Path(__file__).with_name('countries.json').read_text(encoding='utf-8'))
_ALIASES = {}
for _code, _name in _COUNTRIES.items():
    _ALIASES[_country_key(_code)] = _name
    _ALIASES[_country_key(_name)] = _name
for _name, _forms in {
    'United Kingdom': ['UK', 'GBR', 'Great Britain', 'British', 'United Kingdom of Great Britain and Northern Ireland'],
    'United States': ['USA', 'US American', 'American', 'United States of America', 'U.S.A.'],
    'Nigeria': ['Nigerian'], 'India': ['Indian'], 'Pakistan': ['Pakistani'],
    'Bangladesh': ['Bangladeshi'], 'China': ['Chinese', "People’s Republic of China"],
    'Russia': ['Russian', 'Russian Federation'], 'France': ['French'],
    'Germany': ['German'], 'Italy': ['Italian'], 'Spain': ['Spanish'],
    'Portugal': ['Portuguese'], 'Ireland': ['Irish'], 'Netherlands': ['Dutch', 'The Netherlands'],
    'Poland': ['Polish'], 'Ukraine': ['Ukrainian'], 'Romania': ['Romanian'],
    'Canada': ['Canadian'], 'Australia': ['Australian'], 'New Zealand': ['New Zealander'],
    'South Africa': ['South African'], 'Kenya': ['Kenyan'], 'Ghana': ['Ghanaian'],
    'Egypt': ['Egyptian'], 'Morocco': ['Moroccan'], 'Algeria': ['Algerian'],
    'Turkey': ['Turkish', 'Türkiye'], 'Iran': ['Iranian', 'Iran, Islamic Republic of'],
    'Iraq': ['Iraqi'], 'Syria': ['Syrian', 'Syrian Arab Republic'],
    'Saudi Arabia': ['Saudi', 'Saudi Arabian'], 'United Arab Emirates': ['UAE', 'Emirati'],
    'Israel': ['Israeli'], 'Palestine': ['Palestinian', 'Palestinian Territory', 'Palestina'],
    'Singapore': ['Singaporean'], 'Malaysia': ['Malaysian'], 'Indonesia': ['Indonesian'],
    'Philippines': ['Filipino', 'Philippine'], 'Thailand': ['Thai'],
    'Vietnam': ['Vietnamese', 'Viet Nam'], 'Japan': ['Japanese'],
    'South Korea': ['South Korean', 'Republic of Korea', 'Korea, Republic of'],
    'North Korea': ["Democratic People's Republic of Korea", "North Korean"],
    'Sri Lanka': ['Sri Lankan'], 'Nepal': ['Nepali', 'Nepalese'],
    'Brazil': ['Brazilian'], 'Mexico': ['Mexican'], 'Argentina': ['Argentine', 'Argentinian'],
    'Colombia': ['Colombian'], 'Peru': ['Peruvian'], 'Venezuela': ['Venezuelan'],
    'Sweden': ['Swedish'], 'Norway': ['Norwegian'], 'Denmark': ['Danish'],
    'Finland': ['Finnish'], 'Switzerland': ['Swiss'], 'Austria': ['Austrian'],
    'Belgium': ['Belgian'], 'Greece': ['Greek'], 'Czech Republic': ['Czech', 'Czechia'],
    'Hungary': ['Hungarian'], 'Bulgaria': ['Bulgarian'], 'Serbia': ['Serbian'],
    'Croatia': ['Croatian'], 'Lithuania': ['Lithuanian'], 'Latvia': ['Latvian'],
    'Estonia': ['Estonian'], 'Belarus': ['Belarusian'], 'Moldova': ['Moldovan'],
    'Bosnia and Herzegovina': ['Bosnia & Herzegovina', 'Bosnia and Herzegovina'], 'Kosovo': ['XK', 'Kosovan', 'Kosovo'],
    'British Virgin Islands': ['Virgin Islands (UK)', 'British Virgin Islands'], 'U.S. Virgin Islands': ['Virgin Islands (US)'],
    'Macao': ['Macau', 'Macao Special Administrative Region of China'],
    'Hong Kong': ['Hong Kong SAR'], 'Taiwan': ['Taiwanese'],
    "Côte d’Ivoire": ['Ivory Coast', "Cote d'Ivoire", 'Ivorian'],
    'Eswatini': ['Swaziland'], 'Tanzania': ['United Republic of Tanzania'],
}.items():
    for _form in _forms:
        _ALIASES[_country_key(_form)] = _name


# Placeholders are not countries. Checked before the code table, so "NA" is not
# read as Namibia: a placeholder read as a country could invent a location mismatch.
_PLACEHOLDERS = {_country_key(t) for t in ('NA', 'N/A', 'None', 'Unknown', 'Not known', 'TBC', 'XX', 'Test')}


def country_name(text):
    """Canonical country/territory, or None for regions, placeholders and unknown values.

    Exact lookup, not substring matching (US must not match Russia).
    Unknown country strings must not be treated as proven contradictions.
    """
    if not isinstance(text, str) or _country_key(text) in _PLACEHOLDERS:
        return None
    return _ALIASES.get(_country_key(text))


def country_at_end(text):
    """Countries at the end of an address or place of birth; never guess cities."""
    if not isinstance(text, str):
        return None
    direct = country_name(text)
    if direct:
        return direct
    return country_name(re.split(r'[,;\n]', text)[-1].strip())


def countries_in_text(text):
    """Recognise full country names/demonyms in prose, not ambiguous short codes."""
    s = ' ' + _country_key(text) + ' '
    found = set()
    # Longest aliases first: Macao's formal name contains "China", and
    # British Virgin Islands must not also count as United Kingdom.
    for alias, canonical in sorted(_ALIASES.items(), key=lambda item: (-len(item[0]), item[0])):
        if len(alias) <= 3:
            continue
        pattern = r'(?<!\w)' + re.escape(alias) + r'(?!\w)'
        if re.search(pattern, s):
            found.add(canonical)
            s = re.sub(pattern, ' ', s)
    return found


def search_query(name):
    return ' '.join(sorted(re.findall(r'\w+', fold(name))))


def country_parse_status(value, *, address=False):
    """(status, canonical): ignored policy regions differ from parse failures."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return 'MISSING', None
    if not isinstance(value, str):
        return 'UNPARSED', None
    canonical = country_at_end(value) if address else country_name(value)
    if canonical:
        return 'PARSED', canonical
    tail = re.split(r'[,;\n]', value)[-1] if address else value
    if _country_key(tail) in {'international', 'europe'}:
        return 'IGNORED', None
    return 'UNPARSED', None


def field_is_complete(facts, field):
    """V1 parsing gate, NOT an identity decision. Unknown contracts fail closed.

    Both sides must meet the relevant rule's requirements. PARSED does not
    mean verified or true; blocking conflicts still veto this gate.
    """
    if not isinstance(facts, dict) or facts.get('quality_version') != 1:
        return False
    quality = facts.get('quality')
    issues = facts.get('issues')
    if not isinstance(quality, dict) or not isinstance(issues, list):
        return False
    entry = quality.get(field)
    if not isinstance(entry, dict) or entry.get('status') != 'PARSED':
        return False
    parsed = entry.get('parsed')
    if not isinstance(parsed, int) or isinstance(parsed, bool) or parsed <= 0 or entry.get('unparsed') != 0:
        return False
    for issue in issues:
        if not isinstance(issue, dict):
            return False
        if issue.get('field') in (field, '*') and issue.get('blocking', True):
            return False
    return True
