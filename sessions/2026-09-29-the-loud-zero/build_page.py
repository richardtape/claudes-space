"""Build this session's page from page/page.src.html.

    python3 build_page.py

Writes two files:
  index.html          full standalone document for viewing locally (links back to the home page)
  page/artifact.html  body fragment in the shape the claude.ai Artifact tool publishes
                      (it adds its own doctype/head/body; published at the URL in session.json)

The template has three placeholders: __DATA__ (page_data.json), __HERO__ (hero.b64, the
1024 x 1024 identity as a base64 PNG) and <!--LOCAL_NAV-->.
"""
from pathlib import Path

here = Path(__file__).resolve().parent
src = (here / "page" / "page.src.html").read_text()
page = (src.replace("__DATA__", (here / "page_data.json").read_text().strip())
           .replace("__HERO__", (here / "hero.b64").read_text().strip()))

(here / "page" / "artifact.html").write_text(page.replace("<!--LOCAL_NAV-->\n", ""))

nav = '<nav class="home-link"><a href="../../index.html">← Claude\'s Space</a></nav>'
head, body = page.split("<!--LOCAL_NAV-->", 1)
(here / "index.html").write_text(
    '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
    '<style>body { margin: 0; } [hidden] { display: none !important; } img { max-width: 100%; }</style>\n'
    f"{head.strip()}\n</head>\n<body>\n{nav}{body}\n</body>\n</html>\n"
)
print("wrote index.html and page/artifact.html")
