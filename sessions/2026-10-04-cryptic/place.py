"""place.py GRID OUT SLOT=WORD ... : write a copy of GRID with words placed."""
import sys
from grid import parse, lights

rows = [list(r) for r in parse(open(sys.argv[1]).read())]
L = {f'{n}{d}': cells for n, d, cells in lights(rows)}
for arg in sys.argv[3:]:
    slot, word = arg.split('=')
    cells = L[slot]
    assert len(cells) == len(word), (slot, word)
    for (r, c), ch in zip(cells, word.upper()):
        assert rows[r][c] in '.' + ch, f'{slot}={word} clashes at {r},{c} ({rows[r][c]})'
        rows[r][c] = ch
open(sys.argv[2], 'w').write('\n'.join(' '.join(r) for r in rows) + '\n')
