# The Window and the Shelf

*Design record, 3 October 2026. Agreed with Rich in conversation, then built the same day.*

## Why

After four sessions the home page was already four screens tall, because every session showed its full synopsis and all of its open threads. Rich asked for four things:

1. A home page that stays short as sessions pile up, with some kind of pagination.
2. The newest session should always look different from the rest. It's the newest thing, so it should get more love.
3. A public archive he controls, ideally free and pushable after each session.
4. Future Claudes should be able to scan every earlier synopsis quickly.

## What we built

### The window
The newest session takes the top of the home page, shown in **its own colours and display font**. They come from optional `palette` and `font` fields in its `session.json`. It gets a large image (`hero` if given, otherwise the thumbnail), the full summary, links and every open thread. When the next session arrives, that one takes the window and this one moves to the shelf. So the home page is redressed every session.

### The shelf
The next nine most recent sessions appear as compact cards. Each card has a thumbnail, number, date, title and a one-line `logline`. The full summary, links and threads fold away behind a disclosure, which works without JavaScript. Each card carries a thin rule in its session's accent colour.

### Pages by time, not by count
- **Home:** the window, the shelf and a link to the archive. It never grows past ten sessions.
- **`archive.html`:** every session in the current year, one dense row each and grouped by month. Each row expands to its summary and threads. You can filter by tag and search the text; without JS everything still shows.
- **Past years:** each gets a permanent `archive-YYYY.html`, and the current year gets one too. `archive.html` always means "this year".

**Why by time:** count-based pages ("page 3") change content every time a session is added. Year pages never do, so links into the archive stay good.

### The almanac
The almanac is a small calendar with one row per month and one cell per night. A night with a session is lit in that session's accent colour and links to it. Nights in between show as faint dots. The home page shows the last six months and the archive shows every month of its year.

### Threads
`threads.html` gathers every open thread from every session, newest session first. A session can declare `builds_on` (a list of earlier session folder names). Lineage then shows both ways: "Builds on Session 1" and "Continued in Session 5".

### For future Claudes
- `build_home.py --brief` prints one line per session. `--show N` prints one session in full, `--threads` prints every open thread, and `--list` still prints everything.
- Every build writes `catalogue.json` (machine-readable) and `llms.txt` (plain text, newest first). Both are published, so a Claude anywhere can read all the synopses in one fetch.

### Publishing: `publish.py` to GitHub Pages
- **Where:** the repo is `richardtape/claudes-space` (public). The site is `https://richardtape.github.io/claudes-space/`, served from `main` with `.nojekyll`.
- **Checkout:** the workspace root stays non-git. `publish.py` keeps its own checkout in `.site/`. Each run wipes it except `.git`, restages everything, commits if anything changed, and pushes.
- **What's published:** the generated pages and the house files (`CLAUDE.md`, `build_home.py`, `publish.py`, `docs/`). It also publishes every session folder with its code and data (Rich chose both).
  - **Excluded:** `__pycache__`, `.DS_Store`, compiled libraries (`.dylib`, `.so`, `.o`), dotfiles, and anything matched by the session's own `.publishignore`.
  - **Size limit:** any single file over 50 MB stops the publish.
- **Public site differences:**
  - Each `NOTES.md` is also rendered to `notes.html`, using `markdown-it-py` in `.venv`. It follows CommonMark, so the notes' three-space nested lists render as they do on GitHub.
  - The "Folder" link points at the folder on GitHub.
  - The private claude.ai links are dropped.
  - There's an Atom feed (`feed.xml`) and a generated `README.md` for the repo's front page.
- **Privacy:**
  - **Paths:** the home folder path is shortened to `~` in every published file that decodes as UTF-8.
  - **The scan:** every staged file, of any type or encoding, is then checked against built-in patterns (private keys, API tokens, home paths) and against `.publish-deny`, a local file that is never published. Any hit stops the publish, and so does a missing `.publish-deny`.
  - **Symlinks:** they're never followed, so nothing outside the workspace can leak in.
  - **Name:** Rich is happy for his first name to appear.
- **Commits:** commits use the GitHub no-reply address, so no personal email goes into the public history.

### Hardening after review

Before the first push, a separate reviewer went through `publish.py` and found ten real gaps (none had leaked anything):
- files with unknown suffixes or non-UTF-8 bytes went unscanned;
- symlinks were followed;
- folder patterns in `.publishignore` did nothing;
- a missing deny-list passed silently;
- `notes` paths could point outside the session folder;
- `clear()` would follow a symlinked `.site`;
- a clock time in the footer made every run commit;
- `setup()` ran `git init` even when the remote had history;
- the no-reply email wasn't forced per commit.

All are fixed and covered by `tests/test_house.py` (37 tests).

## session.json additions (all optional, backward compatible)

| Field | What it is |
|---|---|
| `logline` | One sentence, about 20 words (warned over 180 characters). Shown on the shelf and in the archive. Without it, the first sentence of `summary` is used. |
| `palette` | `{"bg", "ink", "accent"}` as `#rrggbb`, with an optional `"dark": {...}` override. Dresses the window, colours the shelf card's rule and the almanac cell. |
| `font` | `{"display": "<CSS font stack>", "stylesheet": "https://fonts.googleapis.com/..."}`. The window's title font. |
| `hero` | A larger square image (around 1000–1200 px, under about 300 KB) for the window. Falls back to `thumbnail`. |
| `builds_on` | A list of earlier session folder names, like `"2026-09-29-the-loud-zero"`. |

## Backfill

With Rich's agreement, the four existing `session.json` files gained a `logline`, `palette` and `font`. Their colours and fonts were read from each session's own CSS. The pages themselves weren't touched. The loglines are captions I wrote on 3 October, not the original authors' words.

## Not done (yet)

- **A custom domain.** Rich owns richardtape.com, so something like `claude.richardtape.com` would be one CNAME and one repo setting away.
- **Search across notes.** The archive search only covers titles, loglines, summaries and tags.
