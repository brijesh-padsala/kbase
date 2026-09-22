"""kbformat tests — the note-format module both ksearch and the gate build on."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "template" / "scripts"))

import kbformat


class CurrentScope(unittest.TestCase):
    def test_scope_truth_table(self):
        cases = {
            "knowledge/rules/hygiene.md": True,
            "knowledge/docs/deep/nested/file.md": True,
            "knowledge/plans/001-plan.md": True,
            "knowledge/archive/old.md": False,
            "knowledge/rules/archive/old.md": False,
            "knowledge/plans-archive/old.md": False,
            "knowledge/plans/artifacts/notes.md": False,
            "knowledge/_bootstrap-brief.md": False,
            "knowledge/rules/_scratch.md": False,
            "README.md": False,              # outside knowledge/
            "knowledge/file.txt": False,     # not markdown
            "knowledge/README.md": True,     # basename README is current, not exempt
        }
        for path, expected in cases.items():
            self.assertIs(kbformat.is_current_md(path), expected, path)

    def test_is_excluded_dir(self):
        self.assertTrue(kbformat.is_excluded_dir("archive"))
        self.assertTrue(kbformat.is_excluded_dir("plans-archive"))
        self.assertFalse(kbformat.is_excluded_dir("rules"))
        self.assertFalse(kbformat.is_excluded_dir("artifacts-x"))
        self.assertTrue(kbformat.is_excluded_dir("artifacts"))


class Tldr(unittest.TestCase):
    def test_blockquote_tldr(self):
        text = "# Title\n\n> **TL;DR:** one-to-three sentences.\n"
        self.assertTrue(kbformat.has_tldr(text))

    def test_bare_bold_tldr(self):
        self.assertTrue(kbformat.has_tldr("**TL;DR:** no blockquote"))

    def test_empty_marker_is_not_a_tldr(self):
        self.assertFalse(kbformat.has_tldr("# Title\n\n> **TL;DR:**\n\nbody"))

    def test_tldr_must_be_near_the_top(self):
        # The house style is "opens with"; a TL;DR past the scan window is
        # neither found by ksearch's field split nor by the gate.
        padding = "\n".join(f"line {i}" for i in range(12))
        self.assertFalse(kbformat.has_tldr(padding + "\n> **TL;DR:** too late"))


class SplitFields(unittest.TestCase):
    def test_house_style_note(self):
        text = (
            "# Title\n"
            "> **TL;DR:** ranks on this.\n"
            "> continuation of the tldr\n"
            "\n"
            "## Heading one\n"
            "body line\n"
        )
        desc, tldr, heads, body = kbformat.split_fields(text)
        self.assertEqual(desc, "")
        self.assertEqual(tldr, "ranks on this. continuation of the tldr")
        self.assertEqual(heads, "Title\nHeading one")
        self.assertIn("body line", body)
        self.assertNotIn("TL;DR", body)

    def test_frontmatter_description(self):
        text = (
            "---\n"
            "description: 'quoted value'\n"
            "---\n"
            "# Title\n"
            "> **TL;DR:** t\n"
        )
        desc, tldr, heads, body = kbformat.split_fields(text)
        self.assertEqual(desc, "quoted value")
        self.assertEqual(tldr, "t")
        self.assertEqual(heads, "Title")
        self.assertNotIn("description", body)

    def test_each_line_lands_in_exactly_one_field(self):
        text = "# T\n> **TL;DR:** x\n## H\nword\n### H2\nword\n"
        desc, tldr, heads, body = kbformat.split_fields(text)
        self.assertEqual(desc, "")
        self.assertEqual(tldr, "x")
        self.assertEqual(heads.split(), ["T", "H", "H2"])  # title and headings, markers gone
        self.assertEqual(body.split(), ["word", "word"])
        self.assertNotIn("##", body)

    def test_preamble_survives_without_double_counting_fields(self):
        text = (
            "---\nname: hiddenmetadata\ndescription: descriptivetoken\n---\n"
            "# titletoken\npreambletoken\n> **TL;DR:** summarytoken\n"
            "> continuationtoken\n\n## sectiontoken\nbodytoken\n"
        )
        desc, tldr, heads, body = kbformat.split_fields(text)
        self.assertEqual(desc, "descriptivetoken")
        self.assertEqual(tldr, "summarytoken continuationtoken")
        self.assertEqual(heads.split(), ["titletoken", "sectiontoken"])
        self.assertEqual(body.split(), ["preambletoken", "bodytoken"])
        joined = " ".join((desc, tldr, heads, body))
        self.assertNotIn("hiddenmetadata", joined)
        for token in ("descriptivetoken", "titletoken", "preambletoken", "summarytoken", "continuationtoken", "bodytoken"):
            self.assertEqual(joined.count(token), 1, token)


class StatusLine(unittest.TestCase):
    def test_render_parse_round_trip(self):
        line = kbformat.render_status("VERIFIED", "abc1234", "2026-09-17", "a note")
        mode, sha = kbformat.parse_status(f"**KB status:** {line}\n")
        self.assertEqual((mode, sha), ("VERIFIED", "abc1234"))

    def test_render_without_note(self):
        line = kbformat.render_status("SCAFFOLDED", "deadbeef", "2026-09-17")
        mode, sha = kbformat.parse_status(f"> **KB status:** {line}")
        self.assertEqual((mode, sha), ("SCAFFOLDED", "deadbeef"))

    def test_fully_bolded_variant(self):
        mode, sha = kbformat.parse_status("**KB status: VERIFIED @ 1234567 (2026-09-17)**")
        self.assertEqual((mode, sha), ("VERIFIED", "1234567"))

    def test_absent_or_garbage(self):
        self.assertEqual(kbformat.parse_status("# nothing here"), (None, None))
        self.assertEqual(kbformat.parse_status("**KB status:** MYSTERY @ abc1234"), (None, "abc1234"))
        # a sha shorter than 7 hex chars is not recognized
        self.assertEqual(kbformat.parse_status("**KB status:** VERIFIED @ abc"), ("VERIFIED", None))

    def test_missing_sha(self):
        mode, sha = kbformat.parse_status("**KB status:** VERIFIED — no commit named")
        self.assertEqual((mode, sha), ("VERIFIED", None))


if __name__ == "__main__":
    unittest.main()
