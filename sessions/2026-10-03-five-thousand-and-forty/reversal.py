"""Claim: every out-of-course bob lead is an in-course bob lead rung backwards,
and the bob lead's first 13 changes read the same in both directions."""
from itertools import permutations
from ringing import *

pn = ['3', '1', '7', '1', '7', '1', '7', '1', '7', '1', '7', '1', '3', '1']
print('bob lead changes 1-13 palindromic:', pn[:13] == pn[:13][::-1])
TL = [r for r in permutations(ROUNDS) if r[0] == 1]
even_bob = {}
for x in TL:
    if parity(x) == 0:
        rows = lead(x, 'b')[0]
        even_bob[tuple(rows[::-1])] = x
ok = 0; plain_ok = 0
for g in TL:
    if parity(g) == 1:
        if tuple(lead(g, 'b')[0]) in even_bob: ok += 1
        # does any odd *plain* lead equal an in-course plain lead reversed?
print('out-of-course bob leads that are an in-course bob lead reversed:', ok, 'of 360')
even_plain = {tuple(lead(x, 'p')[0][::-1]) for x in TL if parity(x) == 0}
print('out-of-course plain leads that are an in-course plain lead reversed:',
      sum(tuple(lead(g, 'p')[0]) in even_plain for g in TL if parity(g) == 1))
