"""End-to-end smoke: kbase-init scaffolds a scratch repo, the shipped copies
work together, and the gate really blocks bad staged state.

These tests need git on PATH; everything else is stdlib and tempdirs.
"""

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INIT = REPO / "bin" / "kbase-init"


def git(cwd, *args):
    return subprocess.run(
        ["git", "-c", "user.name=smoke", "-c", "user.email=smoke@example.com", *args],
        cwd=cwd, capture_output=True, text=True,
    )


@unittest.skipUnless(shutil.which("git"), "git not on PATH")
class InitSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "proj"
        self.root.mkdir()
        self.assertEqual(git(self.root, "init").returncode, 0)
        (self.root / "README.md").write_text("# proj\n", encoding="utf-8")
        git(self.root, "add", "-A")
        self.assertEqual(git(self.root, "commit", "-m", "init").returncode, 0)

    def tearDown(self):
        self.tmp.cleanup()

    def _init(self, mode="greenfield", *args, env=None):
        return subprocess.run(
            [sys.executable, str(INIT), "--mode", mode, *args, str(self.root)],
            capture_output=True, text=True, env=env,
        )

    def _gate(self):
        return subprocess.run(
            [sys.executable, str(self.root / "scripts" / "knowledge-gate.py")],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_greenfield_scaffold_verifies_itself(self):
        r = self._init()
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        for rel in ("scripts/kbformat.py", "scripts/ksearch.py", "scripts/knowledge-gate.py", "scripts/kbase-doctor.py", "AGENTS.md"):
            self.assertTrue((self.root / rel).is_file(), rel)

        # The status line the writer produced parses with the shipped reader.
        sys.path.insert(0, str(self.root / "scripts"))
        try:
            import kbformat  # the scratch repo's copy

            text = (self.root / "knowledge" / "README.md").read_text(encoding="utf-8")
            mode, sha = kbformat.parse_status(text)
            self.assertEqual(mode, "VERIFIED")
            self.assertTrue(sha)
        finally:
            sys.path.pop(0)
            sys.modules.pop("kbformat", None)

        # Exercise the actual staged gate, not its no-staged-files shortcut.
        self.assertEqual(git(self.root, "add", "-A").returncode, 0)
        gated = self._gate()
        self.assertEqual(gated.returncode, 0, gated.stdout + gated.stderr)
        self.assertIn("full-tree gate: passed", r.stdout)

    def test_script_collision_fails_before_writing(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        collision = scripts / "ksearch.py"
        collision.write_text("print('project-owned tool')\n", encoding="utf-8")
        result = self._init()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("conflicting scripts/ksearch.py", result.stderr)
        self.assertFalse((self.root / "knowledge").exists())
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertFalse((self.root / ".kbase.json").exists())
        self.assertEqual(collision.read_text(), "print('project-owned tool')\n")

    def test_identical_existing_script_is_managed(self):
        scripts = self.root / "scripts"
        scripts.mkdir()
        shutil.copy2(REPO / "template" / "scripts" / "ksearch.py", scripts / "ksearch.py")
        result = self._init()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.root / ".kbase.json").read_text())
        self.assertIn("scripts/ksearch.py", manifest["managed_files"])

    def test_smoke_ignores_caller_kb_root_and_writes_no_search_log(self):
        # A short project name must not become an unsearchable smoke query.
        self.assertEqual(git(self.root, "remote", "add", "origin", "https://example.invalid/a.git").returncode, 0)
        result = self._init(env=dict(os.environ, KB_ROOT="/does/not/exist", KSEARCH_NO_LOG="0"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ksearch smoke: hits found", result.stdout)
        self.assertFalse((self.root / "knowledge" / "_ksearch-log.tsv").exists())

    def test_force_existing_to_greenfield_removes_unchanged_brief(self):
        self.assertEqual(self._init("existing").returncode, 0)
        result = self._init("greenfield", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "knowledge" / "_bootstrap-brief.md").exists())
        self.assertIn("**KB status:** VERIFIED", (self.root / "knowledge" / "README.md").read_text())

    def test_force_greenfield_to_existing_adds_brief(self):
        self.assertEqual(self._init().returncode, 0)
        result = self._init("existing", "--force")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "knowledge" / "_bootstrap-brief.md").exists())
        self.assertIn("**KB status:** SCAFFOLDED", (self.root / "knowledge" / "README.md").read_text())

    def test_force_greenfield_rejects_modified_brief_before_writing(self):
        self.assertEqual(self._init("existing").returncode, 0)
        brief = self.root / "knowledge" / "_bootstrap-brief.md"
        brief.write_text(brief.read_text() + "\nUser evidence\n")
        readme = self.root / "knowledge" / "README.md"
        before = readme.read_bytes()
        result = self._init("greenfield", "--force")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("modified or not tracked", result.stderr)
        self.assertEqual(readme.read_bytes(), before)
        self.assertIn("User evidence", brief.read_text())

    def test_broken_generated_search_prevents_success_message(self):
        # Use an isolated copy so malformed runtime behavior can be tested without
        # touching the checkout shared with other test processes.
        installation = Path(self.tmp.name) / "broken-kbase"
        (installation / "bin").mkdir(parents=True)
        shutil.copy2(INIT, installation / "bin" / "kbase-init")
        shutil.copy2(REPO / "VERSION", installation / "VERSION")
        shutil.copytree(REPO / "template", installation / "template")
        for code, expected in (
            ("raise RuntimeError('broken search')\n", 1),
            ("raise SystemExit(1)\n", 1),
            ("print('search failed')\nraise SystemExit(1)\n", 1),
            ("print('no matches')\nraise SystemExit(1)\n", 0),
        ):
            with self.subTest(code=code):
                (installation / "template" / "scripts" / "ksearch.py").write_text(code, encoding="utf-8")
                result = subprocess.run(
                    [sys.executable, str(installation / "bin" / "kbase-init"), "--force", str(self.root)],
                    capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, expected, result.stderr)
                if expected:
                    self.assertIn("generated ksearch smoke failed", result.stderr)
                    self.assertNotIn("DONE", result.stdout)
                else:
                    self.assertIn("no hits yet", result.stdout)
                    self.assertIn("DONE", result.stdout)

    def test_default_adapters_manifest_and_stage_instruction(self):
        (self.root / "src").mkdir()
        (self.root / "frontend").mkdir()
        result = self._init()
        self.assertEqual(result.returncode, 0, result.stderr)
        for directory in (".agents", ".claude"):
            for skill in ("distill", "kb-audit", "kb-handoff"):
                stub = self.root / directory / "skills" / skill / "SKILL.md"
                self.assertTrue(stub.is_file(), str(stub))
            self.assertFalse((self.root / directory / "skills" / "kb-plan").exists())
        self.assertIn("@AGENTS.md", (self.root / "CLAUDE.md").read_text())
        manifest = json.loads((self.root / ".kbase.json").read_text())
        self.assertEqual(manifest["schema_version"], 1)
        self.assertEqual(manifest["template_version"], (REPO / "VERSION").read_text().strip())
        self.assertEqual(manifest["agents"], ["codex", "claude"])
        self.assertEqual(manifest["source_roots"], ["src", "frontend"])
        self.assertFalse(manifest["workflow"])
        self.assertEqual(len(manifest["managed_files"]), 10)
        for rel, sha in manifest["managed_files"].items():
            self.assertEqual(hashlib.sha256((self.root / rel).read_bytes()).hexdigest(), sha)
            self.assertTrue(rel.startswith(("scripts/", ".agents/skills/", ".claude/skills/")), rel)

        # The printed command stages generated dotfiles/adapters without a broad
        # wildcard that could accidentally include project credentials.
        (self.root / ".env").write_text("PRIVATE=test\n")
        stage = next(line.strip() for line in result.stdout.splitlines() if line.startswith("    git add -- "))
        staged = subprocess.run(shlex.split(stage), cwd=self.root, capture_output=True, text=True)
        self.assertEqual(staged.returncode, 0, staged.stderr)
        paths = git(self.root, "diff", "--cached", "--name-only").stdout.splitlines()
        for expected in (".gitignore", ".kbase.json", "CLAUDE.md", ".agents/skills/kb-handoff/SKILL.md", ".claude/skills/distill/SKILL.md"):
            self.assertIn(expected, paths)
        self.assertNotIn(".env", paths)

    def test_codex_only_with_workflow(self):
        result = self._init("greenfield", "--agents", "codex", "--workflow")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        for skill in ("kb-plan", "kb-implement", "kb-review", "kb-board"):
            self.assertTrue((self.root / ".agents" / "skills" / skill / "SKILL.md").is_file())
            self.assertTrue((self.root / "knowledge" / "practices" / "skills" / f"{skill}.md").is_file())

    def test_claude_only_preserves_existing_router(self):
        claude = self.root / "CLAUDE.md"
        content = "# Project instructions\n\nKeep this policy.\n"
        claude.write_text(content)
        result = self._init("greenfield", "--agents", "claude")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".agents").exists())
        self.assertEqual(claude.read_text(), content)
        self.assertEqual((self.root / "knowledge" / "_claude-router-block.md").read_text(), "# Knowledge base\n\n@AGENTS.md\n")
        self.assertIn("merge knowledge/_claude-router-block.md into CLAUDE.md manually", result.stdout)
        forced = self._init("greenfield", "--agents", "claude", "--force")
        self.assertEqual(forced.returncode, 0, forced.stderr)
        self.assertEqual(claude.read_text(), content)

    def test_no_adapters(self):
        result = self._init("greenfield", "--agents", "none")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / ".agents").exists())
        self.assertFalse((self.root / ".claude").exists())
        self.assertFalse((self.root / "CLAUDE.md").exists())
        manifest = json.loads((self.root / ".kbase.json").read_text())
        self.assertEqual(manifest["agents"], [])
        self.assertEqual(manifest["source_roots"], ["."])

    def test_custom_adapter_is_preserved_without_adoption(self):
        stub = self.root / ".agents" / "skills" / "distill" / "SKILL.md"
        stub.parent.mkdir(parents=True)
        stub.write_text("Custom project distillation\n")
        result = self._init()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stub.read_text(), "Custom project distillation\n")
        manifest = json.loads((self.root / ".kbase.json").read_text())
        self.assertNotIn(".agents/skills/distill/SKILL.md", manifest["managed_files"])
        self.assertIn("preserved custom .agents/skills/distill/SKILL.md", result.stdout)

    def test_explicit_source_roots_are_validated_and_deduplicated(self):
        (self.root / "backend").mkdir()
        (self.root / "ui").mkdir()
        result = self._init("greenfield", "--source-dir", "backend", "--source-dir", "ui", "--source-dir", "backend/.")
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.root / ".kbase.json").read_text())
        self.assertEqual(manifest["source_roots"], ["backend", "ui"])

    def test_source_root_escape_fails_before_writing(self):
        (self.root / "src").symlink_to(self.root.parent, target_is_directory=True)
        result = self._init("greenfield", "--source-dir", "src")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside the repo", result.stderr)
        self.assertFalse((self.root / "knowledge").exists())

    def test_destination_parent_collision_fails_before_writing(self):
        (self.root / ".claude").write_text("project-owned file\n")
        result = self._init()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not a directory", result.stderr)
        self.assertFalse((self.root / "knowledge").exists())

    def test_destination_parent_symlink_fails_before_writing(self):
        (self.root / "tooling").mkdir()
        (self.root / "scripts").symlink_to(self.root / "tooling", target_is_directory=True)
        result = self._init()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("destination parent is a symlink", result.stderr)
        self.assertFalse((self.root / "knowledge").exists())
        self.assertEqual(list((self.root / "tooling").iterdir()), [])

    def test_existing_mode_scaffolds_brief_and_gate_blocks_bad_state(self):
        r = self._init("existing")
        self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        brief = self.root / "knowledge" / "_bootstrap-brief.md"
        self.assertTrue(brief.is_file())
        self.assertIn("practices/skills/distill.md", brief.read_text(encoding="utf-8"))

        # Commit the scaffold, then stage a born-invalid file.
        git(self.root, "add", "-A")
        git(self.root, "commit", "-m", "scaffold KB")
        bad = self.root / "knowledge" / "rules" / "bad-note.md"
        bad.write_text("# Bad\n\nno tldr and never linked\n", encoding="utf-8")
        git(self.root, "add", str(bad))
        blocked = self._gate()
        self.assertEqual(blocked.returncode, 1)
        self.assertIn("no TL;DR", blocked.stdout)
        self.assertIn("not linked", blocked.stdout)

        # A clean flip passes: drop the bad file, flip both status lines to
        # VERIFIED (the line already names the existing baseline commit),
        # delete the brief, stage everything.
        git(self.root, "reset", "--", str(bad))
        bad.unlink()
        for name in ("README.md", "INDEX.md"):
            p = self.root / "knowledge" / name
            p.write_text(
                p.read_text(encoding="utf-8").replace(
                    "**KB status:** SCAFFOLDED", "**KB status:** VERIFIED"
                ),
                encoding="utf-8",
            )
        brief.unlink()
        git(self.root, "add", "-A")
        flipped = self._gate()
        self.assertEqual(flipped.returncode, 0, flipped.stdout)


if __name__ == "__main__":
    unittest.main()
