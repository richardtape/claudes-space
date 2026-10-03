#!/usr/bin/env python3
"""Build index.html (standalone, works from file://) and page/artifact.html (fragment to
publish on claude.ai) from page/page.src.html + page/core.js + page/app.js + page_data.json.
Standard library only.  Edit the sources, never the built files."""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "page/page.src.html").read_text()
core = (HERE / "page/core.js").read_text()
app = (HERE / "page/app.js").read_text()
data = (HERE / "page_data.json").read_text()
for name, text in (("core.js", core), ("app.js", app), ("page_data.json", data)):
    assert "</script" not in text.lower(), f"{name} contains </script"

page = src.replace("/*CORE*/", core).replace("/*DATA*/", data).replace("/*APP*/", app)
local = page.replace("<!--LOCAL-ONLY-->", "").replace("<!--/LOCAL-ONLY-->", "")
(HERE / "index.html").write_text(local)

frag = re.sub(r"<!--LOCAL-ONLY-->.*?<!--/LOCAL-ONLY-->\n?", "", page, flags=re.S)
for pat in (r"<!doctype html>\n", r'<html lang="en">\n', r"<head>\n", r'<meta charset="utf-8">\n',
            r'<meta name="viewport"[^>]*>\n', r"</head>\n", r"<body>\n", r"</body>\n", r"</html>\n?"):
    frag, n = re.subn(pat, "", frag, count=1)
    assert n == 1, pat
(HERE / "page/artifact.html").write_text(frag)
print(f"index.html {len(local) / 1e3:.0f} kB, page/artifact.html {len(frag) / 1e3:.0f} kB")
