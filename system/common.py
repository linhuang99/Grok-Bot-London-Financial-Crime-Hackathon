"""Policy helpers. Standard library only; no participant data embedded."""
import calendar
import json
import re
import unicodedata
from pathlib import Path


def fold(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(text or '')).casefold()
                   if not unicodedata.combining(c))


MONTHS = {fold(n): i for i in range(1, 13)
          for n in (calendar.month_name[i], calendar.month_abbr[i])}
MONTHS['sept'] = 9


def parse_date(text):
    """Return (year, month|None, day|None); never invent missing parts."""
    if isinstance(text, (tuple, list)):
        if len(text) != 3:
            return None
        y, m, d = text
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
        if not 1 <= y <= 9999 or (m is None and d is not None):
            return None
        if m is not None and not 1 <= m <= 12:
            return None
        if d is not None and not 1 <= d <= calendar.monthrange(y, m)[1]:
            return None
        return y, m, d
    except (ValueError, TypeError, OverflowError):
        return None


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


def country_name(text):
    """Canonical country/territory, or None for regions and unknown values.

    Exact lookup, not substring matching (US must not match Russia).
    Unknown country strings must not be treated as proven contradictions.
    """
    if not isinstance(text, str):
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
