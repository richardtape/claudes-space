"""Assemble index.html from page/template.html, page/app.js and page_data.json."""
import base64
import json
import subprocess

subprocess.run(['~/Developer/claudes-space/.venv/bin/python', 'export.py'], check=True,
               stdout=subprocess.DEVNULL)
data = json.load(open('page_data.json'))
b64 = base64.b64encode(json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode()).decode()
html = open('page/template.html').read()
js = open('page/app.js').read()
assert '</script' not in js
html = html.replace('/*DATA*/', b64).replace('/*SCRIPT*/', js)
open('index.html', 'w').write(html)
print('index.html', len(html) // 1024, 'KB')
