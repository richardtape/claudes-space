"""Check the letter-level mechanics of every clue in clues.json.

Each clue carries a parse: a small expression tree saying how the wordplay
builds the answer. This file checks every claim that can be checked by
counting letters: that anagram fodder really rearranges to the answer, that a
hidden word really is hidden, that reversals, deletions, containers and
charades add up, that quoted fodder really appears in the clue, that the
definition sits at one end of the clue, and that the enumeration fits the grid.

It cannot check meaning: whether 'doctor' can give DR, or whether two words
sound alike. Those are listed as trusted claims, not passed.

Parse nodes (JSON lists):
  ["syn", "LETTERS", "clue words"]    synonym / abbreviation, meaning trusted
  ["ana", "clue words"]               anagram of the words' letters
  ["hid", "clue words"]               answer hidden in the words
  ["hidrev", "clue words"]            hidden reversed
  ["first", "clue words"]             first letters of the words
  ["last", "clue words"]              last letters of the words
  ["odd", "clue words"] / ["even", "clue words"]   alternate letters
  ["rev", node]                       reversal of a node
  ["cat", node, node, ...]            charade: nodes in order
  ["ins", inner, outer]               inner placed inside outer
  ["del", node, "LETTERS"]            node with LETTERS removed (once each,
                                      as a contiguous run)
  ["lit", "LETTERS"]                  letters given directly (e.g. 'about' = C)
                                      - meaning trusted, like syn
  ["hom", "LETTERS", "clue words"]    sounds like - trusted
  ["dd"] / ["cd"]                     double / cryptic definition: no letters
"""
import json
import re
import sys

CHECKABLE = {'ana', 'hid', 'hidrev', 'first', 'last', 'odd', 'even', 'rev',
             'cat', 'ins', 'del'}


def letters(s):
    return re.sub('[^A-Z]', '', s.upper())


def words_of(s):
    """Lowercase words; a possessive 's is split off, so "Hen's" is "hen" + "'s"."""
    s = s.lower().replace('’', "'")
    s = re.sub(r"'s\b", " 's", s)
    return re.findall(r"[a-z0-9]+|'s", s)


def appears(fragment, clue):
    """Does the fragment occur in the clue as whole words, in order?"""
    f, c = words_of(fragment), words_of(clue)
    return any(c[i:i + len(f)] == f for i in range(len(c) - len(f) + 1))


class Check:
    def __init__(self, clue):
        self.clue = clue
        self.failures = []
        self.trusted = []
        self.claims = 0

    def need_text(self, kind, text):
        self.claims += 1
        if not appears(text, self.clue):
            self.failures.append(f'{kind}: "{text}" is not in the clue')

    def match(self, node, target):
        """Can node produce exactly target? Records fodder claims as it goes."""
        op = node[0]
        if op in ('syn', 'lit', 'hom'):
            return letters(node[1]) == target
        if op == 'ana':
            return sorted(letters(node[1])) == sorted(target)
        if op == 'hid':
            L = letters(node[1])
            return target in L and target != L
        if op == 'hidrev':
            return target[::-1] in letters(node[1])
        if op == 'first':
            return ''.join(w[0] for w in words_of(node[1])).upper() == target
        if op == 'last':
            return ''.join(w[-1] for w in words_of(node[1])).upper() == target
        if op == 'odd':
            return letters(node[1])[0::2] == target
        if op == 'even':
            return letters(node[1])[1::2] == target
        if op == 'rev':
            return self.match(node[1], target[::-1])
        if op == 'cat':
            return self.cat(node[1:], target)
        if op == 'ins':
            inner, outer = node[1], node[2]
            for a in range(1, len(target)):
                for b in range(a + 1, len(target)):
                    if self.match(inner, target[a:b]) and self.match(outer, target[:a] + target[b:]):
                        return True
            return False
        if op == 'del':
            removed = letters(node[2])
            src = self.produce(node[1])
            if src is None:
                return False
            for i in range(len(src) - len(removed) + 1):
                if src[i:i + len(removed)] == removed and src[:i] + src[i + len(removed):] == target:
                    return True
            return False
        raise ValueError(f'unknown node {op}')

    def cat(self, parts, target):
        if not parts:
            return target == ''
        for k in range(len(target) + 1):
            if self.match(parts[0], target[:k]) and self.cat(parts[1:], target[k:]):
                return True
        return False

    def produce(self, node):
        """Concrete letters for nodes that have them (needed under del)."""
        op = node[0]
        if op in ('syn', 'lit', 'hom'):
            return letters(node[1])
        if op == 'rev':
            p = self.produce(node[1])
            return p and p[::-1]
        if op == 'cat':
            ps = [self.produce(n) for n in node[1:]]
            return None if None in ps else ''.join(ps)
        if op in ('first', 'last', 'odd', 'even'):
            if op == 'first':
                return ''.join(w[0] for w in words_of(node[1])).upper()
            if op == 'last':
                return ''.join(w[-1] for w in words_of(node[1])).upper()
            L = letters(node[1])
            return L[0::2] if op == 'odd' else L[1::2]
        return None

    def walk(self, node):
        """Collect text claims and trusted claims from the whole tree."""
        op = node[0]
        if op in ('ana', 'hid', 'hidrev', 'first', 'last', 'odd', 'even'):
            self.need_text(op, node[1])
        elif op in ('syn', 'hom'):
            self.need_text(op, node[2])
            self.trusted.append(f'{op}: "{node[2]}" -> {letters(node[1])}')
        elif op == 'lit':
            self.trusted.append(f'lit: {letters(node[1])}')
        for child in node[1:]:
            if isinstance(child, list):
                self.walk(child)


def check_clue(c, slot_len=None):
    chk = Check(c['clue'])
    ans = letters(c['answer'])
    # enumeration
    chk.claims += 1
    enum_total = sum(int(x) for x in re.findall(r'\d+', c['enum']))
    if enum_total != len(ans):
        chk.failures.append(f'enumeration ({c["enum"]}) does not fit {ans} ({len(ans)})')
    if slot_len is not None:
        chk.claims += 1
        if slot_len != len(ans):
            chk.failures.append(f'answer length {len(ans)} != slot length {slot_len}')
    # definition at one end
    for d in c.get('defs', []):
        chk.claims += 1
        cw, dw = words_of(c['clue']), words_of(d)
        if not (cw[:len(dw)] == dw or cw[-len(dw):] == dw):
            chk.failures.append(f'definition "{d}" is not at either end of the clue')
    parse = c['parse']
    if parse[0] not in ('dd', 'cd'):
        chk.walk(parse)
        chk.claims += 1
        if not chk.match(parse, ans):
            chk.failures.append(f'wordplay does not produce {ans}')
    return chk


def kinds(node, out=None):
    out = set() if out is None else out
    out.add(node[0])
    for ch in node[1:]:
        if isinstance(ch, list):
            kinds(ch, out)
    return out


def main(path='clues.json', grid_path='grid_final.txt'):
    from grid import parse as gparse, lights
    rows = gparse(open(grid_path).read())
    slot_len = {f'{n}{d}': len(cells) for n, d, cells in lights(rows)}
    slot_ans = {f'{n}{d}': ''.join(rows[r][c] for r, c in cells) for n, d, cells in lights(rows)}
    clues = json.load(open(path))
    total_claims = total_fail = 0
    bad = 0
    for c in clues:
        chk = check_clue(c, slot_len.get(c['slot']))
        if slot_ans.get(c['slot']) != letters(c['answer']):
            chk.failures.append(f'grid has {slot_ans.get(c["slot"])} at {c["slot"]}')
        total_claims += chk.claims
        total_fail += len(chk.failures)
        status = 'ok ' if not chk.failures else 'BAD'
        bad += bool(chk.failures)
        print(f'{status} {c["slot"]:>4} {c["answer"]:<10} {c["clue"]} ({c["enum"]})')
        for f in chk.failures:
            print(f'       x {f}')
    print(f'\n{len(clues)} clues, {bad} with failures; '
          f'{total_fail} failed of {total_claims} checkable claims')
    return bad


if __name__ == '__main__':
    sys.exit(1 if main(*sys.argv[1:]) else 0)
