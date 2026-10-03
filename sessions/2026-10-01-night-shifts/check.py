"""Check sonnets.txt against the skeleton: meter, rhyme, punctuation, slot openings.

Usage: python check.py [-v]     (-v prints the scansion of every line)
"""
import re
import sys
import json
import pronouncing

HERE = __file__.rsplit("/", 1)[0]

# rhyme vowel (stress stripped) and the coda after it, per position 1..14
RHYME = {"A": (("AY",), "T"), "B": (("AO", "AA", "OW"), "R"), "C": (("EH",), "D"),
         "D": (("OW",), ""), "E": (("EY",), "N"), "F": (("AO", "AA"), "L"),
         "G": (("EY",), "K")}
SCHEME = "ABABCDCDEFEFGG"
ENDS = ",;,.,;,.,;,.,."
PROPER = {"Old"}           # moth names that start a line
PAIRS = [(0, 2), (1, 3), (4, 6), (5, 7), (8, 10), (9, 11), (12, 13)]

# words CMUdict lacks or gets wrong for this purpose: name -> phones
OVERRIDES = {
    "gannets": ["G AE1 N AH0 T S"], "dusky": ["D AH1 S K IY0"],
    "misted": ["M IH1 S T IH0 D"], "curtained": ["K ER1 T AH0 N D"],
    "crosshairs": ["K R AO1 S HH EH2 R Z"], "unheated": ["AH0 N HH IY1 T IH0 D"],
    "thumbprint": ["TH AH1 M P R IH2 N T"], "pencilled": ["P EH1 N S AH0 L D"],
    "unlovely": ["AH0 N L AH1 V L IY0"], "outspread": ["AW2 T S P R EH1 D"],
    "hedgerows": ["HH EH1 JH R OW2 Z"], "unfed": ["AH0 N F EH1 D"], "silvered": ["S IH1 L V ER0 D"],
    # British: moor rhymes with more (CMU only has the American M UH1 R)
    "moor": ["M UH1 R", "M AO1 R"],
}


def load(path=f"{HERE}/sonnets.txt"):
    sonnets, cur = {}, None
    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if line.startswith("## "):
            num, title = line[3:].split("|", 1)
            cur = int(num.strip())
            sonnets[cur] = {"title": title.strip(), "lines": [], "diag": []}
        elif line.strip() and not line.startswith("#") and cur is not None:
            diag = line.rstrip().endswith(" *")
            text = line.rstrip()[:-2].rstrip() if diag else line.rstrip()
            sonnets[cur]["lines"].append(text)
            sonnets[cur]["diag"].append(diag)
    return sonnets


def words_of(text):
    out = []
    for w in re.findall(r"[A-Za-z][A-Za-z'’]*", text):
        w = w.replace("’", "'").lower()
        if w.endswith("'") and not w.endswith("s'"):
            w = w[:-1]
        if w.endswith("s'"):
            w = w[:-1]
        out.append(w)
    return out


def phones(w):
    if w in OVERRIDES:
        return OVERRIDES[w]
    ps = pronouncing.phones_for_word(w)
    if not ps and w.endswith("'s"):
        ps = [p + " Z" for p in pronouncing.phones_for_word(w[:-2])]
    return ps


def stresses(ph):
    return [int(c) for c in re.findall(r"\d", ph)]


def scan(text):
    """Best scansion as iambic pentameter. Returns (violations, notes, pattern) or None."""
    ws = words_of(text)
    options = []
    for w in ws:
        ps = phones(w)
        if not ps:
            return None, f"unknown word: {w}"
        options.append(sorted({tuple(stresses(p)) for p in ps}))
    # DP over words: state = syllables used -> (cost, notes, pattern)
    best = {0: (0, [], "")}
    for w, opts in zip(ws, options):
        nxt = {}
        for used, (cost, notes, pat) in best.items():
            for st in opts:
                c, n = cost, list(notes)
                if len(st) > 1:
                    for i, s in enumerate(st):
                        pos = used + i + 1           # 1-based syllable position
                        if s == 1 and pos % 2 == 1:
                            if pos == 1:
                                n.append(f"initial inversion on '{w}'")
                            else:
                                c += 1
                                n.append(f"'{w}' stressed on weak syllable {pos}")
                p = pat + "".join("/" if (s and len(st) > 1) else ("x" if len(st) > 1 else "·") for s in st)
                key = used + len(st)
                if key not in nxt or c < nxt[key][0]:
                    nxt[key] = (c, n, p)
        best = nxt
    if 10 not in best:
        counts = sorted(best)
        return None, f"syllables possible: {counts}, need 10"
    return best[10], None


LEGAL_ONSETS = {"P R", "T R", "K R", "B R", "D R", "G R", "F R", "TH R", "SH R", "P L", "K L",
                "B L", "G L", "F L", "S L", "S T", "S P", "S K", "S N", "S M", "S W", "K W",
                "T W", "D W", "S T R", "S P R", "S K R", "S P L", "S K W"}


def onset_of(word, toks, i):
    """Onset of the stressed syllable at toks[i], as the ear hears it.

    If the word ends in another dictionary word that carries the stress (a-WAKE,
    up-RIGHT, ig-NITE), use that word's onset; otherwise take the longest legal
    onset from the consonants before the vowel."""
    def bare(seq):
        return [t.rstrip("012") for t in seq]
    vowel_before = any(t[-1].isdigit() for t in toks[:i])
    if not vowel_before:                       # stressed syllable starts the word
        return " ".join(toks[:i])
    for cut in range(1, len(word) - 2):        # longest embedded word first
        for ph in pronouncing.phones_for_word(word[cut:]):
            st = ph.split()
            if len(st) < len(toks) and bare(st) == bare(toks[-len(st):]):
                k = len(toks) - len(st)
                if k <= i:
                    return " ".join(toks[k:i])
    j = i
    while j > 0 and not toks[j - 1][-1].isdigit():
        j -= 1
    cluster = toks[j:i]
    if j == 0:
        return " ".join(cluster)
    for n in range(len(cluster), 0, -1):
        if n == 1 or " ".join(cluster[-n:]) in LEGAL_ONSETS:
            return " ".join(cluster[-n:])
    return ""


def rhyme_parts(word, letter):
    """All (onset, rhyme) for pronunciations of word that end on the target rhyme."""
    vowels, coda = RHYME[letter]
    found = []
    for ph in phones(word):
        toks = ph.split()
        idx = [i for i, t in enumerate(toks) if t[-1] in "12"]
        if not idx:
            continue
        i = idx[-1]
        v, rest = toks[i][:-1], " ".join(toks[i + 1:])
        if v in vowels and rest == coda:
            found.append((onset_of(word, toks, i), v + (" " + rest if rest else "")))
    return found


def main(verbose=False):
    sonnets = load()
    problems, warnings = [], []
    endwords = {k: [] for k in range(14)}
    for n, s in sorted(sonnets.items()):
        L = s["lines"]
        if len(L) != 14:
            problems.append(f"sonnet {n}: {len(L)} lines")
            continue
        for k, text in enumerate(L):
            tag = f"{n}.{k + 1:<2}"
            res, err = scan(text)
            if err:
                problems.append(f"{tag} {err}: {text}")
            else:
                cost, notes, pat = res
                if cost:
                    problems.append(f"{tag} meter ({'; '.join(x for x in notes if 'weak' in x)}): {text}")
                if verbose:
                    print(f"{tag} {pat:<12} {text}" + (f"   [{'; '.join(notes)}]" if notes else ""))
            if not text.endswith(ENDS[k]):
                problems.append(f"{tag} should end with '{ENDS[k]}': {text}")
            first = text.split()[0].strip(",;")
            should_cap = k in (0, 4, 8, 12)
            if first not in ("I", "I'm", "I'll", "I've") and first not in PROPER \
                    and (first[0].isupper() != should_cap):
                problems.append(f"{tag} capitalisation of '{first}'")
            if k in (0, 4, 10) and first not in ("I", "I'm", "I'll", "I've"):
                problems.append(f"{tag} must start with I")
            if k in (3, 11) and first != "and":
                problems.append(f"{tag} must start with 'and'")
            if k == 8 and first not in ("But", "Yet"):
                problems.append(f"{tag} must start with But/Yet")
            if k == 12 and first != "So":
                problems.append(f"{tag} must start with So")
            ew = words_of(text)[-1]
            rp = rhyme_parts(ew, SCHEME[k])
            if not rp:
                problems.append(f"{tag} '{ew}' does not rhyme on {SCHEME[k]} {RHYME[SCHEME[k]]}: {phones(ew)}")
            endwords[k].append((n, ew, rp))
    for a, b in PAIRS:
        for na, wa, ra in endwords[a]:
            for nb, wb, rb in endwords[b]:
                if wa == wb:
                    problems.append(f"same word '{wa}' at {na}.{a + 1} and {nb}.{b + 1}")
                elif any(x == y for x in ra for y in rb):
                    problems.append(f"identical rhyme '{wa}' ({na}.{a + 1}) / '{wb}' ({nb}.{b + 1})")
    for k in range(14):
        seen = {}
        for n, w, _ in endwords[k]:
            if w in seen:
                warnings.append(f"line {k + 1}: '{w}' used by sonnets {seen[w]} and {n}")
            seen[w] = n
    # hidden sonnet: line k comes from sonnet k mod 10
    hidden = []
    for k in range(14):
        n = (k + 1) % 10
        if n in sonnets and len(sonnets[n]["lines"]) == 14:
            if not sonnets[n]["diag"][k]:
                problems.append(f"{n}.{k + 1} should be marked * (hidden sonnet)")
            hidden.append(sonnets[n]["lines"][k])
    for n, s in sonnets.items():
        for k, d in enumerate(s["diag"]):
            if d and (k + 1) % 10 != n:
                problems.append(f"{n}.{k + 1} marked * but is not on the diagonal")
    print(f"{len(sonnets)} sonnets, {sum(len(s['lines']) for s in sonnets.values())} lines")
    for k in range(14):
        print(f"  line {k + 1:>2} {SCHEME[k]}: " + ", ".join(f"{w}({n})" for n, w, _ in endwords[k]))
    if len(hidden) == 14:
        print("\nHidden sonnet 12345678901234:\n  " + "\n  ".join(hidden))
    for w in warnings:
        print("warning:", w)
    for p in problems:
        print("PROBLEM:", p)
    print(f"\n{len(problems)} problems, {len(warnings)} warnings")
    return problems


if __name__ == "__main__":
    sys.exit(1 if main("-v" in sys.argv) else 0)
