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

    def context_report(self, *args, env=None):
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts/kbase-doctor.py"), "--context-only", "--json", *args],
            cwd=self.root, env=self.env if env is None else env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_context_inventory_deduplicates_imports_and_stops_cycles(self):
        agents = self.root / "AGENTS.md"
        agents.write_text("# Router\n@docs/context.md\n", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text("@AGENTS.md\n@docs/context.md\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs/context.md").write_text(
            "@../AGENTS.md\n```text\n@missing-fenced.md\n```\n`@missing-inline.md`\n", encoding="utf-8",
        )
        context = self.context_report()["context"]
        files = context["startup"]["files"]
        self.assertEqual({item["path"] for item in files}, {"AGENTS.md", "CLAUDE.md", "docs/context.md"})
        self.assertEqual(len(files), 3)
        self.assertEqual(context["startup"]["totals"]["bytes"], sum((self.root / item["path"]).stat().st_size for item in files))
        self.assertEqual(context["unavailable"], [])

    def test_context_unicode_bytes_and_required_read_are_separate(self):
        text = "# Mémoire 🧠\r\nSecond line\r\n"
        (self.root / "AGENTS.md").write_bytes(text.encode("utf-8"))
        context = self.context_report()["context"]
        agents = next(item for item in context["startup"]["files"] if item["path"] == "AGENTS.md")
        self.assertEqual(agents["bytes"], len(text.encode("utf-8")))
        self.assertEqual(agents["chars"], len(text))
        self.assertEqual(agents["lines"], 2)
        self.assertEqual(agents["estimated_tokens"], (len(text) + 3) // 4)
        self.assertEqual([item["path"] for item in context["required_reads"]["files"]], ["knowledge/INDEX.md"])
        self.assertNotIn("knowledge/INDEX.md", [item["path"] for item in context["startup"]["files"]])
        self.assertIn("not a model tokenizer", context["measurement"])

    def test_context_only_needs_no_shell_tools_and_writes_nothing(self):
        env = dict(self.env, PATH="")
        env.pop("PYTHONDONTWRITEBYTECODE", None)
        before = self.snapshot()
        report = self.context_report(env=env)
        self.assertTrue(report["ok"])
        self.assertIn("runtime checks skipped", report["checks"][0]["message"])
        wrapped = subprocess.run(
            [sys.executable, str(CLI), "doctor", str(self.root), "--context-only", "--json"],
            cwd=self.root, env=env, capture_output=True, text=True,
        )
        self.assertEqual(wrapped.returncode, 0, wrapped.stdout + wrapped.stderr)
        self.assertTrue(json.loads(wrapped.stdout)["ok"])
        self.assertEqual(before, self.snapshot())
        self.assertFalse((self.root / "knowledge/_ksearch-log.tsv").exists())
        self.assertFalse(list(self.root.rglob("__pycache__")))

    def test_context_skips_outside_remote_sensitive_and_symlink_imports(self):
        outside = Path(self.temp.name) / "outside.md"
        outside.write_bytes(b"SECRET CONTENT\xff")  # Decoding this would fail if the guard read it.
        (self.root / "linked.md").symlink_to(outside)
        (self.root / ".env").write_text("SECRET CONTENT", encoding="utf-8")
        (self.root / "CLAUDE.md").write_text(
            "@AGENTS.md\n@../outside.md\n@https://example.test/rules.md\n@.env\n@linked.md\n", encoding="utf-8",
        )
        report = self.context_report()
        unavailable = report["context"]["unavailable"]
        self.assertEqual(len(unavailable), 4)
        self.assertTrue(any("leaves repository" in item["reason"] for item in unavailable))
        self.assertTrue(any("sensitive" in item["reason"] for item in unavailable))
        self.assertTrue(any("symlink" in item["reason"] for item in unavailable))
        self.assertNotIn("SECRET CONTENT", json.dumps(report))
        self.assertNotIn("utf-8", " ".join(item["reason"] for item in unavailable))

    def test_context_metadata_excludes_bodies_and_warns_on_long_descriptions(self):
        stub = self.root / ".agents/skills/kb-handoff/SKILL.md"
        description = "é" * 301  # 602 UTF-8 bytes, despite only 301 characters.
        body = "body material on demand " * 1000
        stub.write_text(f"---\nname: kb-handoff\ndescription: {description}\n---\n{body}\n", encoding="utf-8")
        report = self.context_report()
        context = report["context"]
        metadata = context["skill_metadata"]
        entry = next(item for item in metadata["codex"]["files"] if item["name"] == "kb-handoff")
        self.assertEqual(entry["bytes"], len(("kb-handoff\n" + description + "\n").encode("utf-8")))
        self.assertEqual(entry["description_bytes"], 602)
        self.assertTrue(any(c["level"] == "WARN" and "600-byte" in c["message"] for c in report["checks"]))
        self.assertIn("kb-handoff", context["duplicate_skill_names"])
        self.assertEqual(set(metadata), {"codex", "claude"})
        self.assertNotIn("body material", json.dumps(report))

    def test_context_budget_deduplicates_index_when_also_imported(self):
        (self.root / "AGENTS.md").write_text("x" * 6001 + "\n@knowledge/INDEX.md\n", encoding="utf-8")
        context = self.context_report()
        required = context["context"]["required_reads"]["files"][0]
        self.assertTrue(required["already_in_startup"])
        self.assertEqual(context["context"]["startup"]["totals"]["bytes"], context["context"]["unique_router_and_required_reads"]["bytes"])
        self.assertTrue(any("6000 bytes" in check["message"] for check in context["checks"]))

    def test_context_only_still_rejects_invalid_manifest_and_non_repository(self):
        (self.root / ".kbase.json").write_text("{}", encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(self.root / "scripts/kbase-doctor.py"), "--context-only", "--json"],
            cwd=self.root, env=dict(self.env, PATH=""), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertNotIn("Traceback", result.stderr)
        outside = subprocess.run(
            [sys.executable, str(self.root / "scripts/kbase-doctor.py"), self.temp.name, "--context-only", "--json"],
            cwd=self.root, env=dict(self.env, PATH=""), capture_output=True, text=True,
        )
        self.assertEqual(outside.returncode, 1)
        self.assertIn("repository root", outside.stdout)

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
