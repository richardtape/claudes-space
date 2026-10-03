from ringing import *

rows, lh = touch('ppppp')
print('plain course length', len(rows), 'comes round:', lh == ROUNDS)
print('plain course lead heads:', [fmt(touch('p' * k)[1]) for k in range(6)])
print('first lead:', ' '.join(fmt(r) for r in lead(ROUNDS)[0]))
print('true?', len(set(rows)) == len(rows))
# treble path
print('treble positions in lead:', [r.index(1) + 1 for r in lead(ROUNDS)[0]])
print('2nd positions in lead:', [r.index(2) + 1 for r in lead(ROUNDS)[0]])
for c in 'pbs':
    rs, nlh = lead(ROUNDS, c)
    print(c, 'lead head after', fmt(nlh), 'parity', parity(nlh), 'last two rows', fmt(rs[-1]), fmt(rs[-2]))
