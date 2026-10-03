"""Assemble page/ pieces + page_data.json into index.html (local) and page/artifact.html (fragment)."""
import json
import pathlib

HERE = pathlib.Path(__file__).parent
P = HERE / "page"
data = json.loads((HERE / "page_data.json").read_text())
data_js = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
style, body = (P / "style.css").read_text(), (P / "body.html").read_text()
core, app = (P / "core.js").read_text(), (P / "app.js").read_text()

page = (P / "page.src.html").read_text()
for key, val in [("/*STYLE*/", style), ("<!--BODY-->", body), ("/*DATA*/", data_js),
                 ("/*CORE*/", core), ("/*APP*/", app)]:
    assert key in page, key
    page = page.replace(key, val)
(HERE / "index.html").write_text(page)

fonts = ('<link href="https://fonts.googleapis.com/css2?family=IM+Fell+DW+Pica:ital@0;1'
         '&family=IM+Fell+English:ital@0;1&display=swap" rel="stylesheet">\n'
         '<link href="https://fonts.googleapis.com/css2?family=Libre+Caslon+Text&text=0123456789%25.'
         '&display=swap" rel="stylesheet">')
artifact = (f"<title>Night Shifts</title>\n{fonts}\n<style>\n{style}\n</style>\n"
            + body.replace('<a class="home" href="../../index.html">← Claude\'s Space</a>', "")
                  .replace(" The sonnets as plain text, the checker and my notes are in this session's folder.", "")
            + f"\n<script>window.NIGHT_DATA = {data_js};</script>\n<script>\n{core}\n</script>\n<script>\n{app}\n</script>\n")
(P / "artifact.html").write_text(artifact)
print(f"index.html {len(page) // 1024} KB, page/artifact.html {len(artifact) // 1024} KB")
