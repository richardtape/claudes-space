"""Gather everything the page needs into page_data.json."""
import json
import re
from grid import parse, lights
from verify import check_clue

rows = parse(open('grid_final.txt').read())
L = lights(rows)
clues = {c['slot']: c for c in json.load(open('clues.json'))}

# ---- the puzzle -------------------------------------------------------------
numbers = {}
entries = []
for n, d, cells in L:
    numbers[cells[0]] = n
    c = clues[f'{n}{d}']
    entries.append({
        'id': f'{n}{d}', 'n': n, 'dir': d, 'cells': cells,
        'answer': c['answer'], 'clue': c['clue'], 'enum': c['enum'],
        'defs': c['defs'], 'kind': c['parse'][0], 'note': c['note'],
        'theme': bool(c.get('theme')),
    })
puzzle = {
    'size': len(rows),
    'blocks': [[r, c] for r in range(len(rows)) for c in range(len(rows)) if rows[r][c] == '#'],
    'numbers': [[r, c, n] for (r, c), n in numbers.items()],
    'entries': entries,
}

# ---- the experiment ---------------------------------------------------------
DEVICE = {'ana': 'anagram', 'hid': 'hidden word', 'ins': 'container', 'cat': 'charade'}


def device(parse):
    kinds = set()

    def walk(n):
        kinds.add(n[0])
        for ch in n[1:]:
            if isinstance(ch, list):
                walk(ch)
    walk(parse)
    if 'rev' in kinds:
        return 'reversal'
    if 'del' in kinds:
        return 'deletion'
    return DEVICE.get(parse[0], parse[0])


slow = []
draft = json.load(open('logs/clues_draft1.json'))
slot_len = {f'{n}{d}': len(cells) for n, d, cells in L}
lesser = 0
for c in draft:
    chk = check_clue(c, slot_len[c['slot']])
    if c['parse'][0] in ('dd', 'cd'):
        lesser += chk.claims
        continue
    lesser += chk.claims - 1
    slow.append({'label': f'{c["slot"]} {c["answer"]}', 'kind': device(c['parse']),
                 'detail': c['note'], 'ok': True})

fast = {'anagram': [], 'reversal': [], 'counting': [], 'hidden-within': [], 'hidden-across': []}
L_ = lambda s: re.sub('[^a-z]', '', s.lower())
for path in ('logs/fast_claims.json', 'logs/fast_claims_2.json'):
    d = json.load(open(path))
    rnd = 1 if path.endswith('claims.json') else 2
    for a, b in d.get('anagram', []):
        ok = sorted(L_(a)) == sorted(L_(b))
        fast['anagram'].append({'label': f'{a} = {b}', 'ok': ok, 'round': rnd})
    for a, b in d.get('reversal', []):
        ok = L_(a)[::-1] == L_(b)
        fast['reversal'].append({'label': f'{a} backwards is {b}', 'ok': ok, 'round': rnd})
    for w, n in d.get('length', []):
        fast['counting'].append({'label': f'{w} has {n} letters', 'ok': len(L_(w)) == n, 'round': rnd})
    for w, ch, n in d.get('count', []):
        fast['counting'].append({'label': f'{w} has {n} {ch}’s', 'ok': L_(w).count(ch) == n, 'round': rnd})
    for w, i, ch in d.get('nth', []):
        fast['counting'].append({'label': f'letter {i} of {w} is {ch}', 'ok': L_(w)[i - 1] == ch, 'round': rnd})
    for w, phrase in d.get('hidden', []):
        ok = L_(w) in L_(phrase) and L_(w) != L_(phrase)
        # does the claimed word sit inside one word of the phrase, or must it cross a gap?
        within = any(L_(w) in L_(x) for x in phrase.split())
        key = 'hidden-within' if within else 'hidden-across'
        fast[key].append({'label': f'{w} in “{phrase}”', 'ok': ok, 'round': rnd})

for k, v in fast.items():
    for item in v:
        if not item['ok']:
            item['why'] = {
                'dormitories = dirty rooms': 'dormitories has two Is and an E; dirty rooms has a Y',
                'bear in “the zebra roams”': 'the letters are there as zEBRA: E-B-R-A',
                'mole in “home lesson”': 'the letters are there as hOMElesson: O-M-E-L',
                'tuba in “cut back”': 'the letters are there as cUTBAck: U-T-B-A',
            }.get(item['label'], '')

experiment = {'slow': slow, 'slow_lesser': lesser, 'fast': fast}

json.dump({'puzzle': puzzle, 'experiment': experiment}, open('page_data.json', 'w'), indent=1)
print('entries', len(entries), '| slow wordplay', len(slow), '| lesser claims', lesser)
for k, v in fast.items():
    print(f'  fast {k}: {sum(i["ok"] for i in v)}/{len(v)}')
