"""Real-index regressions for the staged gate and complete working-tree mode."""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GATE = Path(__file__).resolve().parents[1] / "template" / "scripts" / "knowledge-gate.py"


@unittest.skipUnless(shutil.which("git"), "git not on PATH")
class GateIntegration(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.write("README.md", "# Project\n")
        self.commit("project")
        self.baseline = self.git("rev-parse", "HEAD").stdout.strip()
        self.write_roots("SCAFFOLDED")
        self.write("knowledge/_bootstrap-brief.md", "# Distill this knowledge\n")
        self.write("knowledge/rules/example.md", "# Example\n> **TL;DR:** A useful rule.\n")
        self.commit("scaffold")

    def git(self, *args):
        result = subprocess.run(
            ["git", "-c", "user.name=gate-test", "-c", "user.email=gate@example.com", *args],
            cwd=self.root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def write(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    def append(self, path, content):
        target = self.root / path
        target.write_text(target.read_text(encoding="utf-8") + content, encoding="utf-8")

    def write_roots(self, mode):
        status = f"**KB status:** {mode} @ {self.baseline}\n"
        self.write("knowledge/README.md", f"# Knowledge\n{status}\n[INDEX](INDEX.md)\n")
        self.write("knowledge/INDEX.md", f"# Index\n{status}\n[README](README.md)\n[Rule](rules/example.md)\n")

    def commit(self, message):
        self.git("add", "-A")
        self.git("commit", "-qm", message)

    def gate(self, *args, expected=0, contains=None, cwd=None):
        result = subprocess.run(
            [sys.executable, str(GATE), *args], cwd=cwd or self.root,
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        if contains:
            self.assertIn(contains, result.stdout)
        return result

    def add_linked_note(self):
        self.write("knowledge/rules/new.md", "# New\n> **TL;DR:** A new rule.\n")
        self.append("knowledge/INDEX.md", "[New](rules/new.md)\n")

    def test_unchanged_committed_brief_allows_valid_addition(self):
        self.add_linked_note()
        self.git("add", "knowledge")
        self.gate()

    def test_flip_with_unchanged_committed_brief_fails(self):
        self.write_roots("VERIFIED")
        self.git("add", "knowledge")
        self.gate(expected=1, contains="still exists")

    def test_flip_with_only_unstaged_brief_deletion_fails(self):
        self.write_roots("VERIFIED")
        self.git("add", "knowledge")
        (self.root / "knowledge/_bootstrap-brief.md").unlink()
        self.gate(expected=1, contains="still exists")

    def test_flip_and_staged_brief_deletion_pass(self):
        self.write_roots("VERIFIED")
        (self.root / "knowledge/_bootstrap-brief.md").unlink()
        self.git("add", "-A")
        self.gate()

    def test_brief_deletion_without_flip_fails(self):
        self.git("rm", "knowledge/_bootstrap-brief.md")
        self.gate(expected=1, contains="bootstrap-brief.md is missing")

    def test_root_deletion_reports_missing_file(self):
        self.git("rm", "knowledge/INDEX.md")
        self.gate(expected=1, contains="knowledge/INDEX.md: required knowledge root is missing")

    def test_both_root_deletions_fail(self):
        self.git("rm", "knowledge/INDEX.md", "knowledge/README.md")
        self.gate(expected=1, contains="required knowledge root is missing")

    def test_deleted_note_cannot_link_new_file(self):
        self.append("knowledge/rules/example.md", "[Future](new.md)\n")
        self.commit("link future note")
        self.git("rm", "knowledge/rules/example.md")
        self.write("knowledge/rules/new.md", "# New\n> **TL;DR:** A new rule.\n")
        self.git("add", "knowledge/rules/new.md")
        self.gate(expected=1, contains="not linked")

    def test_unstaged_damage_cannot_fail_valid_staged_changes(self):
        self.add_linked_note()
        self.git("add", "knowledge")
        self.write("knowledge/INDEX.md", "broken unstaged state")
        self.write("knowledge/rules/new.md", "no TLDR")
        self.gate()

    def test_unstaged_repair_cannot_rescue_invalid_staged_note(self):
        self.write("knowledge/rules/new.md", "# No summary\n")
        self.git("add", "knowledge/rules/new.md")
        self.add_linked_note()
        self.gate(expected=1, contains="no TL;DR")
        self.gate(expected=1, contains="not linked")

    def test_all_validates_clean_committed_tree(self):
        self.gate("--all")
        self.gate("--all", cwd=self.root / "knowledge/rules")

    def test_all_validates_unstaged_new_notes(self):
        self.add_linked_note()
        self.gate("--all")
        self.write("knowledge/rules/new.md", "# No summary\n")
        self.gate()  # No staged changes remains a no-op.
        self.gate("--all", expected=1, contains="no TL;DR")

    def test_all_detects_unlinked_note(self):
        self.write("knowledge/rules/unlinked.md", "# Unlinked\n> **TL;DR:** Find me.\n")
        self.gate("--all", expected=1, contains="not linked")

    def test_all_detects_missing_bootstrap_and_roots(self):
        (self.root / "knowledge/_bootstrap-brief.md").unlink()
        self.gate("--all", expected=1, contains="bootstrap-brief.md is missing")
        (self.root / "knowledge/INDEX.md").unlink()
        self.gate("--all", expected=1, contains="required knowledge root is missing")

    def test_all_detects_broken_links_and_reference_definitions(self):
        self.append("knowledge/rules/example.md", "[Missing](missing.md)\n[ref]: gone.md\n")
        self.gate("--all", expected=1, contains="broken local Markdown link: missing.md")
        self.gate("--all", expected=1, contains="broken local Markdown link: gone.md")

    def test_all_ignores_urls_anchors_and_code_examples(self):
        self.append("knowledge/rules/example.md", """
[Web](https://example.com/whatever)
[Email](mailto:test@example.com)
[Anchor](#example)
[Folder](../rules/)
[Project](/README.md)
[Named](<../rules/example.md> "Title")
`[sample](absent.md)`
```markdown
[sample](absent.md)
```
""")
        self.gate("--all")

    def test_all_excludes_archived_artifact_and_private_notes(self):
        for path in ("knowledge/archive/old.md", "knowledge/plans/artifacts/evidence.md", "knowledge/_work.md"):
            self.write(path, "No TLDR; [broken](missing.md)\n")
        self.gate("--all")

    def test_all_checks_plan_states(self):
        self.write("knowledge/plans/001-feature.md", "# Feature\n> **TL;DR:** A plan.\n## Status\nREVIEW-PENDING\n")
        self.append("knowledge/INDEX.md", "[Feature](plans/001-feature.md)\n")
        self.gate("--all", expected=1, contains="needs '## Status'")

    def test_all_does_not_apply_historical_shrink_guard(self):
        self.write_roots("VERIFIED")
        (self.root / "knowledge/_bootstrap-brief.md").unlink()
        self.write("knowledge/memory/operations.md", "# Operations\n> **TL;DR:** Run details.\n" + "long record\n" * 50)
        self.append("knowledge/INDEX.md", "[Operations](memory/operations.md)\n")
        self.commit("verified operations")
        self.write("knowledge/memory/operations.md", "# Operations\n> **TL;DR:** Run details.\n")
        self.git("add", "knowledge/memory/operations.md")
        self.gate(expected=1, contains="shrank >50%")
        self.gate("--all")

    def test_status_sha_mismatch_fails_for_staged_and_all(self):
        self.write_roots("VERIFIED")
        (self.root / "knowledge/_bootstrap-brief.md").unlink()
        path = "knowledge/INDEX.md"
        content = (self.root / path).read_text(encoding="utf-8")
        self.write(path, content.replace(self.baseline, self.git("rev-parse", "HEAD").stdout.strip()))
        self.git("add", "-A")
        self.gate(expected=1, contains="SHAs disagree")
        self.gate("--all", expected=1, contains="SHAs disagree")

    def test_staged_lesson_entry_needs_evidence(self):
        self.write(
            "knowledge/learning/lessons-log.md",
            "# Lessons\n> **TL;DR:** log\n\n"
            "- ✅ — **Claimed (2026-01-01).** asserted, not shown.\n",
        )
        self.append("knowledge/INDEX.md", "[Lessons](learning/lessons-log.md)\n")
        self.git("add", "knowledge")
        self.gate(expected=1, contains="no evidence")
        self.write(
            "knowledge/learning/lessons-log.md",
            "# Lessons\n> **TL;DR:** log\n\n"
            "- ✅ — **Claimed (2026-01-01).** asserted, not shown.\n"
            "  **Evidence:** commit " + self.baseline + "\n",
        )
        self.git("add", "knowledge/learning/lessons-log.md")
        self.gate()

    def test_all_checks_every_lesson_entry(self):
        self.write(
            "knowledge/learning/lessons-log.md",
            "# Lessons\n> **TL;DR:** log\n\n"
            "- ❓ — **Open (2026-01-01).** unverified observation.\n"
            "- ✅ — **Asserted (2026-01-02).** no citation.\n",
        )
        self.append("knowledge/INDEX.md", "[Lessons](learning/lessons-log.md)\n")
        self.commit("add lessons")
        self.gate("--all", expected=1, contains="Asserted")

    def test_note_invoking_missing_script_fails_both_modes(self):
        self.append("knowledge/rules/example.md", "Run `python3 scripts/absent.py` first.\n")
        self.git("add", "knowledge/rules/example.md")
        self.gate(expected=1, contains="scripts/absent.py")
        self.gate("--all", expected=1, contains="scripts/absent.py")

    def test_script_staged_alongside_its_reference_passes(self):
        self.write("scripts/helpers.py", "print('ok')\n")
        self.append("knowledge/rules/example.md", "Run `python3 scripts/helpers.py`.\n")
        self.git("add", "scripts/helpers.py", "knowledge/rules/example.md")
        self.gate()

    def test_script_deleted_while_referenced_fails(self):
        self.write("scripts/helpers.py", "print('ok')\n")
        self.append("knowledge/rules/example.md", "Run `python3 scripts/helpers.py`.\n")
        self.commit("add helper and reference")
        self.git("rm", "scripts/helpers.py")
        self.append("knowledge/rules/example.md", "An unrelated note edit.\n")
        self.git("add", "knowledge/rules/example.md")
        self.gate(expected=1, contains="scripts/helpers.py")

    def test_credential_content_blocked_in_both_modes(self):
        self.append("knowledge/rules/example.md", "key: AKIAIOSFODNN7EXAMPLE\n")
        self.git("add", "knowledge/rules/example.md")
        self.gate(expected=1, contains="AWS")
        self.git("reset", "-q")  # unstaged content still fails the working-tree check
        self.gate("--all", expected=1, contains="AWS")
        self.git("checkout", "--", "knowledge/rules/example.md")

    def test_credential_filename_blocked(self):
        self.write("knowledge/.env", "A=1\n")
        self.git("add", "knowledge/.env")
        self.gate(expected=1, contains=".env")

    def test_duplicate_plan_numbers_blocked(self):
        for slug in ("a", "b"):
            self.write(
                f"knowledge/plans/001-{slug}.md",
                f"# Plan {slug}\n> **TL;DR:** a plan.\n## Status\nDRAFT\n",
            )
        self.append("knowledge/INDEX.md", "[A](plans/001-a.md) [B](plans/001-b.md)\n")
        self.git("add", "knowledge")
        self.gate(expected=1, contains="001")

    def test_no_knowledge_is_noop_only_in_default_mode(self):
        self.git("rm", "-r", "knowledge")
        self.git("commit", "-qm", "remove knowledge")
        self.gate()
        self.gate("--all", expected=1, contains="knowledge/ is missing")

    def test_outside_git_reports_actionable_failure(self):
        with tempfile.TemporaryDirectory() as outside:
            self.gate("--all", expected=1, contains="run inside a Git repo", cwd=outside)


if __name__ == "__main__":
    unittest.main()
