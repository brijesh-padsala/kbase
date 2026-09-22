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


class Report(unittest.TestCase):
    def test_report_exit_codes(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(gate.report(["problem one"]), 1)
            self.assertEqual(gate.report([]), 0)
        self.assertIn("problem one", out.getvalue())


if __name__ == "__main__":
    unittest.main()
