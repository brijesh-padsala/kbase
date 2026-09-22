"""ksearch tests — the pure scoring seam and the unified file scope."""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))

import ksearch


def note(tldr="", body="", heading="# Title"):
    return f"{heading}\n> **TL;DR:** {tldr}\n\n{body}\n"


class Score(unittest.TestCase):
    def test_aboutness_beats_passing_mention(self):
        docs = {
            "about.md": note(tldr="auth and sessions", body="filler " * 40),
            "mention.md": note(tldr="filler", body="auth appears here once. " + "other " * 40),
        }
        ranked, _ = ksearch.score(["auth"], docs)
        self.assertEqual(ranked[0][1], "about.md")

    def test_filename_boost(self):
        docs = {
            "auth.md": note(tldr="x", body="auth auth"),
            "other.md": note(tldr="x", body="auth auth"),
        }
        ranked, _ = ksearch.score(["auth"], docs)
        self.assertEqual(ranked[0][1], "auth.md")

    def test_no_match_is_absent_not_zero(self):
        ranked, _ = ksearch.score(["zzz"], {"a.md": note(tldr="t")})
        self.assertEqual(ranked, [])

    def test_descriptions_come_back(self):
        text = "---\ndescription: the auth design\n---\n# T\n> **TL;DR:** t\n"
        _, descs = ksearch.score(["auth"], {"a.md": text})
        self.assertEqual(descs["a.md"], "the auth design")

    def test_limit_is_applied_by_the_caller(self):
        docs = {f"f{i}.md": note(tldr="auth", body="x") for i in range(3)}
        ranked, _ = ksearch.score(["auth"], docs)
        self.assertEqual(len(ranked), 3)
        self.assertEqual(len(ranked[:1]), 1)


class Scope(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        for rel in (
            "rules/keep.md",
            "archive/old.md",
            "plans-archive/old.md",
            "plans/artifacts/notes.md",
            "plans/001-plan.md",
            "_scratch.md",
        ):
            p = os.path.join(self.root, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write("# x\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_scope_excludes_archives_artifacts_and_underscore(self):
        files = ksearch.list_md_files(None, False, self.root)
        rels = {os.path.relpath(f, self.root) for f in files}
        self.assertEqual(rels, {os.path.join("rules", "keep.md"), os.path.join("plans", "001-plan.md")})

    def test_include_archive_widens_retrieval(self):
        files = ksearch.list_md_files(None, True, self.root)
        rels = {os.path.relpath(f, self.root) for f in files}
        self.assertIn(os.path.join("archive", "old.md"), rels)
        self.assertIn(os.path.join("plans", "artifacts", "notes.md"), rels)
        self.assertNotIn("_scratch.md", rels)  # _-files are never indexed


class SearchCli(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        os.makedirs(os.path.join(self.root, "rules"), exist_ok=True)
        with open(os.path.join(self.root, "rules", "auth.md"), "w", encoding="utf-8") as fh:
            fh.write(note(tldr="auth design", body="sessions live here"))

    def tearDown(self):
        self.tmp.cleanup()

    def _run(self, query, env_log_off=True):
        out = io.StringIO()
        env = dict(os.environ, KSEARCH_NO_LOG="1") if env_log_off else os.environ
        old = os.environ
        os.environ = env
        try:
            with contextlib.redirect_stdout(out):
                code = ksearch.search(query, 5, None, False, root=self.root)
        finally:
            os.environ = old
        return code, out.getvalue()

    def test_hit(self):
        code, out = self._run("auth design")
        self.assertEqual(code, 0)
        self.assertIn("auth.md", out)

    def test_no_hit_exit_1(self):
        code, out = self._run("zzznothing")
        self.assertEqual(code, 1)
        self.assertIn("no matches", out)

    def test_query_log_written_unless_disabled(self):
        code, out = self._run("auth design", env_log_off=False)
        self.assertEqual(code, 0)
        log = os.path.join(self.root, "_ksearch-log.tsv")
        self.assertTrue(os.path.exists(log))
        with open(log, encoding="utf-8") as fh:
            line = fh.read().strip()
        self.assertIn("auth design", line)
        self.assertIn("auth.md", line)
        self.assertTrue(line.endswith("\t1"))


if __name__ == "__main__":
    unittest.main()
