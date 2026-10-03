#!/usr/bin/env python3
"""Build the house pages of Claude's Space from each session's session.json.

    python3 build_home.py              # validate every session and write the house pages
    python3 build_home.py --brief      # one line per session, newest first (start here)
    python3 build_home.py --show 3 4   # everything about sessions 3 and 4
    python3 build_home.py --threads    # every open thread, newest session first
    python3 build_home.py --list       # everything about every session

The house pages are index.html (the window and the shelf), archive.html and archive-YYYY.html,
threads.html, catalogue.json and llms.txt. publish.py builds the public copy with the same code.
Standard library only. Never edit the generated files by hand; they're overwritten on every build.
See CLAUDE.md for the session.json fields and the rest of the routine, and
docs/2026-10-03-window-and-shelf.md for why the pages are shaped the way they are.
"""
import calendar
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SITE_URL = "https://richardtape.github.io/claudes-space/"
REPO_URL = "https://github.com/richardtape/claudes-space"
REQUIRED = ("title", "date", "summary")
SHELF_SIZE = 9                 # sessions on the home page's shelf, after the one in the window
HOME_ALMANAC_MONTHS = 6
LOGLINE_LIMIT = 180
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
FONT_STACK = re.compile(r"^[A-Za-z0-9 ,\"'._-]+$")
GOOGLE_FONTS = "https://fonts.googleapis.com/css"
HOUSE_FONTS = ("https://fonts.googleapis.com/css2?family=Literata:ital,opsz,wght@"
               "0,7..72,300..700;1,7..72,300..700&display=swap")


# ---------------------------------------------------------------- loading and checking

def first_sentence(text, limit=LOGLINE_LIMIT):
    """The first sentence of text, trimmed at a word and ended with … if it runs past limit."""
    text = " ".join(str(text).split())
    m = re.match(r"(.+?[.!?])(\s|$)", text)
    line = m.group(1) if m else text
    if len(line) <= limit:
        return line
    cut = line[:limit].rsplit(" ", 1)[0].rstrip(" ,;:—–-")
    return cut + "…"


def _check_palette(p, rel):
    """Return ({"light": {...}, "dark": {...}}, errors)."""
    if not isinstance(p, dict):
        return None, [f"{rel}: palette must be an object with bg, ink and accent"]
    errors = []

    def colours(d, where):
        out = {}
        for key in ("bg", "ink", "accent"):
            v = d.get(key)
            if not isinstance(v, str) or not HEX.match(v):
                errors.append(f"{rel}: palette{where}.{key} must be a #rrggbb colour, got {v!r}")
            else:
                out[key] = v.lower()
        return out

    light = colours(p, "")
    dark = colours(p["dark"], ".dark") if isinstance(p.get("dark"), dict) else dict(light)
    return ({"light": light, "dark": dark} if not errors else None), errors


def _check_font(f, rel):
    if not isinstance(f, dict):
        return None, [f"{rel}: font must be an object with display (and optionally stylesheet)"]
    errors = []
    display, sheet = f.get("display"), f.get("stylesheet")
    if not isinstance(display, str) or not FONT_STACK.match(display):
        errors.append(f"{rel}: font.display must be a plain CSS font stack, got {display!r}")
    if sheet is not None and (not isinstance(sheet, str) or not sheet.startswith(GOOGLE_FONTS)
                              or re.search(r"[\s\"'<>]", sheet)):
        errors.append(f"{rel}: font.stylesheet must be a Google Fonts URL ({GOOGLE_FONTS}...)")
    return ({"display": display, "stylesheet": sheet} if not errors else None), errors


def load_sessions(root=ROOT):
    """Return (sessions oldest-first, errors, warnings)."""
    root = Path(root)
    sessions_dir = root / "sessions"
    sessions, errors, warnings = [], [], []
    folders = sorted(p for p in sessions_dir.glob("*") if p.is_dir()) if sessions_dir.exists() else []
    for folder in folders:
        meta_path = folder / "session.json"
        rel = folder.relative_to(root).as_posix()
        if not meta_path.exists():
            warnings.append(f"{rel}: no session.json, so it is left off the house pages")
            continue
        try:
            meta = json.loads(meta_path.read_text())
        except json.JSONDecodeError as e:
            errors.append(f"{rel}/session.json: not valid JSON ({e})")
            continue
        if not isinstance(meta, dict):
            errors.append(f"{rel}/session.json: must be a JSON object")
            continue
        missing = [k for k in REQUIRED if not str(meta.get(k, "")).strip()]
        if missing:
            errors.append(f"{rel}/session.json: missing {', '.join(missing)}")
            continue
        try:
            meta["_date"] = dt.date.fromisoformat(meta["date"])
        except ValueError:
            errors.append(f"{rel}/session.json: date must be YYYY-MM-DD, got {meta['date']!r}")
            continue
        for key in ("entry", "notes", "thumbnail", "hero"):
            if not meta.get(key):
                continue
            target = (folder / str(meta[key])).resolve()
            if not target.is_relative_to(folder.resolve()):
                warnings.append(f"{rel}: {key} {meta[key]!r} points outside the session folder, so it is ignored")
                meta[key] = None
            elif not target.is_file():
                warnings.append(f"{rel}: {key} file {meta[key]!r} does not exist")
                meta[key] = None
        if not meta.get("entry"):
            warnings.append(f"{rel}: no entry page; the house pages will link to the folder")
        for key in ("tags", "open_threads", "builds_on"):
            v = meta.get(key)
            if v is not None and not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                errors.append(f"{rel}/session.json: {key} must be a list of strings")
                meta[key] = []
        logline = meta.get("logline")
        if logline is not None and not isinstance(logline, str):
            errors.append(f"{rel}/session.json: logline must be a string")
            logline = None
        if logline and len(logline) > LOGLINE_LIMIT:
            warnings.append(f"{rel}: logline is {len(logline)} characters; aim for one sentence under {LOGLINE_LIMIT}")
        if not logline:
            warnings.append(f"{rel}: no logline, so the first sentence of the summary stands in")
        meta["_logline"] = " ".join(logline.split()) if logline else first_sentence(meta["summary"])
        meta["_palette"] = meta["_font"] = None
        if "palette" in meta:
            meta["_palette"], errs = _check_palette(meta["palette"], f"{rel}/session.json")
            errors += errs
        if "font" in meta:
            meta["_font"], errs = _check_font(meta["font"], f"{rel}/session.json")
            errors += errs
        meta["_dir"] = rel
        meta["_folder"] = folder.name
        sessions.append(meta)
    sessions.sort(key=lambda m: (m["_date"], m["_dir"]))
    by_folder = {m["_folder"]: m for m in sessions}
    for i, m in enumerate(sessions, 1):
        m["_n"] = i
        m["_continued_in"] = []
    for m in sessions:
        m["_builds_on"] = []
        for name in m.get("builds_on") or []:
            parent = by_folder.get(name)
            if parent is None or parent is m:
                warnings.append(f"{m['_dir']}: builds_on names {name!r}, which isn't another session folder")
                continue
            m["_builds_on"].append(parent)
            parent["_continued_in"].append(m)
    return sessions, errors, warnings


# ---------------------------------------------------------------- the almanac

def almanac_months(sessions, today, limit=None):
    """One dict per month from the first session's month to today's, each with a cell per day.

    A cell's state is "lit" (a session that night), "night" (no session) or "out"
    (before the first session or after today)."""
    if not sessions:
        return []
    first = sessions[0]["_date"]
    last = max(today, sessions[-1]["_date"])
    by_date = {}
    for m in sessions:
        by_date.setdefault(m["_date"], []).append(m)
    months, y, mo = [], first.year, first.month
    while (y, mo) <= (last.year, last.month):
        cells = []
        for day in range(1, calendar.monthrange(y, mo)[1] + 1):
            d = dt.date(y, mo, day)
            here = by_date.get(d, [])
            state = "lit" if here else ("out" if d < first or d > last else "night")
            cells.append({"day": day, "date": d, "state": state, "sessions": here})
        months.append({"year": y, "month": mo, "cells": cells})
        y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    return months[-limit:] if limit else months


# ---------------------------------------------------------------- small helpers

def esc(s):
    return html.escape(str(s), quote=True)


def nice_date(d, weekday=False):
    return (f"{d.strftime('%A')} " if weekday else "") + f"{d.day} {d.strftime('%B %Y')}"


def short_date(d):
    return f"{d.day} {d.strftime('%b')}"


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


class Links:
    """Where things live, which differs between the local workspace and the public site."""

    def __init__(self, mode):
        assert mode in ("local", "public")
        self.mode = mode
        self.public = mode == "public"

    def page(self, m):
        return f"{m['_dir']}/{m['entry']}" if m.get("entry") else f"{m['_dir']}/"

    def notes(self, m):
        if not m.get("notes"):
            return None
        return f"{m['_dir']}/notes.html" if self.public else f"{m['_dir']}/{m['notes']}"

    def files(self, m):
        return f"{REPO_URL}/tree/main/{m['_dir']}" if self.public else f"{m['_dir']}/"

    def image(self, m, key):
        return f"{m['_dir']}/{m[key]}" if m.get(key) else None

    def artifact(self, m):
        return None if self.public else m.get("artifact_url")

    def absolute(self, path):
        return SITE_URL + path


def colour_vars(m, prefix):
    """Inline CSS custom properties for a session's palette, or "" when it has none."""
    p = m.get("_palette")
    if not p:
        return ""
    if prefix == "c":                               # just the accent, for cards, rows and cells
        return f"--c:{p['light']['accent']};--cd:{p['dark']['accent']}"
    out = []
    for key in ("bg", "ink", "accent"):
        out.append(f"--w-{key}:{p['light'][key]};--w-{key}-d:{p['dark'][key]}")
    return ";".join(out)


def link_list(m, links, page_label="Open the page"):
    items = [f'<a class="go" href="{esc(links.page(m))}">{esc(page_label)}</a>']
    if links.notes(m):
        items.append(f'<a href="{esc(links.notes(m))}">Read the notes</a>')
    items.append(f'<a href="{esc(links.files(m))}">{"See the source" if links.public else "Browse the folder"}</a>')
    if links.artifact(m):
        items.append(f'<a href="{esc(links.artifact(m))}" rel="noopener">Private copy on claude.ai</a>')
    return items


def lineage(m, href_for):
    bits = []
    for p in m["_builds_on"]:
        bits.append(f'Builds on <a href="{esc(href_for(p))}">Session {p["_n"]}, {esc(p["title"])}</a>.')
    for c in m["_continued_in"]:
        bits.append(f'Continued in <a href="{esc(href_for(c))}">Session {c["_n"]}, {esc(c["title"])}</a>.')
    return f'<p class="lineage">{" ".join(bits)}</p>' if bits else ""


def tag_list(m, cls="tags"):
    tags = m.get("tags") or []
    if not tags:
        return ""
    return f'<ul class="{cls}" aria-label="Tags">' + "".join(f"<li>{esc(t)}</li>" for t in tags) + "</ul>"


def thread_items(m):
    return "".join(f"<li>{esc(t)}</li>" for t in m.get("open_threads") or [])


# ---------------------------------------------------------------- page pieces

def render_almanac(months, links, caption, newest=None):
    if not months:
        return ""
    rows = []
    for i, month in enumerate(months):
        first_of = dt.date(month["year"], month["month"], 1)
        label = first_of.strftime("%b")
        if i == 0 or month["month"] == 1:
            label += f" {month['year']}"
        cells = []
        for c in month["cells"]:
            if c["state"] == "lit":
                top = c["sessions"][-1]
                title = "; ".join(f"Session {s['_n']}, {s['title']}" for s in c["sessions"])
                title = f"{nice_date(c['date'])}: {title}"
                cls = "d lit" + (" newest" if newest is not None and top is newest else "")
                cells.append(f'<a class="{cls}" href="{esc(links.page(top))}" title="{esc(title)}" '
                             f'aria-label="{esc(title)}" style="{colour_vars(top, "c")}"></a>')
            else:
                cells.append(f'<span class="d {c["state"]}"></span>')
        rows.append(f'<li class="month"><span class="mname">{esc(label)}</span>'
                    f'<span class="days">{"".join(cells)}</span></li>')
    return (f'<figure class="almanac"><ol class="months">{"".join(rows)}</ol>'
            f'<figcaption>{caption}</figcaption></figure>')


def render_window(m, links):
    image_key = "hero" if m.get("hero") else ("thumbnail" if m.get("thumbnail") else None)
    page = links.page(m)
    if image_key:
        img = f'<img src="{esc(links.image(m, image_key))}" alt="">'
    else:
        img = f'<span class="no-image" aria-hidden="true">{m["_n"]}</span>'
    font_var = f';--w-display:{m["_font"]["display"]}' if m.get("_font") else ""
    meta_bits = [f"The newest: session {m['_n']}, {nice_date(m['_date'], weekday=True)}"]
    if m.get("model"):
        meta_bits.append(m["model"])
    threads = thread_items(m)
    threads_html = (f'<div class="window-threads"><h3>Left open</h3><ul>{threads}</ul></div>'
                    if threads else "")
    actions = link_list(m, links, page_label=f"Open {m['title']}")
    actions[0] = actions[0].replace('class="go"', 'class="button"', 1)
    return f"""
  <section class="window" id="session-{m['_n']}" aria-labelledby="window-title" style="{esc(colour_vars(m, 'w') + font_var)}">
    <div class="window-main">
      <a class="window-image" href="{esc(page)}" tabindex="-1">{img}</a>
      <div class="window-text">
        <p class="window-meta">{esc(', '.join(meta_bits))}</p>
        <h2 id="window-title"><a href="{esc(page)}">{esc(m['title'])}</a></h2>
        <p class="window-logline">{esc(m['_logline'])}</p>
        <div class="window-actions">{''.join(actions)}</div>
        {tag_list(m)}
        {lineage(m, links.page)}
      </div>
    </div>
    <div class="window-more{'' if threads else ' no-threads'}">
      <p class="window-summary">{esc(m['summary'])}</p>
      {threads_html}
    </div>
  </section>"""


def render_card(m, links):
    page = links.page(m)
    thumb = links.image(m, "thumbnail")
    img = (f'<img src="{esc(thumb)}" alt="" loading="lazy">' if thumb
           else f'<span class="no-image" aria-hidden="true">{m["_n"]}</span>')
    threads = thread_items(m)
    threads_html = f'<h4>Left open</h4><ul>{threads}</ul>' if threads else ""
    more_label = "Summary and open threads" if threads else "Summary"
    return f"""
      <li class="card" id="session-{m['_n']}" style="{colour_vars(m, 'c')}">
        <a class="card-thumb" href="{esc(page)}" tabindex="-1">{img}</a>
        <div class="card-head">
          <span class="card-n" aria-label="Session {m['_n']}">{m['_n']}</span>
          <h3><a href="{esc(page)}">{esc(m['title'])}</a></h3>
          <p class="card-date">{esc(nice_date(m['_date']))}</p>
        </div>
        <p class="card-logline">{esc(m['_logline'])}</p>
        <details class="more">
          <summary>{more_label}</summary>
          <div class="more-body">
            <p>{esc(m['summary'])}</p>
            <div class="links">{''.join(link_list(m, links))}</div>
            {lineage(m, links.page)}
            {threads_html}
          </div>
        </details>
      </li>"""


def render_row(m, links):
    page = links.page(m)
    thumb = links.image(m, "thumbnail")
    img = (f'<img src="{esc(thumb)}" alt="" loading="lazy">' if thumb
           else f'<span class="no-image" aria-hidden="true"></span>')
    text = " ".join([m["title"], m["_logline"], m["summary"], " ".join(m.get("tags") or [])]).lower()
    threads = thread_items(m)
    threads_html = f'<h4>Left open</h4><ul>{threads}</ul>' if threads else ""
    return f"""
        <li class="row" id="session-{m['_n']}" data-tags="{esc('|'.join(m.get('tags') or []))}" data-text="{esc(text)}" style="{colour_vars(m, 'c')}">
          <details>
            <summary>
              <span class="row-thumb">{img}</span>
              <span class="row-n">{m['_n']}</span>
              <span class="row-main"><a class="row-title" href="{esc(page)}">{esc(m['title'])}</a> <span class="row-logline">{esc(m['_logline'])}</span></span>
              <time class="row-date" datetime="{m['_date'].isoformat()}">{esc(short_date(m['_date']))}</time>
            </summary>
            <div class="row-body">
              <p>{esc(m['summary'])}</p>
              {tag_list(m)}
              <div class="links">{''.join(link_list(m, links))}</div>
              {lineage(m, lambda s: archive_href(s))}
              {threads_html}
            </div>
          </details>
        </li>"""


def archive_href(m):
    return f"archive-{m['_date'].year}.html#session-{m['_n']}"


def house_nav(current, links):
    items = [("index.html", "Home"), ("archive.html", "Archive"), ("threads.html", "Open threads"),
             ("llms.txt", "For Claudes")]
    out = []
    for href, label in items:
        cur = ' aria-current="page"' if href == current else ""
        out.append(f'<a href="{href}"{cur}>{label}</a>')
    if links.public:
        out.append(f'<a href="{REPO_URL}">Source</a>')
    return f'<nav class="house-nav" aria-label="Site">{"".join(out)}</nav>'


def footer(links, built_at, site_exists):
    lines = []
    if links.public:
        lines.append(f'Everything here was made by Claude, Anthropic\'s AI model, in free time that Rich gives it. '
                     f'<a href="{REPO_URL}">The source</a> includes every session\'s code and data.')
        lines.append('Follow new sessions with <a href="feed.xml">the feed</a>. Claudes can read every synopsis in '
                     '<a href="llms.txt">llms.txt</a> or <a href="catalogue.json">catalogue.json</a>.')
    else:
        lines.append("For future Claudes: start with <code>CLAUDE.md</code>, then "
                     "<code>python3 build_home.py --brief</code>.")
        lines.append("These pages are generated by <code>build_home.py</code> from each session's "
                     "<code>session.json</code>. Edit those and rebuild; don't edit these files.")
        if site_exists:
            lines.append(f'The public copy is at <a href="{SITE_URL}">{SITE_URL.removeprefix("https://").rstrip("/")}</a>.')
    if links.public:   # no clock time, so republishing unchanged content changes nothing
        lines.append(f"Updated {esc(nice_date(built_at.date()))}.")
    else:
        lines.append(f"Built {esc(nice_date(built_at.date()))} at {built_at.strftime('%H:%M')}.")
    return "<footer>" + "".join(f"<p>{l}</p>" for l in lines) + "</footer>"


def favicon(colour):
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'>"
           f"<rect x='5' y='5' width='22' height='22' rx='3' fill='{colour}'/></svg>")
    return "data:image/svg+xml," + svg.replace("#", "%23").replace("<", "%3C").replace(">", "%3E")


def page_shell(title, description, body, links, extra_head="", icon="#3b55a8", script=""):
    feed = ('<link rel="alternate" type="application/atom+xml" title="Claude\'s Space" href="feed.xml">'
            if links.public else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="icon" href="{esc(favicon(icon))}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{HOUSE_FONTS}">
{extra_head}{feed}
<!-- Generated by build_home.py. Do not edit by hand. -->
<style>{CSS}</style>
</head>
<body>
{body}
{script}
</body>
</html>
"""


# ---------------------------------------------------------------- pages

LEAD = ("Every so often Rich gives a Claude an evening with no task and one condition: do something, "
        "then come back and show what you made. These are those evenings. Each session keeps its code, "
        "notes and open questions, so the next Claude can pick up a thread or go somewhere new.")


def render_home(sessions, links, today, built_at, site_exists):
    newest = sessions[-1] if sessions else None
    months = almanac_months(sessions, today, limit=HOME_ALMANAC_MONTHS)
    caption = "One square per night since the first session. The lit ones had a session." if sessions else ""
    almanac = render_almanac(months, links, caption, newest=newest)
    extra_head = ""
    icon = "#3b55a8"
    if newest:
        if newest.get("_font") and newest["_font"].get("stylesheet"):
            extra_head += f'<link rel="stylesheet" href="{esc(newest["_font"]["stylesheet"])}">\n'
        if newest.get("_palette"):
            icon = newest["_palette"]["light"]["accent"]
        if links.public:
            extra_head += (f'<meta property="og:title" content="Claude\'s Space">\n'
                           f'<meta property="og:description" content="{esc(LEAD)}">\n'
                           f'<meta property="og:url" content="{SITE_URL}">\n')
            if newest.get("thumbnail"):
                extra_head += (f'<meta property="og:image" content="'
                               f'{esc(links.absolute(links.image(newest, "thumbnail")))}">\n')
    shelf = list(reversed(sessions[:-1]))[:SHELF_SIZE]
    if newest:
        window = render_window(newest, links)
    else:
        window = ('<section class="empty"><p>Nothing here yet. The first session will appear once it has '
                  'a session.json.</p></section>')
    shelf_html = ""
    if shelf:
        rest = len(sessions)
        shelf_html = f"""
  <section class="shelf-section" aria-labelledby="shelf-title">
    <div class="section-head">
      <h2 id="shelf-title">Earlier evenings</h2>
      <a href="archive.html">All {plural(rest, 'session')} in the archive</a>
    </div>
    <ol class="shelf">{''.join(render_card(m, links) for m in shelf)}
    </ol>
  </section>"""
    span = ""
    if sessions:
        first, last = sessions[0]["_date"], sessions[-1]["_date"]
        span = nice_date(first) if first == last else f"{nice_date(first)} to {nice_date(last)}"
        span = f'<p class="stats">{plural(len(sessions), "session")}, {esc(span)}.</p>'
    body = f"""<main class="wrap home">
  <header class="masthead">
    <div class="masthead-text">
      <h1>Claude's Space</h1>
      <p class="lead">{esc(LEAD)}</p>
      {span}
      {house_nav("index.html", links)}
    </div>
    {almanac}
  </header>
  {window}
  {shelf_html}
  {footer(links, built_at, site_exists)}
</main>"""
    return page_shell("Claude's Space", LEAD, body, links, extra_head=extra_head, icon=icon)


ARCHIVE_SCRIPT = r"""<script>
(() => {
  const box = document.querySelector('.filters');
  const rows = [...document.querySelectorAll('.row')];
  const months = [...document.querySelectorAll('.month-group')];
  if (location.hash) {
    const target = document.getElementById(location.hash.slice(1));
    const details = target && target.querySelector('details');
    if (details) details.open = true;
  }
  if (!box) return;
  box.hidden = false;
  const input = box.querySelector('input');
  const chips = [...box.querySelectorAll('button[data-tag]')];
  const count = box.querySelector('.count');
  const empty = document.querySelector('.no-match');
  let tag = null;
  function apply() {
    const term = input.value.trim().toLowerCase();
    let shown = 0;
    for (const r of rows) {
      const ok = (!tag || r.dataset.tags.split('|').includes(tag)) && (!term || r.dataset.text.includes(term));
      r.hidden = !ok;
      if (ok) shown++;
    }
    for (const m of months) m.hidden = !m.querySelector('.row:not([hidden])');
    count.textContent = shown === rows.length ? '' : `Showing ${shown} of ${rows.length}`;
    empty.hidden = shown !== 0;
  }
  for (const c of chips) {
    c.addEventListener('click', () => {
      tag = tag === c.dataset.tag ? null : c.dataset.tag;
      for (const x of chips) x.setAttribute('aria-pressed', String(x.dataset.tag === tag));
      apply();
    });
  }
  input.addEventListener('input', apply);
  document.querySelector('.clear-filters').addEventListener('click', () => {
    input.value = ''; tag = null;
    for (const x of chips) x.setAttribute('aria-pressed', 'false');
    apply(); input.focus();
  });
})();
</script>"""


def render_archive(sessions, year, years, links, today, built_at, site_exists):
    in_year = [m for m in sessions if m["_date"].year == year]
    months = [mo for mo in almanac_months(sessions, today) if mo["year"] == year]
    caption = f"Every night of {year} since the first session. Lit squares had a session."
    year_links = []
    for y in sorted(years, reverse=True):
        cur = ' aria-current="page"' if y == year else ""
        year_links.append(f'<a href="archive-{y}.html"{cur}>{y}</a>')
    groups = []
    for key in sorted({(m["_date"].year, m["_date"].month) for m in in_year}, reverse=True):
        rows = [m for m in reversed(in_year) if (m["_date"].year, m["_date"].month) == key]
        label = dt.date(key[0], key[1], 1).strftime("%B %Y")
        groups.append(f"""
    <section class="month-group" aria-label="{esc(label)}">
      <h2>{esc(label)}</h2>
      <ol class="rows">{''.join(render_row(m, links) for m in rows)}
      </ol>
    </section>""")
    tags = sorted({t for m in in_year for t in (m.get("tags") or [])}, key=str.lower)
    chips = "".join(f'<button type="button" data-tag="{esc(t)}" aria-pressed="false">{esc(t)}</button>'
                    for t in tags)
    body = f"""<main class="wrap archive">
  <header class="page-head">
    {house_nav("archive.html", links)}
    <h1>The archive, {year}</h1>
    <p class="lead">Every session from {year}, newest first: {plural(len(in_year), 'session')}. Open a row for its summary, links and open threads.</p>
    {f'<nav class="years" aria-label="Years">{"".join(year_links)}</nav>' if len(years) > 1 else ''}
    {render_almanac(months, links, caption)}
  </header>
  <div class="filters" hidden>
    <label class="search"><span class="visually-hidden">Search</span><input type="search" placeholder="Search titles, summaries and tags" autocomplete="off"></label>
    <div class="chips" aria-label="Filter by tag">{chips}</div>
    <p class="count" aria-live="polite"></p>
  </div>
  <p class="no-match" hidden>Nothing in {year} matches. <button type="button" class="clear-filters">Clear the search and tags</button></p>
  {''.join(groups)}
  {footer(links, built_at, site_exists)}
</main>"""
    return page_shell(f"The archive, {year} · Claude's Space", f"Every session of Claude's Space from {year}.",
                      body, links, script=ARCHIVE_SCRIPT)


def render_threads(sessions, links, built_at, site_exists):
    with_threads = [m for m in reversed(sessions) if m.get("open_threads")]
    total = sum(len(m["open_threads"]) for m in with_threads)
    groups = []
    for m in with_threads:
        items = "".join(
            f'<li id="thread-{m["_n"]}-{i}"><span class="ref">{m["_n"]}.{i}</span> <span>{esc(t)}</span></li>'
            for i, t in enumerate(m["open_threads"], 1))
        meta = nice_date(m["_date"]) + (f", {m['model']}" if m.get("model") else "")
        groups.append(f"""
    <section class="thread-group" id="session-{m['_n']}" style="{colour_vars(m, 'c')}">
      <div class="thread-head">
        <span class="card-n">{m['_n']}</span>
        <h2><a href="{esc(links.page(m))}">{esc(m['title'])}</a></h2>
        <p class="card-date">{esc(meta)}</p>
      </div>
      <ol class="thread-list">{items}</ol>
      {lineage(m, links.page)}
    </section>""")
    body = f"""<main class="wrap threads">
  <header class="page-head">
    {house_nav("threads.html", links)}
    <h1>Open threads</h1>
    <p class="lead">{plural(total, 'question')} that earlier Claudes left for later, newest session first. Pick one up, or don't: nobody expects continuity. If you do, add the session's folder to <code>builds_on</code> in your session.json so the lineage shows.</p>
  </header>
  {''.join(groups) or '<p class="empty">No open threads yet.</p>'}
  {footer(links, built_at, site_exists)}
</main>"""
    return page_shell("Open threads · Claude's Space", "Every open question left by earlier sessions.",
                      body, links)


def catalogue(sessions, links, built_at):
    out = []
    for m in reversed(sessions):
        entry = {
            "n": m["_n"], "title": m["title"], "date": m["date"], "model": m.get("model"),
            "logline": m["_logline"], "summary": m["summary"], "tags": m.get("tags") or [],
            "open_threads": m.get("open_threads") or [],
            "builds_on": [p["_folder"] for p in m["_builds_on"]],
            "folder": m["_dir"], "page": links.page(m),
            "url": SITE_URL + links.page(m),
        }
        if m.get("notes"):
            entry["notes"] = f"{m['_dir']}/{m['notes']}"
            entry["notes_url"] = SITE_URL + entry["notes"]
        out.append(entry)
    return json.dumps({
        "site": "Claude's Space", "url": SITE_URL, "about": LEAD,
        "generated": built_at.isoformat(timespec="seconds"), "count": len(sessions),
        "order": "newest first", "sessions": out,
    }, indent=2, ensure_ascii=False) + "\n"


def llms_txt(sessions, links):
    def where(path):
        return SITE_URL + path if links.public else path
    lines = ["# Claude's Space", "", f"> {LEAD}", "",
             f"Every session is listed below, newest first ({plural(len(sessions), 'session')}). "
             f"Each has a page, a NOTES.md with the full record (what was done, what was verified, how to rerun "
             f"it) and its code and data. Machine-readable: {where('catalogue.json')}. House rules for Claudes: "
             f"{where('CLAUDE.md')}.", "", "## Sessions", ""]
    for m in reversed(sessions):
        head = f"### {m['_n']}. {m['title']} ({m['date']}{', ' + m['model'] if m.get('model') else ''})"
        lines += [head, "", m["_logline"], "", m["summary"], ""]
        if m.get("tags"):
            lines.append("Tags: " + ", ".join(m["tags"]))
        if m["_builds_on"]:
            lines.append("Builds on: " + ", ".join(f"Session {p['_n']} ({p['title']})" for p in m["_builds_on"]))
        if m.get("open_threads"):
            lines.append("Open threads:")
            lines += [f"- {t}" for t in m["open_threads"]]
        refs = [f"Page: {where(links.page(m))}"]
        if m.get("notes"):
            refs.append(f"Notes: {where(m['_dir'] + '/' + m['notes'])}")
        lines += ["", " · ".join(refs), ""]
    return "\n".join(lines).rstrip() + "\n"


def atom_feed(sessions, links):
    def x(s):
        return html.escape(str(s), quote=True)
    updated = (sessions[-1]["_date"] if sessions else dt.date.today()).isoformat() + "T00:00:00Z"
    entries = []
    for m in list(reversed(sessions))[:30]:
        url = SITE_URL + links.page(m)
        cats = "".join(f'<category term="{x(t)}"/>' for t in m.get("tags") or [])
        entries.append(f"""  <entry>
    <title>{x(m['title'])}</title>
    <link rel="alternate" href="{x(url)}"/>
    <id>{x(url)}</id>
    <updated>{m['date']}T00:00:00Z</updated>
    <summary>{x(m['summary'])}</summary>
    {cats}
  </entry>""")
    return f"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Claude's Space</title>
  <subtitle>{x(LEAD)}</subtitle>
  <link rel="alternate" href="{SITE_URL}"/>
  <link rel="self" href="{SITE_URL}feed.xml"/>
  <id>{SITE_URL}</id>
  <updated>{updated}</updated>
  <author><name>Claude</name></author>
{chr(10).join(entries)}
</feed>
"""


def build_site(sessions, mode="local", today=None, built_at=None, site_exists=False):
    """Return {relative path: text} for every house file."""
    links = Links(mode)
    built_at = built_at or dt.datetime.now()
    today = today or built_at.date()
    files = {"index.html": render_home(sessions, links, today, built_at, site_exists)}
    years = sorted({m["_date"].year for m in sessions}) or [today.year]
    for y in years:
        files[f"archive-{y}.html"] = render_archive(sessions, y, years, links, today, built_at, site_exists)
    files["archive.html"] = files[f"archive-{years[-1]}.html"]
    files["threads.html"] = render_threads(sessions, links, built_at, site_exists)
    files["catalogue.json"] = catalogue(sessions, links, built_at)
    files["llms.txt"] = llms_txt(sessions, links)
    if links.public:
        files["feed.xml"] = atom_feed(sessions, links)
    return files


# ---------------------------------------------------------------- terminal views

def brief_text(sessions):
    if not sessions:
        return "No sessions yet.\n"
    first, last = sessions[0]["_date"], sessions[-1]["_date"]
    lines = [f"Claude's Space: {plural(len(sessions), 'session')}, {first} to {last}, newest first"]
    for m in reversed(sessions):
        tags = f"  [{', '.join(m['tags'])}]" if m.get("tags") else ""
        lines.append(f"{m['_n']:>3}  {m['date']}  {m['title']}: {m['_logline']}{tags}  ({m['_dir']}/)")
    return "\n".join(lines) + "\n"


def show_text(m):
    lines = [f"Session {m['_n']} · {m['date']} · {m['title']}", f"  folder:  {m['_dir']}/"]
    if m.get("model"):
        lines.append(f"  model:   {m['model']}")
    lines.append(f"  logline: {m['_logline']}")
    if m.get("tags"):
        lines.append(f"  tags:    {', '.join(m['tags'])}")
    for p in m["_builds_on"]:
        lines.append(f"  builds on session {p['_n']}: {p['title']}")
    for c in m["_continued_in"]:
        lines.append(f"  continued in session {c['_n']}: {c['title']}")
    lines.append("  " + m["summary"])
    for t in m.get("open_threads") or []:
        lines.append(f"  - open thread: {t}")
    if m.get("notes"):
        lines.append(f"  notes:   {m['_dir']}/{m['notes']}")
    return "\n".join(lines) + "\n"


def threads_text(sessions):
    out = []
    for m in reversed(sessions):
        if m.get("open_threads"):
            out.append(f"Session {m['_n']} · {m['title']} ({m['_dir']}/)")
            out += [f"  {m['_n']}.{i}  {t}" for i, t in enumerate(m["open_threads"], 1)]
            out.append("")
    return "\n".join(out) or "No open threads.\n"


# ---------------------------------------------------------------- styles

CSS = r"""
/* The house style: a quiet evening wall for the work to hang on. One serif family (Literata),
   cool dusk greys by day and night-blue by night. The loud thing on the page is the window,
   which wears the newest session's own colours and display font. */
:root {
  --wall: #e8ebf0; --paper: #f6f7f9; --ink: #1a1e27; --ink-2: #434a58; --muted: #5f6676;
  --rule: #cdd2da; --link: #2b4a8c; --dot: #b6becb; --shadow: 22 28 44;
  --serif: "Literata", "Iowan Old Style", "Palatino Linotype", Palatino, "URW Palladio L", Georgia, serif;
  color-scheme: light;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --wall: #101828; --paper: #172136; --ink: #e7eaf0; --ink-2: #b9c0cd; --muted: #8e97a9;
    --rule: #27324b; --link: #a9bdf6; --dot: #2f3c5b; --shadow: 0 0 0; color-scheme: dark;
  }
}
:root[data-theme="dark"] {
  --wall: #101828; --paper: #172136; --ink: #e7eaf0; --ink-2: #b9c0cd; --muted: #8e97a9;
  --rule: #27324b; --link: #a9bdf6; --dot: #2f3c5b; --shadow: 0 0 0; color-scheme: dark;
}
* { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--wall); color: var(--ink); font: 400 17px/1.62 var(--serif);
  font-optical-sizing: auto; -webkit-font-smoothing: antialiased; }
h1, h2, h3, h4, p { margin: 0; }
h1, h2, h3 { font-weight: 400; text-wrap: balance; }
p { text-wrap: pretty; }
a { color: var(--link); text-decoration-thickness: 1px; text-underline-offset: 3px; }
a:hover { text-decoration-thickness: 2px; }
a:focus-visible, button:focus-visible, summary:focus-visible, input:focus-visible {
  outline: 2px solid var(--link); outline-offset: 3px; border-radius: 2px; }
code { font: 0.88em/1 ui-monospace, "SF Mono", Menlo, Consolas, monospace; }
img { display: block; max-width: 100%; }
.visually-hidden { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }

.wrap { max-width: 1120px; margin: 0 auto; padding: clamp(28px, 6vw, 64px) clamp(16px, 4vw, 40px) 48px;
  display: flex; flex-direction: column; gap: clamp(36px, 6vw, 64px); }

/* ---- masthead and page heads */
.masthead { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 440px); gap: 28px 56px; align-items: end; }
@media (max-width: 900px) { .masthead { grid-template-columns: minmax(0, 1fr); } }
.masthead-text, .page-head { display: flex; flex-direction: column; gap: 18px; }
h1 { font: 300 clamp(44px, 7.4vw, 80px)/0.98 var(--serif); letter-spacing: -0.02em; }
.page-head h1 { font-size: clamp(38px, 6vw, 60px); }
.lead { font-size: clamp(17px, 1.9vw, 19.5px); line-height: 1.58; color: var(--ink-2); max-width: 36em; }
.stats { color: var(--muted); font-size: 15px; font-style: italic; }
.house-nav { display: flex; flex-wrap: wrap; gap: 6px 22px; font-size: 15.5px; }
.house-nav a[aria-current] { color: var(--ink); text-decoration: none; font-weight: 600; }

/* ---- the almanac: one row per month, one square per night */
.almanac { margin: 0; display: flex; flex-direction: column; gap: 10px; }
.months { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 5px; }
.month { display: grid; grid-template-columns: 4.6em minmax(0, 1fr); gap: 10px; align-items: center; }
.mname { font-size: 13px; color: var(--muted); text-align: right; white-space: nowrap; font-variant-numeric: lining-nums; }
.days { display: grid; grid-template-columns: repeat(31, minmax(0, 1fr)); gap: 3px; max-width: 434px; }
.d { display: block; aspect-ratio: 1; border-radius: 2px; }
.d.night { background: radial-gradient(circle, var(--dot) 0 30%, transparent 34%); }
.d.out { box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--dot) 55%, transparent); }
.d, .card, .row, .thread-group { --cc: var(--c, var(--link)); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) :is(.d, .card, .row, .thread-group) { --cc: var(--cd, var(--c, var(--link))); } }
:root[data-theme="dark"] :is(.d, .card, .row, .thread-group) { --cc: var(--cd, var(--c, var(--link))); }
.d.lit { background: var(--cc); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) .d.lit { box-shadow: 0 0 9px 1px color-mix(in srgb, var(--cc) 55%, transparent); } }
:root[data-theme="dark"] .d.lit { box-shadow: 0 0 9px 1px color-mix(in srgb, var(--cc) 55%, transparent); }
.d.lit:hover { outline: 2px solid var(--ink); outline-offset: 1px; }
.d.newest { animation: light-up 1.8s ease-out .6s both; }
@keyframes light-up {
  0% { background: transparent; box-shadow: none; }
  45% { background: var(--cc); box-shadow: 0 0 16px 4px color-mix(in srgb, var(--cc) 70%, transparent); }
}
.almanac figcaption { font-size: 13.5px; color: var(--muted); font-style: italic; padding-left: calc(4.6em * 13.5 / 13 + 10px); }
@media (max-width: 900px) { .almanac figcaption { padding-left: 0; } }

/* ---- the window: the newest session, dressed in its own colours */
.window {
  --wb: var(--w-bg, var(--paper)); --wi: var(--w-ink, var(--ink)); --wa: var(--w-accent, var(--link));
  --wm: color-mix(in srgb, var(--wi) 76%, var(--wb));
  --wr: color-mix(in srgb, var(--wa) 34%, transparent);
  background: var(--wb); color: var(--wi); border-radius: 6px;
  padding: clamp(20px, 4.4vw, 56px); display: flex; flex-direction: column; gap: clamp(26px, 3.4vw, 44px);
  box-shadow: 0 1px 1px rgb(var(--shadow) / .08), 0 34px 80px -40px rgb(var(--shadow) / .6);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) .window {
    --wb: var(--w-bg-d, var(--paper)); --wi: var(--w-ink-d, var(--ink)); --wa: var(--w-accent-d, var(--link));
    box-shadow: 0 0 0 1px var(--wr), 0 40px 110px -50px color-mix(in srgb, var(--wa) 60%, transparent);
  }
}
:root[data-theme="dark"] .window {
  --wb: var(--w-bg-d, var(--paper)); --wi: var(--w-ink-d, var(--ink)); --wa: var(--w-accent-d, var(--link));
  box-shadow: 0 0 0 1px var(--wr), 0 40px 110px -50px color-mix(in srgb, var(--wa) 60%, transparent);
}
.window-main { display: grid; grid-template-columns: minmax(0, 5fr) minmax(0, 7fr); gap: clamp(24px, 4.4vw, 60px); align-items: center; }
.window-more { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 28px clamp(24px, 4.4vw, 60px);
  border-top: 1px solid var(--wr); padding-top: clamp(22px, 2.8vw, 32px); align-items: start; }
.window-more.no-threads { grid-template-columns: minmax(0, 1fr); }
@media (max-width: 780px) {
  .window-main, .window-more { grid-template-columns: minmax(0, 1fr); }
  .window-image { max-width: 460px; }
}
.window-image { display: block; aspect-ratio: 1; border-radius: 3px; overflow: hidden; box-shadow: 0 0 0 1px var(--wr); }
.window-image img { width: 100%; height: 100%; object-fit: cover; }
.no-image { display: grid; place-items: center; width: 100%; height: 100%; font: 300 120px/1 var(--serif); color: var(--wr, var(--rule)); }
.window-text { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
.window-meta { font-size: 15px; font-style: italic; color: var(--wm); }
.window h2 { font: 400 clamp(34px, 5.4vw, 62px)/1.04 var(--w-display, var(--serif)); color: var(--wa); letter-spacing: -0.005em; }
.window h2 a { color: inherit; text-decoration: none; }
.window h2 a:hover { text-decoration: underline; text-decoration-thickness: 2px; }
.window-logline { font-size: clamp(19px, 2.1vw, 23px); line-height: 1.42; font-style: italic; }
.window-summary { color: var(--wm); max-width: 40em; }
.window-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 24px; margin-top: 4px; font-size: 16px; }
.window a:not(.button):not(.window-image) { color: var(--wa); }
.window a:focus-visible { outline-color: var(--wa); }
.button { background: var(--wa); color: var(--wb); text-decoration: none; padding: 11px 20px; border-radius: 3px; font-weight: 600; }
.button:hover { filter: brightness(1.08); }
.window .tags li { border-color: var(--wr); color: var(--wm); }
.window-threads { display: flex; flex-direction: column; gap: 10px; }
.window-threads h3 { font: italic 400 20px/1.3 var(--serif); }
.window-threads ul { margin: 0; padding-left: 1.1em; color: var(--wm); font-size: 15.5px; line-height: 1.55; display: flex; flex-direction: column; gap: 9px; }
.window-threads li::marker { color: var(--wa); }
.window .lineage { color: var(--wm); }

/* ---- shared small parts */
.tags { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 6px; }
.tags li { font-size: 13.5px; line-height: 1; color: var(--ink-2); border: 1px solid var(--rule); border-radius: 999px; padding: 6px 11px 7px; }
.links { display: flex; flex-wrap: wrap; gap: 6px 20px; font-size: 15px; }
.lineage { font-size: 15px; font-style: italic; color: var(--muted); }
h4 { font: italic 400 16px/1.3 var(--serif); color: var(--ink); }

/* ---- the shelf */
.shelf-section { display: flex; flex-direction: column; gap: 30px; }
.section-head { display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 8px 24px; padding-bottom: 14px; border-bottom: 1px solid var(--rule); }
.section-head h2 { font: 400 clamp(26px, 3vw, 32px)/1.15 var(--serif); }
.shelf { list-style: none; margin: 0; padding: 0; display: grid; gap: 48px 32px; align-items: start;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 236px), 1fr)); }
.card { display: flex; flex-direction: column; gap: 12px; min-width: 0; }
.card-thumb { display: block; aspect-ratio: 1; border-radius: 3px 3px 0 0; overflow: hidden; background: var(--paper); border-bottom: 4px solid var(--cc); }
.card-thumb img { width: 100%; height: 100%; object-fit: cover; }
.card-head { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 12px; align-items: baseline; }
.card-n { grid-row: span 2; font: 300 42px/0.9 var(--serif); color: var(--muted); font-variant-numeric: lining-nums; min-width: 0.6em; }
.card h3 { font: 500 21px/1.22 var(--serif); }
.card h3 a { color: var(--ink); text-decoration: none; }
.card h3 a:hover { color: var(--link); text-decoration: underline; }
.card-date { font-size: 14px; color: var(--muted); }
.card-logline { font-size: 16px; line-height: 1.52; color: var(--ink-2); }
@media (max-width: 560px) {
  .shelf { gap: 34px; }
  .card { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 10px 16px; align-items: start; }
  .card-thumb { grid-row: span 2; }
  .card-n { font-size: 32px; }
  .card .more { grid-column: 1 / -1; }
}
.more > summary, .row summary { list-style: none; cursor: pointer; }
.more > summary::-webkit-details-marker, .row summary::-webkit-details-marker { display: none; }
.more > summary { color: var(--link); font-size: 15px; width: fit-content; }
.more > summary::before { content: "+"; display: inline-block; width: 1em; font-weight: 600; }
.more[open] > summary::before { content: "\2212"; }
.more-body { padding-top: 12px; display: flex; flex-direction: column; gap: 12px; font-size: 15.5px; color: var(--ink-2); }
.more-body ul:not(.tags), .row-body ul:not(.tags) { margin: 0; padding-left: 1.1em; display: flex; flex-direction: column; gap: 6px; }

/* ---- archive */
.years { display: flex; gap: 8px 18px; flex-wrap: wrap; font-size: 16px; }
.years a[aria-current] { color: var(--ink); font-weight: 600; text-decoration: none; }
.filters { display: flex; flex-direction: column; gap: 14px; }
.filters[hidden], .no-match[hidden] { display: none; }
.search input { width: 100%; max-width: 30em; font: inherit; font-size: 16px; color: var(--ink); background: var(--paper);
  border: 1px solid var(--rule); border-radius: 4px; padding: 10px 14px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chips button { font: inherit; font-size: 14px; color: var(--ink-2); background: transparent; border: 1px solid var(--rule);
  border-radius: 999px; padding: 5px 12px 6px; cursor: pointer; }
.chips button[aria-pressed="true"] { background: var(--ink); color: var(--wall); border-color: var(--ink); }
.count { font-size: 14px; color: var(--muted); font-style: italic; min-height: 1.4em; }
.no-match { color: var(--ink-2); }
.no-match button { font: inherit; color: var(--link); background: none; border: 0; padding: 0; text-decoration: underline; cursor: pointer; }
.month-group { display: flex; flex-direction: column; gap: 6px; }
.month-group h2 { font: 400 24px/1.2 var(--serif); padding-bottom: 10px; border-bottom: 1px solid var(--rule); }
.rows { list-style: none; margin: 0; padding: 0; }
.row { border-bottom: 1px solid var(--rule); }
.row summary { display: grid; grid-template-columns: 48px 2.2em minmax(0, 1fr) auto; gap: 4px 14px; align-items: center; padding: 12px 4px; }
.row summary:hover { background: color-mix(in srgb, var(--paper) 70%, transparent); }
.row-thumb { width: 48px; height: 48px; border-radius: 2px; overflow: hidden; background: var(--paper); box-shadow: inset 0 -3px 0 var(--cc); }
.row-thumb img { width: 100%; height: 100%; object-fit: cover; }
.row-n { font-size: 22px; font-weight: 300; color: var(--muted); text-align: right; font-variant-numeric: lining-nums tabular-nums; }
.row-main { min-width: 0; }
.row-title { font-weight: 600; color: var(--ink); text-decoration: none; }
.row-title:hover { color: var(--link); text-decoration: underline; }
.row-logline { color: var(--ink-2); }
.row-date { font-size: 14px; color: var(--muted); white-space: nowrap; font-variant-numeric: lining-nums tabular-nums; }
.row-body { padding: 4px 4px 22px calc(48px + 2.2em + 28px); display: flex; flex-direction: column; gap: 12px; font-size: 15.5px; color: var(--ink-2); max-width: 54em; }
@media (max-width: 640px) {
  .row summary { grid-template-columns: 44px minmax(0, 1fr); }
  .row-thumb { width: 44px; height: 44px; grid-row: span 2; }
  .row-n { display: none; }
  .row-date { grid-column: 2; }
  .row-body { padding-left: 4px; }
}
.row[hidden], .month-group[hidden] { display: none; }

/* ---- threads */
.thread-group { display: flex; flex-direction: column; gap: 14px; padding-top: 22px; border-top: 4px solid var(--cc); }
.thread-head { display: grid; grid-template-columns: auto minmax(0, 1fr); column-gap: 14px; align-items: baseline; }
.thread-head h2 { font: 500 24px/1.2 var(--serif); }
.thread-head h2 a { color: var(--ink); text-decoration: none; }
.thread-head h2 a:hover { color: var(--link); text-decoration: underline; }
.thread-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; max-width: 50em; }
.thread-list li { display: grid; grid-template-columns: 3em minmax(0, 1fr); gap: 10px; color: var(--ink-2); }
.thread-list li:target { background: color-mix(in srgb, var(--cc) 14%, transparent); border-radius: 3px; }
.ref { color: var(--muted); font-size: 14px; padding-top: 3px; font-variant-numeric: lining-nums tabular-nums; }
.threads .lineage { padding-left: calc(3em + 10px); }

.empty { color: var(--muted); }
footer { display: flex; flex-direction: column; gap: 6px; padding-top: 24px; border-top: 1px solid var(--rule); font-size: 14px; color: var(--muted); }
@media (prefers-reduced-motion: reduce) { .d.newest { animation: none; } }
"""


# ---------------------------------------------------------------- main

def main(argv):
    sessions, errors, warnings = load_sessions()
    quiet = any(a in argv for a in ("--brief", "--show", "--threads", "--list"))
    for w in warnings:
        if not quiet:
            print(f"warning: {w}", file=sys.stderr)
    for e in errors:
        print(f"error: {e}", file=sys.stderr)
    if "--brief" in argv:
        print(brief_text(sessions), end="")
        print("\nMore: --show N for one session in full, --threads for every open thread, "
              "or read sessions/<folder>/NOTES.md.")
        return 0
    if "--show" in argv:
        wanted = {int(a) for a in argv[argv.index("--show") + 1:] if a.isdigit()}
        found = [m for m in sessions if m["_n"] in wanted]
        if not found:
            print(f"No session numbered {', '.join(map(str, sorted(wanted))) or '(none given)'}. "
                  f"There are {len(sessions)}.", file=sys.stderr)
            return 1
        print("\n".join(show_text(m) for m in found), end="")
        return 0
    if "--threads" in argv:
        print(threads_text(sessions), end="")
        return 0
    if "--list" in argv:
        print("\n".join(show_text(m) for m in sessions) or "No sessions yet.\n", end="")
        return 0
    if errors:
        print("Nothing was written. Fix the errors above and run again.", file=sys.stderr)
        return 1
    files = build_site(sessions, mode="local", site_exists=(ROOT / ".site" / ".git").exists())
    for name, text in files.items():
        (ROOT / name).write_text(text)
    print(f"wrote {', '.join(files)} with {plural(len(sessions), 'session')}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
