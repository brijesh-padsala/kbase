"""ksearch tests — the pure scoring seam and the unified file scope."""

import contextlib
import io
import json
import os
import subprocess
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

    def test_flag_spelling_matches_ordinary_query(self):
        self.assertEqual(ksearch.tokenize("--callers --impact"), ["callers", "impact"])
        ranked, _ = ksearch.score(["callers"], {"commands.md": note(tldr="code tools", body="ripwire --callers=Widget")})
        self.assertEqual(ranked[0][1], "commands.md")

    def test_real_template_title_queries_find_the_canonical_note(self):
        root = Path(__file__).resolve().parents[1] / "template/knowledge"
        docs = {
            str(path.relative_to(root)).removesuffix(".tmpl"): path.read_text(encoding="utf-8")
            for path in root.rglob("*") if path.is_file() and path.name.endswith((".md", ".md.tmpl"))
            and "artifacts" not in path.parts
        }
        for query, target in (("new agent onboarding", "rules/new-agent-onboarding.md"), ("kb-handoff", "practices/skills/kb-handoff.md")):
            ranked, _ = ksearch.score(ksearch.tokenize(query), docs)
            self.assertEqual(ranked[0][1], target, query)


class Passages(unittest.TestCase):
    def candidate(self, text, query="needle"):
        return {"score": 1.0, "file": "docs/evidence.md", "description": "",
                "passage": ksearch.select_passage(text, ksearch.tokenize(query))}

    def test_prefers_matching_prose_to_yaml_and_toc(self):
        text = (
            "---\ndescription: needle needle needle\n---\n# Guide\n"
            "1. [needle needle](#needle)\n\n## Evidence\n"
            "The needle is stored here.\nA follow-up detail.\n"
        )
        row = ksearch.result_row(self.candidate(text))
        self.assertEqual((row["line_start"], row["line_end"]), (8, 9))
        self.assertEqual(row["heading"], "Evidence")
        self.assertEqual(row["excerpt"], "The needle is stored here.\nA follow-up detail.")
        self.assertFalse(row["truncated"])

    def test_description_only_match_has_an_honest_source_citation(self):
        text = "---\ndescription: needle\n---\n# Guide\nUnrelated content.\n"
        row = ksearch.result_row(self.candidate(text))
        self.assertEqual(row["line_start"], 2)
        self.assertIn("needle", row["excerpt"])

    def test_clipping_preserves_a_late_match_and_valid_unicode(self):
        text = "# Evidence\n" + "🙂" * 500 + "needle" + "🔥" * 500 + "\n"
        row = ksearch.result_row(self.candidate(text), excerpt_bytes=80)
        self.assertIn("needle", row["excerpt"])
        self.assertLessEqual(len(row["excerpt"].encode("utf-8")), 80)
        self.assertEqual((row["line_start"], row["line_end"]), (2, 2))
        self.assertTrue(row["excerpt"].startswith("…"))
        self.assertTrue(row["excerpt"].endswith("…"))
        self.assertTrue(row["truncated"])

    def test_citations_track_shortened_multiline_passage(self):
        text = "# Evidence\nneedle\n" + "large context " * 100 + "\nMore context.\n"
        row = ksearch.result_row(self.candidate(text), excerpt_bytes=40)
        self.assertEqual((row["line_start"], row["line_end"]), (2, 3))
        self.assertIn("needle", row["excerpt"])
        self.assertTrue(row["truncated"])

    def test_query_in_a_heading_stays_retrievable(self):
        row = ksearch.result_row(self.candidate("# needle\n> **TL;DR:** a useful note\n"))
        self.assertEqual(row["line_start"], 1)
        self.assertEqual(row["heading"], "needle")
        self.assertIn("needle", row["excerpt"])

    def test_rendered_description_and_heading_are_bounded(self):
        candidate = self.candidate("# " + "界" * 500 + "\nneedle\n")
        candidate["description"] = "界" * 500
        row = ksearch.result_row(candidate)
        self.assertLessEqual(len(row["description"].encode()), 160)
        self.assertLessEqual(len(row["heading"].encode()), 120)
        self.assertTrue(row["truncated"])

    def test_substrings_cannot_displace_a_matching_token(self):
        text = (
            "# Session setup\n> **TL;DR:** auth uses signed sessions.\n\n"
            "An authoritative author describes authentication adapters.\n"
        )
        row = ksearch.result_row(self.candidate(text, "auth"))
        self.assertEqual(row["line_start"], 2)
        self.assertIn("auth uses signed sessions", row["excerpt"])

    def test_flag_matches_use_the_same_normalization_as_scoring(self):
        text = "# Commands\nRun ripwire --callers=Widget for this symbol.\n"
        row = ksearch.result_row(self.candidate(text, "callers"))
        self.assertEqual(row["line_start"], 2)
        self.assertIn("--callers", row["excerpt"])


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


class SearchBudgets(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.script = Path(__file__).resolve().parents[1] / "template/scripts/ksearch.py"
        self.env = dict(os.environ, KB_ROOT=str(self.root), KSEARCH_NO_LOG="1", PYTHONDONTWRITEBYTECODE="1")
        for i in range(7):
            (self.root / f"note-{i}.md").write_text(
                f"# Evidence {i}\n> **TL;DR:** Background details.\n\n"
                + "🙂" * 500 + "needle" + "界" * 500 + "\n",
                encoding="utf-8",
            )

    def run_cli(self, *args, env=None):
        return subprocess.run(
            [sys.executable, "-B", str(self.script), *args],
            env=env or self.env, capture_output=True, text=True,
        )

    def test_default_budget_covers_utf8_metadata_and_final_newline(self):
        for mode in ([], ["--json"]):
            with self.subTest(mode=mode):
                result = self.run_cli("needle", *mode)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLessEqual(len(result.stdout.encode("utf-8")), 2400)
                self.assertTrue(result.stdout.endswith("\n"))
                self.assertIn("budget omitted", result.stderr)
                if mode:
                    rows = json.loads(result.stdout)
                    self.assertGreater(len(rows), 0)
                    self.assertLess(len(rows), 5)
                    for row in rows:
                        self.assertIn("needle", row["excerpt"])
                        self.assertEqual((row["line_start"], row["line_end"]), (4, 4))
                        self.assertTrue(row["truncated"])
                        self.assertTrue(row["heading"].startswith("Evidence"))
                else:
                    self.assertIn(".md:4-4", result.stdout)
                    self.assertIn("[truncated]", result.stdout)

    def test_budget_sweep_never_breaks_json_or_discards_the_matching_term(self):
        for budget in (1, 80, 180, 240, 300, 501, 1024, 2400):
            with self.subTest(budget=budget):
                result = self.run_cli("--json", "--max-bytes", str(budget), "--", "needle")
                if result.returncode == 2:
                    self.assertEqual(result.stdout, "")
                    self.assertIn("top citation", result.stderr)
                    self.assertNotIn("no matches", result.stderr)
                    continue
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertLessEqual(len(result.stdout.encode("utf-8")), budget)
                rows = json.loads(result.stdout)
                self.assertGreater(len(rows), 0)
                for row in rows:
                    self.assertIn("needle", row["excerpt"])

    def test_unbounded_output_keeps_requested_count_and_valid_citations(self):
        result = self.run_cli("needle", "--json", "--max-bytes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = json.loads(result.stdout)
        self.assertEqual(len(rows), 5)
        self.assertGreater(len(result.stdout.encode()), 2400)
        self.assertEqual(result.stderr, "")
        docs = ksearch.read_docs(ksearch.list_md_files(None, root=str(self.root)))
        ranked, _ = ksearch.score(["needle"], docs)
        self.assertEqual([r["file"] for r in rows], [Path(p).name for _, p in ranked[:5]])

    def test_json_no_hit_is_an_empty_array(self):
        result = self.run_cli("unfindableword", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), [])
        self.assertEqual(result.stderr, "")

    def test_json_empty_scope_and_stopwords_still_emit_arrays(self):
        for args in (("needle", "--dir", "missing"), ("the",)):
            result = self.run_cli(*args, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout), [])

    def test_no_hit_paths_honor_even_tiny_budgets(self):
        for args in (("unfindableword",), ("needle", "--dir", "missing"), ("the",)):
            with self.subTest(args=args):
                result = self.run_cli(*args, "--json", "--max-bytes", "1")
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertIn("--max-bytes too small", result.stderr)
                fitting = self.run_cli(*args, "--json", "--max-bytes", "3")
                self.assertEqual(fitting.returncode, 1)
                self.assertEqual(fitting.stdout, "[]\n")
        human = self.run_cli("unfindableword", "--max-bytes", "1")
        self.assertEqual(human.returncode, 2)
        self.assertEqual(human.stdout, "")

    def test_negative_budget_is_an_argument_error(self):
        result = self.run_cli("needle", "--max-bytes", "-1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("must be nonnegative", result.stderr)

    def test_query_log_records_matches_before_limit(self):
        env = dict(self.env)
        env.pop("KSEARCH_NO_LOG")
        result = self.run_cli("needle", "--limit", "2", "--max-bytes", "0", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / "_ksearch-log.tsv").read_text().strip().split("\t")[-1], "7")

    def test_unbounded_mode_handles_matching_terms_longer_than_excerpt_default(self):
        query = "x" * 1000
        (self.root / "long-term.md").write_text(note(tldr=query), encoding="utf-8")
        result = self.run_cli(query, "--json", "--max-bytes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(query, json.loads(result.stdout)[0]["excerpt"])


if __name__ == "__main__":
    unittest.main()
