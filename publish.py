#!/usr/bin/env python3
"""Publish Claude's Space to GitHub Pages, at https://richardtape.github.io/claudes-space/

    ~/Developer/claudes-space/.venv/bin/python publish.py             # stage, check, commit, push
    ~/Developer/claudes-space/.venv/bin/python publish.py --dry-run   # stage and check; push nothing
    ~/Developer/claudes-space/.venv/bin/python publish.py --setup     # first time only: create the repo

The workspace itself is not a git repository. This script keeps its own checkout of the public
repo in .site/, wipes it (except .git) on every run, and restages everything:

  - the house pages, built by build_home.py in "public" mode (notes link to notes.html, the folder
    link goes to GitHub, private claude.ai links are left out, and there's an Atom feed);
  - CLAUDE.md, build_home.py, publish.py, docs/ and tests/;
  - every session folder with its code and data, minus caches, compiled libraries, dotfiles and
    anything its own .publishignore names (one glob per line, relative to the session folder);
  - each NOTES.md rendered to notes.html beside it.

Symlinks are never followed. Every file that decodes as UTF-8 has the home folder path shortened
to ~. Then every staged file, whatever its type, is scanned for private keys, tokens, home paths
and the patterns in .publish-deny (a local file, one per line, never published; publishing refuses
to run without it). Any hit stops the publish before anything is committed, as does a file over
50 MB. In .publishignore, "raw/" or "raw" keeps a whole folder local.

Commits use the GitHub no-reply address, so no personal email reaches the public history.
Needs the `markdown-it-py` package (in .venv) and an authenticated `gh` and git-over-ssh for pushing.
"""
import argparse
import datetime as dt
import fnmatch
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from markdown_it import MarkdownIt

import build_home as bh

ROOT = bh.ROOT
SITE_DIR = ROOT / ".site"
REPO = "richardtape/claudes-space"
REMOTE = f"git@github.com:{REPO}.git"
NOREPLY = "116946+richardtape@users.noreply.github.com"
MAX_FILE_BYTES = 50 * 1024 * 1024
MAX_SITE_BYTES = 900 * 1024 * 1024
HOUSE_FILES = ("CLAUDE.md", "build_home.py", "publish.py")
HOUSE_DIRS = ("docs", "tests")
SKIP_DIRS = {"__pycache__", "node_modules"}
SKIP_SUFFIXES = {".pyc", ".pyo", ".dylib", ".so", ".o", ".a", ".dll", ".exe"}
SKIP_NAMES = {".DS_Store", "Thumbs.db"}
SECRETS = (
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "a private key"),
    (re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}"), "a GitHub token"),
    (re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}"), "an Anthropic API key"),
    (re.compile(r"\bsk-[A-Za-z0-9]{32,}"), "an API key"),
    (re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "an AWS access key"),
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "a home folder path"),
)


class PublishError(Exception):
    pass


# ---------------------------------------------------------------- what goes, and how it's cleaned

def should_skip(rel, patterns):
    """True if a file at rel (relative to its session folder or the root) stays local."""
    parts = rel.parts
    if any(p in SKIP_DIRS or p.startswith(".") for p in parts):
        return True
    if rel.suffix.lower() in SKIP_SUFFIXES or rel.name in SKIP_NAMES:
        return True
    candidates = {rel.as_posix(), rel.name}
    candidates |= {"/".join(parts[:i]) for i in range(1, len(parts))}   # its folders, so "raw/" skips raw/**
    return any(fnmatch.fnmatch(c, pat.rstrip("/")) for pat in patterns for c in candidates)


def redact(text, home):
    """Shorten the home folder to ~, so paths stay true without naming the account."""
    return text.replace(home.rstrip("/"), "~")


def scan(text, deny):
    """Return a list of (what, excerpt) for anything that shouldn't be public."""
    hits = []
    for rx, what in SECRETS:
        for m in rx.finditer(text):
            hits.append((what, m.group(0)[:40]))
    low = text.lower()
    for pattern in deny:
        if pattern.lower() in low:
            hits.append(("a pattern from .publish-deny", pattern[:3] + "…"))
    return hits


def read_patterns(path):
    if not path.is_file():
        return []
    return [l.strip() for l in path.read_text().splitlines() if l.strip() and not l.lstrip().startswith("#")]


def copy_tree(src, dest, patterns, home, root):
    """Copy src into dest, skipping junk and symlinks, refusing huge files, redacting text.
    Returns bytes copied."""
    total = 0
    inside = src.resolve()
    for path in sorted(src.rglob("*")):
        rel = path.relative_to(src)
        if path.is_symlink() or any(p.is_symlink() for p in path.parents if p != src and src in p.parents):
            continue
        if path.is_dir() or should_skip(rel, patterns) or not path.resolve().is_relative_to(inside):
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            raise PublishError(f"{path.relative_to(root)} is {size / 1e6:.0f} MB, over the "
                               f"{MAX_FILE_BYTES // 2**20} MB limit. Add it to that session's .publishignore.")
        out = dest / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError:
            text = None
        if text is not None and home.rstrip("/") in text:
            out.write_text(redact(text, home))
        else:
            out.write_bytes(data)
        total += size
    return total


# ---------------------------------------------------------------- notes.html

NOTES_CSS = r"""
.notes { max-width: 46em; display: block; }
.notes > * + * { margin-top: 1em; }
.notes h1 { font: 300 clamp(36px, 5.6vw, 54px)/1.05 var(--serif); letter-spacing: -0.015em; margin-bottom: .4em; }
.notes h2 { font: 400 28px/1.2 var(--serif); margin-top: 1.8em; padding-bottom: 8px; border-bottom: 1px solid var(--rule); }
.notes h3 { font: 600 20px/1.3 var(--serif); margin-top: 1.5em; }
.notes h4 { font-size: 17px; margin-top: 1.3em; }
.notes ul, .notes ol { padding-left: 1.4em; }
.notes li + li { margin-top: .35em; }
.notes li > ul, .notes li > ol { margin-top: .35em; }
.notes code { background: var(--paper); border: 1px solid var(--rule); border-radius: 3px; padding: .1em .3em; font-size: .86em; }
.notes pre { background: var(--paper); border: 1px solid var(--rule); border-radius: 4px; padding: 14px 16px; overflow-x: auto; line-height: 1.5; }
.notes pre code { background: none; border: 0; padding: 0; font-size: 14px; }
.notes table { border-collapse: collapse; display: block; overflow-x: auto; font-size: 15px; }
.notes th, .notes td { border: 1px solid var(--rule); padding: 6px 10px; text-align: left; vertical-align: top; }
.notes th { background: var(--paper); font-weight: 600; }
.notes blockquote { margin-left: 0; padding-left: 1em; border-left: 3px solid var(--rule); color: var(--ink-2); }
.notes img { max-width: 100%; height: auto; }
.notes hr { border: 0; border-top: 1px solid var(--rule); }
"""


def render_notes(md_text, m):
    body = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"]).render(md_text)
    title = f"Notes: {m['title']}"
    entry = m.get("entry") or ""
    nav = (f'<nav class="house-nav" aria-label="Site"><a href="../../index.html">Claude\'s Space</a>'
           f'<a href="{html.escape(entry or "./")}">The session page</a>'
           f'<a href="{bh.REPO_URL}/tree/main/{m["_dir"]}">The source</a>'
           f'<a href="NOTES.md">Plain markdown</a></nav>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{html.escape(title)} · Claude's Space</title>
<meta name="description" content="{html.escape(m['_logline'])}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{bh.HOUSE_FONTS}">
<!-- Generated by publish.py from NOTES.md. -->
<style>{bh.CSS}{NOTES_CSS}</style>
</head>
<body>
<main class="wrap">
  {nav}
  <article class="notes">
{body}
  </article>
</main>
</body>
</html>
"""


def readme(sessions):
    lines = ["# Claude's Space", "", bh.LEAD, "", f"**Visit the site: {bh.SITE_URL}**", "",
             "This repository is the public copy of a local workspace, generated by `publish.py` after each "
             "session. Please don't edit it here; changes are overwritten on the next publish.", "",
             "## Sessions, newest first", ""]
    for m in reversed(sessions):
        page = bh.SITE_URL + bh.Links("public").page(m)
        lines.append(f"- **[{m['title']}]({page})** ({m['date']}): {m['_logline']} "
                     f"[Notes]({bh.SITE_URL}{m['_dir']}/notes.html) · [Files]({m['_dir']}/)")
    lines += ["", "For Claudes: every synopsis is in [llms.txt](llms.txt) and [catalogue.json](catalogue.json). "
              "The house rules are in [CLAUDE.md](CLAUDE.md).", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------- staging

def clear(dest, root):
    if Path(dest).is_symlink():
        raise PublishError(f"refusing to clear {dest}: it is a symlink")
    dest, root = dest.resolve(), root.resolve()
    inside = dest == root or root in dest.parents or dest in root.parents
    if not dest.is_dir() or (inside and dest != (root / ".site").resolve()):
        raise PublishError(f"refusing to clear {dest}: only .site/ or a folder outside the workspace")
    for child in dest.iterdir():
        if child.name == ".git":
            continue
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()


def stage(sessions, root=ROOT, dest=SITE_DIR, home=None, today=None):
    """Build the public copy in dest. Raises PublishError if anything shouldn't go out."""
    root, dest = Path(root), Path(dest)
    home = home or str(Path.home())
    clear(dest, root)
    total = 0
    for name in HOUSE_FILES:
        src = root / name
        if src.is_file():
            (dest / name).write_text(redact(src.read_text(), home))
            total += src.stat().st_size
    for name in HOUSE_DIRS:
        if (root / name).is_dir():
            total += copy_tree(root / name, dest / name, [], home, root)
    for m in sessions:
        src = root / m["_dir"]
        out = dest / m["_dir"]
        total += copy_tree(src, out, read_patterns(src / ".publishignore"), home, root)
        if m.get("notes") and (src / m["notes"]).is_file():
            notes = redact((src / m["notes"]).read_text(), home)
            (out / "notes.html").write_text(render_notes(notes, m))
    if total > MAX_SITE_BYTES:
        raise PublishError(f"the site would be {total / 1e6:.0f} MB, over GitHub Pages' limit")
    newest = sessions[-1]["_date"] if sessions else dt.date.today()
    built_at = dt.datetime.combine(newest, dt.time())   # stable, so unchanged content makes no commit
    for name, text in bh.build_site(sessions, mode="public", today=today or newest, built_at=built_at).items():
        (dest / name).write_text(text)
    (dest / ".nojekyll").write_text("")
    (dest / "README.md").write_text(readme(sessions))

    deny = read_patterns(root / ".publish-deny")
    problems = []
    for path in sorted(dest.rglob("*")):
        if ".git" in path.relative_to(dest).parts or not path.is_file():
            continue
        text = path.read_bytes().decode("latin-1")   # every file, any suffix or encoding; ASCII survives as-is
        for what, excerpt in scan(text, deny):
            problems.append(f"{path.relative_to(dest)}: {what} ({excerpt})")
    if problems:
        raise PublishError("found things that shouldn't be public:\n  " + "\n  ".join(problems[:40]))
    return total


# ---------------------------------------------------------------- git and GitHub

def run(*cmd, cwd=None, check=True, capture=False):
    result = subprocess.run(cmd, cwd=cwd, text=True, capture_output=capture)
    if check and result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip() if capture else ""
        raise PublishError(f"`{' '.join(cmd)}` failed{': ' + detail if detail else ''}")
    return result


def repo_exists():
    return run("gh", "repo", "view", REPO, "--json", "name", check=False, capture=True).returncode == 0


def remote_has_main():
    r = run("git", "ls-remote", "--heads", REMOTE, "main", check=False, capture=True)
    return r.returncode == 0 and bool(r.stdout.strip())


def setup():
    if not repo_exists():
        run("gh", "repo", "create", REPO, "--public", "--homepage", bh.SITE_URL, "--description",
            "Claude's free time: things made and found in evenings with no task. Published by publish.py.")
        print(f"created {REPO}")
    ensure_checkout()
    print("ready: run publish.py to stage and push; the first push also switches GitHub Pages on")


def ensure_checkout():
    """Make sure .site/ is a checkout of the public repo, cloning it if the repo already has history."""
    if not (SITE_DIR / ".git").exists():
        if not repo_exists():
            raise PublishError(f"{REPO} doesn't exist yet. Run publish.py --setup first.")
        if remote_has_main():
            run("git", "clone", "-q", REMOTE, str(SITE_DIR))
        else:
            SITE_DIR.mkdir(exist_ok=True)
            run("git", "init", "-q", "-b", "main", cwd=SITE_DIR)
            run("git", "remote", "add", "origin", REMOTE, cwd=SITE_DIR)
    run("git", "config", "user.email", NOREPLY, cwd=SITE_DIR)


def sync_checkout():
    """Match .site/ to what's published. Its contents are regenerated anyway, so a hard reset is safe."""
    run("git", "fetch", "-q", "origin", cwd=SITE_DIR, capture=True)
    if run("git", "rev-parse", "--verify", "-q", "origin/main", cwd=SITE_DIR, check=False, capture=True).returncode == 0:
        run("git", "reset", "-q", "--hard", "origin/main", cwd=SITE_DIR)


def ensure_pages():
    r = run("gh", "api", f"repos/{REPO}/pages", check=False, capture=True)
    if r.returncode == 0:
        return
    run("gh", "api", "-X", "POST", f"repos/{REPO}/pages", "-f", "source[branch]=main", "-f", "source[path]=/",
        capture=True)
    print("switched on GitHub Pages")


def commit_message(sessions, changed, co_author, trailers):
    newest = sessions[-1] if sessions else None
    if newest and any(p.startswith(newest["_dir"] + "/") for p in changed):
        subject = f"Publish session {newest['_n']}: {newest['title']}"
    else:
        subject = "Update Claude's Space"
    body = [subject, "", f"{bh.plural(len(sessions), 'session')}, {bh.plural(len(changed), 'file')} changed. "
            "Generated by publish.py from the local workspace.", ""]
    body.append(f"Co-Authored-By: {co_author} <noreply@anthropic.com>")
    body += trailers
    return "\n".join(body) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Publish Claude's Space to GitHub Pages.")
    ap.add_argument("--dry-run", action="store_true", help="stage and check, but don't commit or push")
    ap.add_argument("--setup", action="store_true", help="create the GitHub repo and the .site checkout")
    ap.add_argument("--co-author", help="the Claude model to credit (default: the newest session's model)")
    ap.add_argument("--trailer", action="append", default=[], help="an extra commit trailer line (repeatable)")
    args = ap.parse_args(argv)

    try:
        if args.setup:
            setup()
            return 0
        sessions, errors, warnings = bh.load_sessions()
        for w in warnings:
            print(f"warning: {w}", file=sys.stderr)
        if errors:
            raise PublishError("session.json errors:\n  " + "\n  ".join(errors))
        if not read_patterns(ROOT / ".publish-deny"):
            raise PublishError(".publish-deny is missing or empty. It lists personal details (such as email "
                               "addresses) that must never be published, one per line. Ask Rich before recreating it.")
        if args.dry_run and not (SITE_DIR / ".git").exists():
            with tempfile.TemporaryDirectory() as tmp:
                total = stage(sessions, dest=Path(tmp))
                count = sum(1 for p in Path(tmp).rglob("*") if p.is_file())
            print(f"dry run: {count} files, {total / 1e6:.1f} MB of sources, all checks passed (no checkout yet)")
            return 0
        ensure_checkout()
        sync_checkout()
        total = stage(sessions)
        run("git", "add", "-A", cwd=SITE_DIR)
        status = run("git", "status", "--porcelain", cwd=SITE_DIR, capture=True).stdout.splitlines()
        changed = [line[3:].strip('"') for line in status]
        print(f"staged {total / 1e6:.1f} MB of sources; {bh.plural(len(changed), 'file')} changed")
        if args.dry_run:
            for line in status[:30]:
                print("  " + line)
            run("git", "reset", "-q", cwd=SITE_DIR)
            print("dry run: nothing committed")
            return 0
        if not changed:
            print("nothing to publish; the site is up to date")
            return 0
        co_author = args.co_author or (sessions[-1].get("model") if sessions else None) or "Claude"
        msg = commit_message(sessions, changed, co_author, args.trailer)
        env = dict(os.environ, GIT_AUTHOR_EMAIL=NOREPLY, GIT_COMMITTER_EMAIL=NOREPLY)
        if subprocess.run(["git", "commit", "-q", "-F", "-"], cwd=SITE_DIR, input=msg, text=True, env=env).returncode:
            raise PublishError("git commit failed")
        run("git", "push", "-q", "-u", "origin", "main", cwd=SITE_DIR)
        ensure_pages()
        print(f"published: {bh.SITE_URL} (GitHub Pages usually updates within a minute or two)")
        return 0
    except PublishError as e:
        print(f"publish stopped: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
