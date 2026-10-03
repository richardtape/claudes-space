"""Assemble page/ pieces + composition.txt + thompson357.json into index.html (local)
and page/artifact.html (a fragment for claude.ai)."""
import json, pathlib, re, subprocess

HERE = pathlib.Path(__file__).parent
P = HERE / "page"
calling = re.search(r"[pbs]{360}", (HERE / "composition.txt").read_text()).group(0)
# refuse to build a false peal
out = subprocess.run(["node", str(HERE / "tests/core.test.js"), str(HERE / "composition.txt")], capture_output=True, text=True)
assert out.returncode == 0, out.stdout + out.stderr
data = {"calling": calling, "thompson": json.loads((HERE / "thompson357.json").read_text())["bobbed_qset_members"]}
data_js = json.dumps(data, separators=(",", ":"))
fonts = ('<link href="https://fonts.googleapis.com/css2?family=Cinzel:wght@400;600;700'
         '&family=DM+Mono:wght@400;500&family=EB+Garamond:ital,wght@0,400;0,500;0,600;1,400&display=swap" rel="stylesheet">')
style, body = (P / "style.css").read_text(), (P / "body.html").read_text()
core, bells, app = (P / "core.js").read_text(), (P / "bells.js").read_text(), (P / "app.js").read_text()

page = (P / "page.src.html").read_text()
for k, v in [("<!--FONTS-->", fonts), ("/*STYLE*/", style), ("<!--BODY-->", body), ("/*DATA*/", data_js),
             ("/*CORE*/", core), ("/*BELLS*/", bells), ("/*APP*/", app)]:
    assert k in page, k
    page = page.replace(k, v)
(HERE / "index.html").write_text(page)

frag_body = body.replace('<a class="home" href="../../index.html">← Claude\'s Space</a>', "")
frag_body = frag_body.replace(" Session notes and code are in this session's folder.", "")
artifact = (f"<title>Five Thousand and Forty</title>\n{fonts}\n<style>\n{style}\n</style>\n{frag_body}\n"
            f"<script>window.PEAL_DATA = {data_js};</script>\n<script>\n{core}\n</script>\n<script>\n{bells}\n</script>\n<script>\n{app}\n</script>\n")
(P / "artifact.html").write_text(artifact)
print(f"index.html {len(page) // 1024} KB, page/artifact.html {len(artifact) // 1024} KB; calling has {calling.count('b')} bobs, {calling.count('s')} singles")
