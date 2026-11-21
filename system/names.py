"""Name-part agreement under identity SOP principle 8, not fuzzy-score cutoffs."""
import re
from functools import lru_cache
from common import fold

_PLACEHOLDERS = {'na', 'n/a', 'test', 'unknown', 'xxx', 'none', 'null', 'n', 'a'}


def name_parts(name, variants=None, *, company=False):
    text = fold(name)
    previous = None
    while text != previous:
        previous = text
        text = re.sub(r'\([^()]*\)|\[[^\[\]]*\]|\{[^{}]*\}', ' ', text)
    text = re.sub(r'\bn\s*/\s*a\b', ' ', text)
    # Punctuation separates parts; initials, placeholders and digits are not parts.
    parts = [x for x in re.findall(r'\w+', text, re.UNICODE) if x.isalpha()]
    excluded = set(_PLACEHOLDERS)
    if company:
        excluded.update(fold(x) for x in (variants or {}).get('company_legal_forms', []))
    return tuple(dict.fromkeys(x for x in parts if len(x) > 1 and x not in excluded))


def _distance(a, b, limit):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        row = [i]
        for j, y in enumerate(b, 1):
            row.append(min(row[-1] + 1, prev[j] + 1, prev[j-1] + (x != y)))
        if min(row) > limit:
            return limit + 1
        prev = row
    return prev[-1]


def _part_agrees(a, b, groups):
    if a == b or any(a in g and b in g for g in groups):
        return True
    n = min(len(a), len(b))
    limit = 0 if n < 4 else 1 if n <= 6 else 2
    return limit > 0 and _distance(a, b, limit) <= limit


def _agree(a, b, variants, company=False):
    left = name_parts(a, variants, company=company)
    right = name_parts(b, variants, company=company)
    if not left or not right:
        return False
    groups = [set(fold(x) for x in g) for g in variants.get('groups', [])]
    edges = []
    for i, x in enumerate(left):
        for j, y in enumerate(right):
            if _part_agrees(x, y, groups):
                edges.append((1 << i, 1 << j))
    # A joined part covers the consecutive split parts, but counts as one match.
    for single, split, reverse in [(left, right, False), (right, left, True)]:
        for i, x in enumerate(single):
            for start in range(len(split)):
                joined = split[start]
                mask = 1 << start
                for end in range(start + 1, len(split)):
                    joined += split[end]
                    mask |= 1 << end
                    if len(joined) > len(x):
                        break
                    if joined == x:
                        edges.append((mask, 1 << i) if reverse else (1 << i, mask))
    all_left, all_right = (1 << len(left)) - 1, (1 << len(right)) - 1

    @lru_cache(None)
    def search(lmask, rmask, count):
        if count >= 2:
            return True
        if len(left) <= len(right) and lmask == all_left:
            return True
        if len(right) <= len(left) and rmask == all_right:
            return True
        for lm, rm in edges:
            if not (lm & lmask or rm & rmask) and search(lmask | lm, rmask | rm, count + 1):
                return True
        return False
    return search(0, 0, 0)


def names_agree(name_a, name_b, variants):
    """Agreed individual-name interface; no country or identity inference."""
    return _agree(name_a, name_b, variants)


def company_names_agree(name_a, name_b, variants):
    """Company-only helper: remove legal forms without altering personal names."""
    return _agree(name_a, name_b, variants, company=True)


def usable_individual_name(name):
    """Policy gate: fewer than two real customer parts cannot confirm/name-clear."""
    return len(name_parts(name)) >= 2
