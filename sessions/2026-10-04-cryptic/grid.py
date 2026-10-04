"""Grid model: parse a text grid, find lights, number them, report stats.

Grid text: '#' block, '.' empty white, a letter = fixed white."""


def parse(text):
    rows = [r.replace(' ', '') for r in text.strip().splitlines()]
    assert all(len(r) == len(rows[0]) for r in rows), [len(r) for r in rows]
    return rows


def lights(rows):
    """Return list of (number, direction, [(r,c),...]) in clue-number order."""
    R, C = len(rows), len(rows[0])
    white = lambda r, c: 0 <= r < R and 0 <= c < C and rows[r][c] != '#'
    out, n = [], 0
    for r in range(R):
        for c in range(C):
            if not white(r, c):
                continue
            starts = []
            if not white(r, c - 1) and white(r, c + 1):
                starts.append('A')
            if not white(r - 1, c) and white(r + 1, c):
                starts.append('D')
            if starts:
                n += 1
                for d in starts:
                    dr, dc = (0, 1) if d == 'A' else (1, 0)
                    cells, rr, cc = [], r, c
                    while white(rr, cc):
                        cells.append((rr, cc))
                        rr, cc = rr + dr, cc + dc
                    out.append((n, d, cells))
    return out


def report(rows):
    R, C = len(rows), len(rows[0])
    L = lights(rows)
    use = {}
    for n, d, cells in L:
        for rc in cells:
            use[rc] = use.get(rc, 0) + 1
    problems = []
    # symmetry
    for r in range(R):
        for c in range(C):
            if (rows[r][c] == '#') != (rows[R - 1 - r][C - 1 - c] == '#'):
                problems.append(f'asymmetric at {r},{c}')
    # every white cell in some light; no 1- or 2-letter lights
    for r in range(R):
        for c in range(C):
            if rows[r][c] != '#' and (r, c) not in use:
                problems.append(f'orphan cell {r},{c}')
    lines = []
    for n, d, cells in L:
        k = len(cells)
        checked = sum(use[rc] == 2 for rc in cells)
        word = ''.join(rows[r][c] for r, c in cells)
        flag = ''
        if k < 3:
            problems.append(f'{n}{d} too short')
        if checked * 2 < k - 1:
            flag = '  <-- under-checked'
            problems.append(f'{n}{d} under-checked {checked}/{k}')
        # no two adjacent unchecked cells
        for a, b in zip(cells, cells[1:]):
            if use[a] == 1 and use[b] == 1:
                problems.append(f'{n}{d} has adjacent unches')
                break
        lines.append(f'{n:>3}{d} len {k:>2} checked {checked}/{k}  {word}{flag}')
    # connectivity
    whites = [(r, c) for r in range(R) for c in range(C) if rows[r][c] != '#']
    seen, stack = {whites[0]}, [whites[0]]
    while stack:
        r, c = stack.pop()
        for dr, dc in ((0, 1), (1, 0), (0, -1), (-1, 0)):
            q = (r + dr, c + dc)
            if q in use and q not in seen and rows[q[0]][q[1]] != '#':
                seen.add(q)
                stack.append(q)
    if len(seen) != len(whites):
        problems.append('grid not connected')
    return L, lines, problems


if __name__ == '__main__':
    import sys
    rows = parse(open(sys.argv[1]).read())
    L, lines, problems = report(rows)
    print('\n'.join(lines))
    print(f'{len(L)} lights;', 'problems:', problems or 'none')
