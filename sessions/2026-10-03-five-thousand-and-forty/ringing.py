"""Core change-ringing machinery: rows, place notation, Grandsire Triples leads.

A row is a tuple of bell numbers (1-based) in striking order.
A change is given by the set of places (1-based positions) that stay put;
every other adjacent pair swaps.
"""
from itertools import permutations

N = 7  # working bells for Triples (the tenor, 8, always rings last and is ignored here)
ROUNDS = tuple(range(1, N + 1))


def parse_pn(pn):
    """'3.1.7' -> list of frozensets of places. '-' or 'x' means no places."""
    out = []
    for tok in pn.split('.'):
        if tok in ('x', '-'):
            out.append(frozenset())
        else:
            out.append(frozenset(int(c, 16) if c not in 'ET' else {'E': 11, 'T': 12}[c] for c in tok))
    return out


def apply(row, places):
    r = list(row)
    i = 0
    n = len(r)
    while i < n:
        if (i + 1) in places:
            i += 1
        else:
            assert i + 1 < n and (i + 2) not in places, (row, places)
            r[i], r[i + 1] = r[i + 1], r[i]
            i += 2
    return tuple(r)


# Grandsire Triples: plain lead, bob lead, single lead (14 changes each).
PLAIN = parse_pn('3.1.7.1.7.1.7.1.7.1.7.1.7.1')
BOB = PLAIN[:12] + parse_pn('3.1')
SINGLE = PLAIN[:12] + parse_pn('3.123')
CALLS = {'p': PLAIN, 'b': BOB, 's': SINGLE}


def lead(lh, call='p'):
    """Rows of one lead starting from lead head lh (inclusive), and the next lead head."""
    rows = [lh]
    r = lh
    for ch in CALLS[call]:
        r = apply(r, ch)
        rows.append(r)
    return rows[:-1], rows[-1]


def touch(calls, start=ROUNDS):
    """Expand a string of calls (one per lead) into rows. Returns (rows, final lead head)."""
    rows = []
    lh = start
    for c in calls:
        rs, lh = lead(lh, c)
        rows.extend(rs)
    return rows, lh


def parity(row):
    """0 for even (in-course), 1 for odd."""
    r = list(row)
    p = 0
    for i in range(len(r)):
        while r[i] != i + 1:
            j = r[i] - 1
            r[i], r[j] = r[j], r[i]
            p ^= 1
    return p


def as_perm(row):
    """Row as a position transformation from rounds (0-based tuple)."""
    return tuple(b - 1 for b in row)


def compose(a, b):
    """Row a, then apply the transformation that takes rounds to row b. Equivalent to
    ringing from a whatever changes take rounds to b."""
    return tuple(a[b[i] - 1] for i in range(len(b)))


def fmt(row):
    return ''.join(str(b) for b in row)
