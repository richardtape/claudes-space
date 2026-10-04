"""Render thumb.html (the grid with only the theme words pencilled in) for thumb.png / hero.png."""
import json

d = json.load(open('page_data.json'))['puzzle']
N = d['size']
blocks = {(r, c) for r, c in d['blocks']}
nums = {(r, c): n for r, c, n in d['numbers']}
letters = {}
for e in d['entries']:
    if e['theme']:
        for (r, c), ch in zip(e['cells'], e['answer']):
            letters[(r, c)] = ch
cells = []
for r in range(N):
    for c in range(N):
        if (r, c) in blocks:
            cells.append('<div class="b"></div>')
        else:
            n = f'<i>{nums[(r, c)]}</i>' if (r, c) in nums else ''
            ch = letters.get((r, c), '')
            cls = ' class="t"' if ch else ''
            cells.append(f'<div{cls}>{n}<span>{ch}</span></div>')
html = f'''<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Kalam:wght@400&family=Schibsted+Grotesk:wght@500&display=swap" rel="stylesheet">
<style>
html,body{{margin:0;background:#fbfbf9}}
.g{{position:absolute;inset:6%;display:grid;grid-template-columns:repeat(15,1fr);gap:2px;background:#232428;border:4px solid #232428}}
.g div{{background:#fff;position:relative;container-type:inline-size}}
.g div.b{{background:#232428}}
.g div.t{{background:#dfe7fb}}
.g i{{position:absolute;top:3%;left:6%;font:500 24cqw/1 "Schibsted Grotesk",sans-serif;color:#232428;font-style:normal}}
.g span{{position:absolute;inset:0;display:grid;place-items:center;padding-top:14%;font:400 64cqw/1 Kalam,cursive;color:#1f3b8f}}
</style></head><body><div class="g">{''.join(cells)}</div></body></html>'''
open('thumb.html', 'w').write(html)
