"""Exercise evaluator validation, real retrieval output, and exit contracts."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


REPO = Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "template" / "scripts"


class RetrievalEvaluation(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / "knowledge"
        self.root.mkdir()
        (self.root / "rules").mkdir()
        (self.root / "rules" / "deploy.md").write_text(
            "# Deployment\n\n> **TL;DR:** Deployment uses canary validation.\n\n"
            "## Canary\n\nCheck canary probes before deployment.\n", encoding="utf-8"
        )
        (self.root / "rules" / "other.md").write_text(
            "# Formatter\n\n> **TL;DR:** Formatting uses a formatter.\n", encoding="utf-8"
        )
        self.cases = self.base / "cases.jsonl"
        self.script = SCRIPTS / "ksearch-eval.py"

    def tearDown(self):
        self.temp.cleanup()

    def run_eval(self, cases, *arguments):
        self.cases.write_text("\n".join(json.dumps(case) for case in cases) + "\n", encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-B", str(self.script), str(self.cases), "--root", str(self.root), "--json", *arguments],
            cwd=self.base, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True, text=True,
        )

    def fake_search(self, code):
        scripts = self.base / "scripts"
        scripts.mkdir()
        for name in ("ksearch-eval.py", "kbformat.py", "ksearch.py"):
            shutil.copy2(SCRIPTS / name, scripts / name)
        # Keep the real importable scoring implementation but replace the CLI
        # entry point to test malformed runtime output and diagnostic accounting.
        path = scripts / "ksearch.py"
        source = path.read_text()
        source = source[:source.index('if __name__ == "__main__":')] + 'if __name__ == "__main__":\n' + code
        path.write_text(source)
        self.script = scripts / "ksearch-eval.py"

    def test_positive_and_no_answer_metrics_and_no_mutation(self):
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        result = self.run_eval([
            {"id": "deploy", "query": "canary", "relevant": ["rules/deploy.md"], "dir": "rules"},
            {"id": "absent", "query": "axolotl", "relevant": []},
        ])
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["summary"]["passed"], 2)
        self.assertEqual(report["summary"]["raw_mrr"], 1)
        self.assertEqual(report["summary"]["displayed_recall_at_limit"], 1)
        self.assertEqual(report["summary"]["abstention_rate"], 1)
        self.assertIn("heuristic", report["token_estimate"])
        self.assertEqual(len(report["corpus_sha256"]), 64)
        after = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_quality_miss_and_unexpected_hits_exit_one(self):
        result = self.run_eval([
            {"query": "canary", "relevant": ["rules/other.md"]},
            {"query": "canary", "relevant": []},
        ])
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["summary"]["passed"], 0)
        self.assertEqual(report["summary"]["raw_mrr"], 0)
        self.assertEqual(report["summary"]["abstention_rate"], 0)

    def test_symlink_resolves_search_beside_the_real_evaluator(self):
        alias = self.base / "evaluate"
        alias.symlink_to(self.script)
        self.script = alias
        result = self.run_eval([{"query": "canary", "relevant": ["rules/deploy.md"]}])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["summary"]["passed"], 1)

    def test_fixture_validation_rejects_invalid_cases(self):
        (self.root / "archive").mkdir()
        (self.root / "archive" / "old.md").write_text("# Old canary\n")
        (self.root / "_private.md").write_text("# Private canary\n")
        invalid = [
            {"relevant": []},
            {"query": "the", "relevant": []},
            {"query": "canary"},
            {"query": "canary", "relevant": "rules/deploy.md"},
            {"query": "canary", "relevant": ["missing.md"]},
            {"query": "canary", "relevant": ["../outside.md"]},
            {"query": "canary", "relevant": ["archive/old.md"]},
            {"query": "canary", "relevant": ["_private.md"]},
            {"query": "canary", "relevant": ["rules/deploy.md"], "dir": "missing"},
            {"query": "canary", "relevant": [], "dir": "archive"},
            {"query": "canary", "relevant": [], "dir": "../"},
            {"query": "canary", "relevant": [], "id": 3},
        ]
        for case in invalid:
            with self.subTest(case=case):
                result = self.run_eval([case])
                self.assertEqual(result.returncode, 2)
                self.assertIn("ksearch-eval:", result.stderr)
                self.assertEqual(result.stdout, "")

    def test_duplicate_ids_and_empty_fixture_are_errors(self):
        case = {"id": "duplicate", "query": "canary", "relevant": []}
        for rows in ([case, case], []):
            with self.subTest(rows=rows):
                result = self.run_eval(rows)
                self.assertEqual(result.returncode, 2)

    def test_gold_outside_directory_is_invalid(self):
        (self.root / "docs").mkdir()
        result = self.run_eval([{"query": "canary", "relevant": ["rules/deploy.md"], "dir": "docs"}])
        self.assertEqual(result.returncode, 2)
        self.assertIn("outside dir", result.stderr)

    def test_actual_output_bytes_and_budget_are_measured(self):
        result = self.run_eval([{"query": "canary", "relevant": ["rules/deploy.md"]}], "--max-bytes", "500")
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["results"][0]
        actual = subprocess.run(
            [sys.executable, "-B", str(SCRIPTS / "ksearch.py"), "--json", "--max-bytes", "500", "--limit", "5", "canary"],
            cwd=self.root, env=dict(os.environ, KB_ROOT=str(self.root), KSEARCH_NO_LOG="1", PYTHONDONTWRITEBYTECODE="1"),
            capture_output=True,
        )
        self.assertEqual(row["stdout_bytes"], len(actual.stdout))
        self.assertLessEqual(row["stdout_bytes"], 500)
        self.assertEqual(row["total_output_bytes"], len(actual.stdout) + len(actual.stderr))
        self.assertEqual(row["stdout_estimated_tokens"], round(len(actual.stdout.decode()) / 4, 2))

    def test_tiny_budget_is_runtime_error_not_no_answer(self):
        result = self.run_eval([{"query": "canary", "relevant": []}], "--max-bytes", "1")
        self.assertEqual(result.returncode, 2)
        self.assertIn("ksearch failed", result.stderr)

    def test_zero_budget_disables_the_output_cap(self):
        result = self.run_eval([{"query": "canary", "relevant": ["rules/deploy.md"]}], "--max-bytes", "0")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["max_bytes"], 0)
        self.assertGreater(report["results"][0]["stdout_bytes"], 0)

    def test_stderr_is_included_in_total_output_cost(self):
        self.fake_search("    print('[]')\n    print('diagnostic', file=sys.stderr)\n    sys.exit(1)\n")
        result = self.run_eval([{"query": "axolotl", "relevant": []}])
        self.assertEqual(result.returncode, 0, result.stderr)
        row = json.loads(result.stdout)["results"][0]
        self.assertEqual(row["stdout_bytes"], 3)
        self.assertEqual(row["stderr_bytes"], 11)
        self.assertEqual(row["total_output_bytes"], 14)
        self.assertEqual(row["total_estimated_tokens"], 3.5)

    def test_invalid_cli_json_is_runtime_error(self):
        self.fake_search("    print('not JSON')\n")
        result = self.run_eval([{"query": "canary", "relevant": ["rules/deploy.md"]}])
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid JSON", result.stderr)


if __name__ == "__main__":
    unittest.main()
