"""Tests for the shared house scripts: build_home.py and publish.py.

    ~/Developer/claudes-space/.venv/bin/python -m unittest discover -s tests -v

build_home.py is stdlib only; publish.py needs the `markdown-it-py` package from .venv.
Each test builds a throwaway workspace in a temp folder, so the real sessions are never touched.
"""
import datetime as dt
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import build_home as bh  # noqa: E402

# Built in pieces so the privacy scan in publish.py doesn't flag this file when it is published.
FAKE_HOME = "/Users" + "/someone"

PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082"
)


def make_session(root, folder, **meta):
    d = root / "sessions" / folder
    d.mkdir(parents=True, exist_ok=True)
    base = {"title": folder, "date": folder[:10], "summary": f"Summary of {folder}. Second sentence.",
            "entry": "index.html", "notes": "NOTES.md", "thumbnail": "thumb.png"}
    base.update(meta)
    (d / "session.json").write_text(json.dumps(base))
    (d / "index.html").write_text("<!doctype html><title>x</title>")
    (d / "thumb.png").write_bytes(PNG_1PX)
    (d / "NOTES.md").write_text(f"# {folder}\n\nSome *notes*.\n")
    return d


class Workspace:
    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / "sessions").mkdir()
        return self.root

    def __exit__(self, *exc):
        self._tmp.cleanup()


class LoadAndValidate(unittest.TestCase):
    def test_minimal_session_loads_with_logline_fallback(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", summary="First sentence here. Then more.")
            sessions, errors, _ = bh.load_sessions(root)
            self.assertEqual(errors, [])
            self.assertEqual(sessions[0]["_logline"], "First sentence here.")
            self.assertEqual(sessions[0]["_n"], 1)

    def test_explicit_logline_wins(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", logline="A short line.")
            sessions, _, _ = bh.load_sessions(root)
            self.assertEqual(sessions[0]["_logline"], "A short line.")

    def test_long_logline_warns(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", logline="x" * 200)
            _, errors, warnings = bh.load_sessions(root)
            self.assertEqual(errors, [])
            self.assertTrue(any("logline" in w for w in warnings))

    def test_fallback_logline_is_trimmed_at_a_word(self):
        long = " ".join(["word"] * 80) + "."
        line = bh.first_sentence(long, limit=60)
        self.assertLessEqual(len(line), 61)
        self.assertTrue(line.endswith("…"))
        self.assertFalse(line[:-1].endswith(" "))

    def test_bad_palette_colour_is_an_error(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", palette={"bg": "red", "ink": "#000000", "accent": "#ffffff"})
            _, errors, _ = bh.load_sessions(root)
            self.assertTrue(any("palette" in e for e in errors))

    def test_palette_with_dark_override(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", palette={
                "bg": "#ffffff", "ink": "#111111", "accent": "#aa3300",
                "dark": {"bg": "#000000", "ink": "#eeeeee", "accent": "#ff8855"}})
            sessions, errors, _ = bh.load_sessions(root)
            self.assertEqual(errors, [])
            p = sessions[0]["_palette"]
            self.assertEqual(p["light"]["accent"], "#aa3300")
            self.assertEqual(p["dark"]["accent"], "#ff8855")

    def test_palette_without_dark_uses_same_colours(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", palette={"bg": "#101010", "ink": "#eeeeee", "accent": "#d9ac52"})
            sessions, _, _ = bh.load_sessions(root)
            p = sessions[0]["_palette"]
            self.assertEqual(p["light"], p["dark"])

    def test_font_stylesheet_must_be_google_fonts(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", font={"display": "Cinzel, serif",
                                                     "stylesheet": "https://evil.example/x.css"})
            _, errors, _ = bh.load_sessions(root)
            self.assertTrue(any("font" in e for e in errors))

    def test_font_stack_cannot_break_out_of_css(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", font={"display": "x; } body { display:none"})
            _, errors, _ = bh.load_sessions(root)
            self.assertTrue(any("font" in e for e in errors))

    def test_builds_on_unknown_folder_warns_and_is_dropped(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", builds_on=["2025-12-31-nope"])
            sessions, errors, warnings = bh.load_sessions(root)
            self.assertEqual(errors, [])
            self.assertEqual(sessions[0]["_builds_on"], [])
            self.assertTrue(any("builds_on" in w for w in warnings))

    def test_builds_on_links_both_ways(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a")
            make_session(root, "2026-01-03-b", builds_on=["2026-01-02-a"])
            sessions, _, _ = bh.load_sessions(root)
            a, b = sessions
            self.assertEqual([s["_n"] for s in b["_builds_on"]], [1])
            self.assertEqual([s["_n"] for s in a["_continued_in"]], [2])

    def test_paths_outside_the_folder_are_dropped(self):
        with Workspace() as root:
            (root / "secret.md").write_text("private")
            make_session(root, "2026-01-02-a", notes="../../secret.md")
            sessions, _, warnings = bh.load_sessions(root)
            self.assertIsNone(sessions[0].get("notes"))
            self.assertTrue(any("notes" in w for w in warnings))

    def test_missing_hero_file_warns(self):
        with Workspace() as root:
            make_session(root, "2026-01-02-a", hero="hero.png")
            sessions, _, warnings = bh.load_sessions(root)
            self.assertIsNone(sessions[0].get("hero"))
            self.assertTrue(any("hero" in w for w in warnings))


class Almanac(unittest.TestCase):
    def test_cells_are_lit_dim_or_outside(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a")
            make_session(root, "2026-10-01-b")
            sessions, _, _ = bh.load_sessions(root)
            months = bh.almanac_months(sessions, today=dt.date(2026, 10, 3))
            self.assertEqual([(m["year"], m["month"]) for m in months], [(2026, 9), (2026, 10)])
            sep, oct_ = months
            self.assertEqual(len(sep["cells"]), 30)
            self.assertEqual(sep["cells"][27]["state"], "out")      # 28 Sep, before the first session
            self.assertEqual(sep["cells"][28]["state"], "lit")      # 29 Sep
            self.assertEqual(sep["cells"][29]["state"], "night")    # 30 Sep, no session
            self.assertEqual(oct_["cells"][0]["state"], "lit")
            self.assertEqual(oct_["cells"][2]["state"], "night")    # 3 Oct is today
            self.assertEqual(oct_["cells"][3]["state"], "out")      # the future

    def test_limit_keeps_most_recent_months(self):
        with Workspace() as root:
            make_session(root, "2026-01-05-a")
            sessions, _, _ = bh.load_sessions(root)
            months = bh.almanac_months(sessions, today=dt.date(2026, 10, 3), limit=6)
            self.assertEqual([m["month"] for m in months], [5, 6, 7, 8, 9, 10])

    def test_two_sessions_one_night(self):
        with Workspace() as root:
            make_session(root, "2026-01-05-a")
            make_session(root, "2026-01-05-b")
            sessions, _, _ = bh.load_sessions(root)
            cell = bh.almanac_months(sessions, today=dt.date(2026, 1, 5))[0]["cells"][4]
            self.assertEqual(len(cell["sessions"]), 2)


class Site(unittest.TestCase):
    def build(self, root, mode="local", today=dt.date(2026, 10, 3)):
        sessions, errors, _ = bh.load_sessions(root)
        self.assertEqual(errors, [])
        return bh.build_site(sessions, mode=mode, today=today)

    def test_local_build_writes_the_expected_files(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a")
            files = self.build(root)
            for name in ("index.html", "archive.html", "archive-2026.html", "threads.html",
                         "catalogue.json", "llms.txt"):
                self.assertIn(name, files)
            self.assertNotIn("feed.xml", files)

    def test_public_build_adds_feed_and_hides_private_links(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a", artifact_url="https://claude.ai/artifact/abc")
            local, public = self.build(root, "local"), self.build(root, "public")
            self.assertIn("claude.ai/artifact/abc", local["index.html"])
            self.assertNotIn("claude.ai/artifact/abc", public["index.html"])
            self.assertIn("feed.xml", public)
            self.assertIn("NOTES.md", local["index.html"])
            self.assertIn("notes.html", public["index.html"])
            self.assertNotIn("NOTES.md\"", public["index.html"])

    def test_newest_session_is_in_the_window_and_others_on_the_shelf(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-old", title="Old One")
            make_session(root, "2026-10-01-new", title="New One",
                         palette={"bg": "#16110d", "ink": "#ece4d5", "accent": "#d9ac52"})
            html = self.build(root)["index.html"]
            window = html.split('class="window"', 1)[1].split("</section>", 1)[0]
            self.assertIn("New One", window)
            self.assertNotIn("Old One", window)
            self.assertIn("#d9ac52", window)
            self.assertIn("Old One", html.split('class="shelf"', 1)[1])

    def test_shelf_holds_at_most_nine(self):
        with Workspace() as root:
            for day in range(1, 15):
                make_session(root, f"2026-03-{day:02d}-s")
            html = self.build(root)["index.html"]
            shelf = html.split('class="shelf"', 1)[1]
            self.assertEqual(shelf.count('class="card"'), 9)

    def test_archive_splits_by_year_with_stable_names(self):
        with Workspace() as root:
            make_session(root, "2025-12-30-a", title="Last Year")
            make_session(root, "2026-01-02-b", title="This Year")
            files = self.build(root, today=dt.date(2026, 1, 3))
            self.assertIn("archive-2025.html", files)
            self.assertIn("archive-2026.html", files)
            self.assertIn("This Year", files["archive.html"])
            self.assertNotIn("Last Year</a>", files["archive.html"])
            self.assertIn("Last Year", files["archive-2025.html"])
            self.assertIn('href="archive-2025.html"', files["archive.html"])

    def test_catalogue_is_newest_first_and_complete(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a", open_threads=["Why?"], tags=["maths"])
            make_session(root, "2026-09-30-b")
            cat = json.loads(self.build(root, "public")["catalogue.json"])
            self.assertEqual(cat["count"], 2)
            self.assertEqual([s["n"] for s in cat["sessions"]], [2, 1])
            first = cat["sessions"][1]
            self.assertEqual(first["open_threads"], ["Why?"])
            self.assertTrue(first["url"].startswith(bh.SITE_URL))

    def test_titles_are_escaped(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a", title="<script>alert(1)</script>")
            html = self.build(root)["index.html"]
            self.assertNotIn("<script>alert(1)", html)
            self.assertIn("&lt;script&gt;", html)

    def test_threads_page_lists_every_thread(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a", open_threads=["First question", "Second question"])
            make_session(root, "2026-09-30-b", open_threads=["Third question"])
            page = self.build(root)["threads.html"]
            for q in ("First question", "Second question", "Third question"):
                self.assertIn(q, page)
            self.assertIn('id="thread-1-2"', page)


class Brief(unittest.TestCase):
    def test_brief_is_one_line_per_session(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a", logline="Line A.")
            make_session(root, "2026-09-30-b", logline="Line B.")
            sessions, _, _ = bh.load_sessions(root)
            text = bh.brief_text(sessions)
            body = [l for l in text.splitlines() if l.strip()][1:]
            self.assertEqual(len(body), 2)
            self.assertIn("Line B.", body[0])   # newest first


try:
    import publish as pb  # noqa: E402
except ImportError as e:  # markdown-it-py missing: run with .venv python
    pb = None
    PUBLISH_SKIP = str(e)


@unittest.skipIf(pb is None, "publish.py needs .venv (markdown-it-py)")
class Publish(unittest.TestCase):
    def test_junk_is_skipped(self):
        for rel in ("__pycache__/x.pyc", "a/.DS_Store", "libtopple.dylib", "x.so", ".hidden", "img/.cache/y"):
            self.assertTrue(pb.should_skip(Path(rel), []), rel)
        for rel in ("index.html", "img/identity.npy", "logs/run.log", "page/app.js"):
            self.assertFalse(pb.should_skip(Path(rel), []), rel)

    def test_publishignore_patterns(self):
        self.assertTrue(pb.should_skip(Path("big/data.bin"), ["big/*"]))
        self.assertTrue(pb.should_skip(Path("raw/deep/big.bin"), ["raw/"]))
        self.assertTrue(pb.should_skip(Path("secret/a.txt"), ["secret"]))
        self.assertFalse(pb.should_skip(Path("secrets.txt"), ["secret"]))
        self.assertTrue(pb.should_skip(Path("x/huge.npy"), ["*.npy"]))
        self.assertFalse(pb.should_skip(Path("small.json"), ["*.npy"]))

    def test_redact_paths(self):
        home, root = FAKE_HOME, FAKE_HOME + "/Developer/claudes-space"
        text = f"run {root}/.venv/bin/python x.py; see {home}/Desktop"
        out = pb.redact(text, home=home)
        self.assertIn("run ~/Developer/claudes-space/.venv/bin/python x.py", out)
        self.assertIn("~/Desktop", out)
        self.assertNotIn(FAKE_HOME, out)

    def test_scan_finds_deny_patterns_and_secrets(self):
        hits = pb.scan("contact me at someone@example.org", ["someone@example.org"])
        self.assertEqual(len(hits), 1)
        self.assertTrue(pb.scan("token gho_" + "a" * 36, []))
        self.assertTrue(pb.scan("-----BEGIN OPENSSH " + "PRIVATE KEY-----", []))
        self.assertTrue(pb.scan(f"path {FAKE_HOME}/x", []))
        self.assertFalse(pb.scan("an ordinary sentence about sandpiles", []))

    def test_stage_copies_sessions_and_renders_notes(self):
        with Workspace() as root:
            d = make_session(root, "2026-09-29-a")
            (d / "__pycache__").mkdir()
            (d / "__pycache__" / "x.pyc").write_bytes(b"\0")
            (d / "data.npy").write_bytes(b"\x93NUMPY")
            (d / "script.py").write_text(f"PY = '{root}/.venv/bin/python'\n")
            sessions, _, _ = bh.load_sessions(root)
            dest = root / ".site"
            dest.mkdir()
            pb.stage(sessions, root=root, dest=dest, home=str(root.parent), today=dt.date(2026, 10, 3))
            s = dest / "sessions" / "2026-09-29-a"
            self.assertTrue((s / "index.html").exists())
            self.assertTrue((s / "data.npy").exists())
            self.assertFalse((s / "__pycache__").exists())
            self.assertIn("<em>notes</em>", (s / "notes.html").read_text())
            self.assertNotIn(str(root.parent), (s / "script.py").read_text())
            for name in ("index.html", "archive.html", "threads.html", "feed.xml", "llms.txt",
                         "catalogue.json", ".nojekyll", "README.md"):
                self.assertTrue((dest / name).exists(), name)

    def test_clear_only_touches_the_site_folder(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a")
            with self.assertRaises(pb.PublishError):
                pb.clear(root / "sessions", root)
            with self.assertRaises(pb.PublishError):
                pb.clear(root, root)
            self.assertTrue((root / "sessions" / "2026-09-29-a" / "session.json").exists())
            site = root / ".site"
            (site / ".git").mkdir(parents=True)
            (site / "old.html").write_text("x")
            pb.clear(site, root)
            self.assertEqual([p.name for p in site.iterdir()], [".git"])

    def stage(self, root, deny=None):
        if deny:
            (root / ".publish-deny").write_text("\n".join(deny) + "\n")
        sessions, _, _ = bh.load_sessions(root)
        dest = root / ".site"
        dest.mkdir(exist_ok=True)
        pb.stage(sessions, root=root, dest=dest, home=str(root.parent), today=dt.date(2026, 10, 3))
        return dest

    def test_any_suffix_is_redacted_and_scanned(self):
        with Workspace() as root:
            d = make_session(root, "2026-09-29-a")
            (d / "Makefile").write_text(f"run:\n\t{root}/.venv/bin/python x.py\n")
            s = self.stage(root) / "sessions" / "2026-09-29-a"
            self.assertNotIn(str(root.parent), (s / "Makefile").read_text())
            (d / "analysis.ipynb").write_text('{"cells": ["mail someone@example.org"]}')
            with self.assertRaises(pb.PublishError):
                self.stage(root, deny=["someone@example.org"])

    def test_non_utf8_text_is_still_scanned(self):
        with Workspace() as root:
            d = make_session(root, "2026-09-29-a")
            (d / "latin.txt").write_bytes("caf\xe9 someone@example.org".encode("latin-1"))
            with self.assertRaises(pb.PublishError):
                self.stage(root, deny=["someone@example.org"])

    def test_symlinks_are_not_followed(self):
        with Workspace() as root:
            d = make_session(root, "2026-09-29-a")
            outside = root.parent / f"outside-{root.name}.txt"
            outside.write_text("not for publishing")
            try:
                (d / "linked").symlink_to(outside)
                s = self.stage(root) / "sessions" / "2026-09-29-a"
                self.assertFalse((s / "linked").exists())
            finally:
                outside.unlink()

    def test_symlinked_site_is_not_cleared(self):
        with Workspace() as root:
            other = root / "elsewhere"
            other.mkdir()
            (other / "precious.txt").write_text("keep me")
            (root / ".site").symlink_to(other)
            with self.assertRaises(pb.PublishError):
                pb.clear(root / ".site", root)
            self.assertTrue((other / "precious.txt").exists())

    def test_staging_twice_gives_identical_files(self):
        with Workspace() as root:
            make_session(root, "2026-09-29-a")
            sessions, _, _ = bh.load_sessions(root)
            outs = []
            for name in ("one", "two"):
                dest = Path(tempfile.mkdtemp(prefix=name))
                pb.stage(sessions, root=root, dest=dest, home=str(root.parent))
                outs.append({p.relative_to(dest): p.read_bytes() for p in dest.rglob("*") if p.is_file()})
            self.assertEqual(outs[0], outs[1])

    def test_stage_refuses_oversized_files(self):
        with Workspace() as root:
            d = make_session(root, "2026-09-29-a")
            with open(d / "huge.bin", "wb") as f:
                f.truncate(pb.MAX_FILE_BYTES + 1)
            sessions, _, _ = bh.load_sessions(root)
            dest = root / ".site"
            dest.mkdir()
            with self.assertRaises(pb.PublishError):
                pb.stage(sessions, root=root, dest=dest, home=str(root.parent), today=dt.date(2026, 10, 3))


if __name__ == "__main__":
    unittest.main()
