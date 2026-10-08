"""Assemble index.html from page/template.html and page/data.js (data inlined, so the
page works from file:// with no fetches)."""
from pathlib import Path

HERE = Path(__file__).resolve().parent
tpl = (HERE / "template.html").read_text(encoding="utf-8")
data = (HERE / "data.js").read_text(encoding="utf-8")
assert tpl.count("/*DATA*/") == 1
out = tpl.replace("/*DATA*/", data.replace("</", "<\\/"))
(HERE.parent / "index.html").write_text(out, encoding="utf-8")
print(f"index.html: {len(out) / 1024:.0f} KB")
