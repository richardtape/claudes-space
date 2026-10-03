"""In a Holt-style peal (singles three leads apart), are the out-of-course leads a B-block backwards?"""
import re, sys
from ringing import *
c = re.search(r'[pbs]{360}', open(sys.argv[1]).read()).group(0)
rows, end = touch(c)
assert len(set(rows)) == 5040 and end == ROUNDS
lhs = [ROUNDS]
for k in c: lhs.append(lead(lhs[-1], k)[1])
s = [i for i, k in enumerate(c) if k == 's']
print('singles at leads', [i + 1 for i in s], ' calls in the out-of-course stretch:', c[s[0] + 1:s[1] + 1])
ooc = [i for i in range(360) if parity(lhs[i]) == 1]
print('out-of-course leads:', [i + 1 for i in ooc])
ooc_rows = [r for i in ooc for r in lead(lhs[i], c[i])[0]]
# find the B-block (three bob leads that come round) whose rows, reversed, are these
target = list(reversed(ooc_rows))
x = target[0]
bb = touch('bbb', x)[0]
print('B-block from', fmt(x), 'comes round:', touch('bbb', x)[1] == x, ' rows equal the out-of-course rows reversed:', bb == target)
