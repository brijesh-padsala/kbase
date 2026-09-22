"""Exercise doctor/check/update on installed copies in real scratch repositories."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

BASE = Path(__file__).resolve().parents[1]
CLI = BASE / "bin/kbase"


@unittest.skipUnless(shutil.which("git"), "git is required")
class InstalledTools(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "project"
        self.root.mkdir()
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", KSEARCH_NO_LOG="1")
        self.git("init")
        (self.root / "README.md").write_text("# Project\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("-c", "user.name=test", "-c", "user.email=test@example.com", "commit", "-m", "init")
        result = self.cli("init", "--mode", "greenfield", "--agents", "codex,claude", "--workflow")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True, check=True)

    def cli(self, command, *args):
        return subprocess.run([sys.executable, str(CLI), command, str(self.root), *args], env=self.env, capture_output=True, text=True)

    def manifest(self):
        return json.loads((self.root / ".kbase.json").read_text(encoding="utf-8"))

    def save_manifest(self, data):
        (self.root / ".kbase.json").write_text(json.dumps(data), encoding="utf-8")

    def snapshot(self):
        return {p.relative_to(self.root).as_posix(): p.read_bytes() for p in self.root.rglob("*") if p.is_file() and ".git" not in p.relative_to(self.root).parts}

    def older_install(self):
        rel = "scripts/ksearch.py"
        data = (self.root / rel).read_bytes() + b"\n# Older generated version.\n"
        (self.root / rel).write_bytes(data)
        manifest = self.manifest()
        manifest["managed_files"][rel] = hashlib.sha256(data).hexdigest()
        manifest["template_version"] = "0.1.0"
        self.save_manifest(manifest)
        return rel

    def test_doctor_is_read_only_and_distinguishes_warnings(self):
        before = self.snapshot()
        result = self.cli("doctor", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertTrue(any(c["level"] == "WARN" and "placeholders" in c["message"] for c in report["checks"]))
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.cli("doctor", "--strict").returncode, 1)

    def test_full_check_rejects_unstaged_invalid_note(self):
        self.assertEqual(self.cli("check").returncode, 0)
        (self.root / "knowledge/docs/bad.md").write_text("# No summary or incoming link\n", encoding="utf-8")
        result = self.cli("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad.md", result.stdout)

    def test_installed_doctor_does_not_create_bytecode_without_environment_override(self):
        env = dict(self.env)
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts/kbase-doctor.py")],
            cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_missing_adapter_fails_doctor(self):
        (self.root / ".claude/skills/kb-review/SKILL.md").unlink()
        result = self.cli("doctor", "--json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("kb-review", result.stdout)

    def test_missing_source_directory_fails_doctor(self):
        manifest = self.manifest()
        manifest["source_roots"] = ["gone"]
        self.save_manifest(manifest)
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("source directory is missing", result.stdout)

    def test_search_failure_is_not_treated_as_no_matches(self):
        (self.root / "scripts/ksearch.py").write_text("raise SystemExit(1)\n", encoding="utf-8")
        result = self.cli("doctor")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Search script failed", result.stdout)

    def test_update_preview_is_read_only_then_apply_preserves_knowledge(self):
        rel = self.older_install()
        knowledge = self.root / "knowledge/docs/architecture.md"
        knowledge.write_text(knowledge.read_text(encoding="utf-8") + "\nPersonal architecture note.\n", encoding="utf-8")
        before = self.snapshot()
        preview = self.cli("update")
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        self.assertIn("Older generated version", preview.stdout)
        self.assertEqual(before, self.snapshot())
        applied = self.cli("update", "--apply")
        self.assertEqual(applied.returncode, 0, applied.stdout + applied.stderr)
        after = self.snapshot()
        changed = {p for p in before if before[p] != after[p]}
        self.assertEqual(changed, {rel, ".kbase.json"})
        self.assertEqual(after[rel], (BASE / "template" / rel).read_bytes())
        self.assertIn("Already current", self.cli("update", "--apply").stdout)

    def test_local_edit_blocks_entire_update(self):
        self.older_install()
        (self.root / "scripts/kbformat.py").write_text("# Local edit\n", encoding="utf-8")
        before = self.snapshot()
        result = self.cli("update", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("CONFLICT", result.stdout)
        self.assertEqual(before, self.snapshot())

    def test_local_deletion_is_preserved(self):
        (self.root / "scripts/ksearch.py").unlink()
        result = self.cli("update", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertFalse((self.root / "scripts/ksearch.py").exists())

    def test_file_ancestor_blocks_update_before_other_files_change(self):
        self.older_install()
        manifest = self.manifest()
        del manifest["managed_files"][".agents/skills/kb-handoff/SKILL.md"]
        self.save_manifest(manifest)
        parent = self.root / ".agents/skills/kb-handoff"
        shutil.rmtree(parent)
        parent.write_text("A user-owned file occupies this path.\n", encoding="utf-8")
        before = self.snapshot()
        for args in ((), ("--apply",)):
            result = self.cli("update", *args)
            self.assertEqual(result.returncode, 1)
            self.assertIn("not a directory", result.stderr)
            self.assertEqual(before, self.snapshot())

    def test_manifest_cannot_make_update_write_knowledge(self):
        manifest = self.manifest()
        rel = "knowledge/docs/architecture.md"
        manifest["managed_files"][rel] = hashlib.sha256((self.root / rel).read_bytes()).hexdigest()
        self.save_manifest(manifest)
        before = self.snapshot()
        result = self.cli("update", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unsupported managed file", result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_manifest_path_traversal_and_symlinks_are_rejected(self):
        original = self.manifest()
        manifest = dict(original, managed_files={"../outside": "0" * 64})
        self.save_manifest(manifest)
        self.assertEqual(self.cli("update", "--apply").returncode, 1)
        self.save_manifest(original)
        script = self.root / "scripts/ksearch.py"
        script.unlink()
        outside = Path(self.temp.name) / "outside.py"
        outside.write_text("# Preserve me\n", encoding="utf-8")
        script.symlink_to(outside)
        result = self.cli("update", "--apply")
        self.assertEqual(result.returncode, 1)
        self.assertIn("symlink", result.stderr)
        self.assertEqual(outside.read_text(encoding="utf-8"), "# Preserve me\n")

    def test_malformed_manifest_reports_without_traceback(self):
        (self.root / ".kbase.json").write_text("{broken", encoding="utf-8")
        for command in ("doctor", "update"):
            result = self.cli(command)
            self.assertEqual(result.returncode, 1)
            self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
