"""knowledge-gate tests — the rule functions, without a repository.

The checks are pure functions over content maps; main() only does git
plumbing. These tests are the interface the rules are pinned to.
"""

import contextlib
import importlib.util
import io
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "template" / "scripts"
sys.path.insert(0, str(SCRIPTS))

_spec = importlib.util.spec_from_file_location("knowledge_gate", SCRIPTS / "knowledge-gate.py")
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

def always_exists(sha):
    return True


def plan(status="DRAFT"):
    return f"# Plan\n\n## Status\n\n{status}\n"


class PlanStatus(unittest.TestCase):
    def test_valid_board_state_passes(self):
        staged = {"knowledge/plans/001-thing.md": plan("IN-PROGRESS")}
        self.assertEqual(gate.check_plan_status(staged), [])

    def test_missing_or_bad_state_flagged(self):
        for content in (plan("WHENEVER"), "# Plan with no status section\n"):
            problems = gate.check_plan_status({"knowledge/plans/002-x.md": content})
            self.assertEqual(len(problems), 1)
            self.assertIn("## Status", problems[0])

    def test_deletion_skipped_and_non_plan_ignored(self):
        self.assertEqual(gate.check_plan_status({"knowledge/plans/003-gone.md": None}), [])
        self.assertEqual(gate.check_plan_status({"knowledge/rules/hygiene.md": "no status"}), [])


class ProtectedShrink(unittest.TestCase):
    PATH = "knowledge/learning/lessons-log.md"

    def test_scaffolded_head_skips_the_guard(self):
        staged = {self.PATH: "tiny"}
        head = {self.PATH: "x" * 1000}
        self.assertEqual(gate.check_protected_shrink(staged, head, "SCAFFOLDED"), [])

    def test_shrink_flagged_once_verified(self):
        staged = {self.PATH: "x" * 100}
        head = {self.PATH: "y" * 1000}
        problems = gate.check_protected_shrink(staged, head, "VERIFIED")
        self.assertEqual(len(problems), 1)
        self.assertIn("shrank >50%", problems[0])

    def test_archive_note_permits_intentional_pruning(self):
        staged = {self.PATH: "x" * 100, "knowledge/archive/pruning-2026.md": "why"}
        head = {self.PATH: "y" * 1000}
        self.assertEqual(gate.check_protected_shrink(staged, head, "VERIFIED"), [])

    def test_growth_and_unstaged_files_pass(self):
        self.assertEqual(
            gate.check_protected_shrink({self.PATH: "z" * 2000}, {self.PATH: "y" * 1000}, "VERIFIED"),
            [],
        )
        self.assertEqual(gate.check_protected_shrink({}, {self.PATH: "y"}, "VERIFIED"), [])


class BornValid(unittest.TestCase):
    def test_linked_tldr_note_passes(self):
        staged = {"knowledge/rules/new-rule.md": "# N\n> **TL;DR:** yes\n"}
        overlay = {"knowledge/INDEX.md": "see new-rule.md", **staged}
        self.assertEqual(gate.check_born_valid(list(staged), staged, overlay), [])

    def test_missing_tldr_flagged(self):
        staged = {"knowledge/rules/new-rule.md": "# N\nno tldr here\n"}
        overlay = {"knowledge/INDEX.md": "see new-rule.md", **staged}
        problems = gate.check_born_valid(list(staged), staged, overlay)
        self.assertEqual(len(problems), 1)
        self.assertIn("no TL;DR", problems[0])

    def test_unlinked_flagged(self):
        staged = {"knowledge/rules/new-rule.md": "# N\n> **TL;DR:** yes\n"}
        problems = gate.check_born_valid(list(staged), staged, {**staged, "knowledge/INDEX.md": "nothing"})
        self.assertEqual(len(problems), 1)
        self.assertIn("not linked", problems[0])

    def test_index_and_readme_exempt_from_tldr_not_from_link(self):
        staged = {"knowledge/INDEX.md": "# Index\n"}
        problems = gate.check_born_valid(list(staged), staged, {**staged, "knowledge/README.md": "see INDEX.md"})
        self.assertEqual(problems, [])


class StatusLines(unittest.TestCase):
    def lines(self, readme, index):
        return {
            "knowledge/README.md": gate.kbformat.parse_status(readme),
            "knowledge/INDEX.md": gate.kbformat.parse_status(index),
        }

    ALWAYS = staticmethod(always_exists)

    def test_verified_flip_is_clean(self):
        readme = "**KB status:** VERIFIED @ abc1234 (2026-09-17)\n"
        self.assertEqual(
            gate.check_status_lines(self.lines(readme, readme), False, [], self.ALWAYS), []
        )

    def test_verified_with_brief_still_present_blocked(self):
        readme = "**KB status:** VERIFIED @ abc1234 (2026-09-17)\n"
        problems = gate.check_status_lines(self.lines(readme, readme), True, [], self.ALWAYS)
        self.assertEqual(len(problems), 1)
        self.assertIn("still exists", problems[0])

    def test_verified_sha_must_exist(self):
        readme = "**KB status:** VERIFIED @ abc1234 (2026-09-17)\n"
        problems = gate.check_status_lines(self.lines(readme, readme), False, [], lambda sha: False)
        self.assertTrue(any("does not exist" in p for p in problems))

    def test_verified_without_sha_blocked(self):
        readme = "**KB status:** VERIFIED\n"
        problems = gate.check_status_lines(self.lines(readme, readme), False, [], self.ALWAYS)
        self.assertTrue(any("must name a commit" in p for p in problems))

    def test_modes_must_agree_and_be_present(self):
        problems = gate.check_status_lines(
            self.lines("**KB status:** SCAFFOLDED @ a100000", "**KB status:** VERIFIED @ a100000"),
            True, [], self.ALWAYS,
        )
        self.assertTrue(any("disagree" in p for p in problems))
        problems = gate.check_status_lines(
            self.lines("no status", "**KB status:** VERIFIED @ a100000"), False, [], self.ALWAYS
        )
        self.assertTrue(any("missing" in p for p in problems))

    def test_scaffolded_needs_brief_when_adding(self):
        scaf = "**KB status:** SCAFFOLDED @ a100000 (2026-09-17)\n"
        # SCAFFOLDED + brief + additions: the normal distillation state.
        self.assertEqual(
            gate.check_status_lines(self.lines(scaf, scaf), True, ["knowledge/rules/x.md"], self.ALWAYS),
            [],
        )
        # SCAFFOLDED + brief gone + a fresh addition: loud flag.
        problems = gate.check_status_lines(
            self.lines(scaf, scaf), False, ["knowledge/rules/x.md"], self.ALWAYS
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("bootstrap-brief", problems[0])
        # Removing the brief without flipping status is invalid even without additions.
        problems = gate.check_status_lines(self.lines(scaf, scaf), False, [], self.ALWAYS)
        self.assertTrue(any("bootstrap-brief" in p for p in problems))

    def test_missing_root_is_actionable(self):
        problems = gate.check_status_lines(
            {"knowledge/README.md": ("VERIFIED", "abc1234")}, False, [], self.ALWAYS
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("knowledge/INDEX.md", problems[0])
        self.assertIn("missing", problems[0])

    def test_matching_modes_with_different_shas_fail(self):
        for mode, brief in (("VERIFIED", False), ("SCAFFOLDED", True)):
            problems = gate.check_status_lines(
                self.lines(f"**KB status:** {mode} @ abc1234", f"**KB status:** {mode} @ def5678"),
                brief, [], self.ALWAYS,
            )
            self.assertTrue(any("SHAs disagree" in p for p in problems))

    def test_status_sha_case_is_immaterial(self):
        self.assertEqual(gate.check_status_lines(
            self.lines("**KB status:** VERIFIED @ ABC1234", "**KB status:** VERIFIED @ abc1234"),
            False, [], self.ALWAYS,
        ), [])


class LessonEvidence(unittest.TestCase):
    LOG = "# Lessons\n> **TL;DR:** log\n\n"

    def test_labeled_entry_with_evidence_passes(self):
        content = self.LOG + "- ✅ — **Thing (2026-01-01).** Evidence: commit abc.\n"
        self.assertEqual(gate.check_lesson_evidence(content), [])

    def test_verified_and_stale_entries_need_evidence(self):
        content = (
            self.LOG
            + "- ✅ — **Claimed (2026-01-01).** asserted, not shown.\n"
            + "- ⚠ — **Old (2025-01-01).** dated and uncited.\n"
        )
        problems = gate.check_lesson_evidence(content)
        self.assertEqual(len(problems), 2)
        self.assertIn("Claimed", problems[0])
        self.assertIn("no evidence", problems[0])

    def test_open_observation_is_exempt(self):
        content = self.LOG + "- ❓ — **Open (2026-01-01).** not verified yet.\n"
        self.assertEqual(gate.check_lesson_evidence(content), [])

    def test_multiline_entry_evidence_on_continuation_counts(self):
        content = (
            self.LOG
            + "- ✅ — **Thing (2026-01-01).**\n"
            + "  **Domain:** ci. **Cue:** renames. **Lesson:** grep first.\n"
            + "  **Evidence:** commit abc123\n"
            + "\n- ✅ — **Later (2026-01-02).** asserted, not shown.\n"
        )
        problems = gate.check_lesson_evidence(content)
        self.assertEqual(len(problems), 1)
        self.assertIn("Later", problems[0])

    def test_fenced_example_is_not_an_entry(self):
        content = self.LOG + "```markdown\n- ✅ — **Sample.** no evidence\n```\n"
        self.assertEqual(gate.check_lesson_evidence(content), [])

    def test_added_bullets_scopes_the_check_to_the_commit(self):
        old = "- ✅ — **Legacy (2020-01-01).** no cite\n"
        new = "- ✅ — **Fresh (2026-01-01).** Evidence: run output.\n"
        content = self.LOG + old + new
        self.assertEqual(gate.check_lesson_evidence(content, {new.strip()}), [])
        problems = gate.check_lesson_evidence(content, {old.strip()})
        self.assertEqual(len(problems), 1)
        self.assertIn("Legacy", problems[0])


class ScriptRefs(unittest.TestCase):
    def test_existing_ref_passes(self):
        notes = {"knowledge/rules/a.md": "run `python3 scripts/ksearch.py x`\n"}
        self.assertEqual(gate.check_script_refs(notes, {"scripts/ksearch.py"}), [])

    def test_missing_script_flagged(self):
        notes = {"knowledge/rules/a.md": "run `python3 scripts/gone.py x`\n"}
        problems = gate.check_script_refs(notes, {"scripts/ksearch.py"})
        self.assertEqual(len(problems), 1)
        self.assertIn("scripts/gone.py", problems[0])

    def test_fenced_examples_and_non_py_paths_ignored(self):
        notes = {"knowledge/rules/a.md": "```\npython3 scripts/gone.py x\n```\nsee tools/x.py and scripts/setup.sh\n"}
        self.assertEqual(gate.check_script_refs(notes, set()), [])


class PlanNumbers(unittest.TestCase):
    def test_unique_numbers_pass_and_archive_ignored(self):
        paths = [
            "knowledge/plans/001-a.md",
            "knowledge/plans/002-b.md",
            "knowledge/plans-archive/001-old.md",
            "knowledge/plans/artifacts/plan-template.md",
        ]
        self.assertEqual(gate.check_plan_numbers(paths), [])

    def test_duplicate_flagged(self):
        problems = gate.check_plan_numbers(
            ["knowledge/plans/003-a.md", "knowledge/plans/003-b.md"]
        )
        self.assertEqual(len(problems), 1)
        self.assertIn("003", problems[0])


class NoSecrets(unittest.TestCase):
    def test_clean_notes_and_secret_vocabulary_pass(self):
        bodies = {"knowledge/memory/operations.md": "secrets live in the vault; name their location\n"}
        self.assertEqual(
            gate.check_no_secrets(list(bodies), bodies), []
        )

    def test_credential_filenames_flagged(self):
        problems = gate.check_no_secrets(
            ["knowledge/.env", "knowledge/x.pem", "knowledge/id_ed25519", "knowledge/rules/a.md"], {}
        )
        self.assertEqual(len(problems), 3)
        self.assertIn("credential material", problems[0])

    def test_key_shapes_flagged_in_bodies_including_fences(self):
        bodies = {"knowledge/docs/x.md": "example:\n```\n-----BEGIN PRIVATE KEY-----\n```\n"}
        problems = gate.check_no_secrets(list(bodies), bodies)
        self.assertEqual(len(problems), 1)
        self.assertIn("PEM", problems[0])

    def test_aws_shaped_id_flagged(self):
        bodies = {"knowledge/memory/ops.md": "key: AKIAIOSFODNN7EXAMPLE\n"}
        problems = gate.check_no_secrets(list(bodies), bodies)
        self.assertEqual(len(problems), 1)
        self.assertIn("AWS", problems[0])

    def test_non_text_suffix_bodies_not_scanned(self):
        bodies = {"knowledge/x.bin": "-----BEGIN PRIVATE KEY-----\n"}
        self.assertEqual(gate.check_no_secrets(list(bodies), bodies), [])


class Report(unittest.TestCase):
    def test_report_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gate.report(["problem one"]), 1)
            self.assertEqual(gate.report([]), 0)
        self.assertIn("problem one", out.getvalue())


if __name__ == "__main__":
    unittest.main()
