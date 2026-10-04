"""Build the fill vocabulary: common English words (wordfreq) that are also
real dictionary words (web2, lowercase entries only, or a regular inflection
of one). Writes words.txt as "word<TAB>zipf" lines."""
import re
from wordfreq import top_n_list, zipf_frequency

WEB2 = {w.strip() for w in open('/usr/share/dict/web2') if w.strip().islower()}


def stems(w):
    """Candidate dictionary stems for a possibly inflected word."""
    out = {w}
    for suf, rep in [('s', ''), ('es', ''), ('ies', 'y'), ('ed', ''), ('ed', 'e'),
                     ('ied', 'y'), ('ing', ''), ('ing', 'e'), ('er', ''), ('er', 'e'),
                     ('ers', ''), ('ers', 'e'), ('est', ''), ('ly', ''), ('ily', 'y'),
                     ('ness', ''), ('ment', ''), ('ments', '')]:
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            base = w[:-len(suf)] + rep
            out.add(base)
            # doubled consonant: stopped -> stop, running -> run
            if suf in ('ed', 'ing', 'er', 'est') and len(base) >= 4 and base[-1] == base[-2]:
                out.add(base[:-1])
    return out


def build(n=90000, min_zipf=2.6):
    words = {}
    for w in top_n_list('en', n):
        if not re.fullmatch('[a-z]+', w) or not 3 <= len(w) <= 15:
            continue
        if not stems(w) & WEB2:
            continue
        z = zipf_frequency(w, 'en')
        if z >= min_zipf:
            words[w] = z
    return words


if __name__ == '__main__':
    words = build()
    with open('words.txt', 'w') as f:
        for w, z in sorted(words.items(), key=lambda kv: -kv[1]):
            f.write(f'{w}\t{z:.2f}\n')
    from collections import Counter
    print(len(words), sorted(Counter(len(w) for w in words).items()))
