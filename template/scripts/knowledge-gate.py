#!/usr/bin/env python3
"""knowledge-gate — validate staged knowledge/ changes (self-contained).

Checks (scoped to the staged overlay — HEAD plus staged changes — so another
session's unstaged WIP can never fail this gate):

1. Plan files need a `## Status` section with a board state.
2. lessons-log.md / memory/operations.md may not shrink >50% without a
   staged archive/ note (anti-truncation).
3. Added knowledge files are born with a TL;DR/description and a link from
   another current file.
4. KB status line (README.md + INDEX.md): present in both, modes agree;
   VERIFIED names a commit that exists; a present _bootstrap-brief.md
   requires SCAFFOLDED (flip and brief deletion happen in one commit).

Exit 0 = pass, 1 = blocked (reasons printed).
"""

import os
import re
import subprocess
import sys

PLAN_FILE = re.compile(r"knowledge/plans/(\d{3})-[^/]+\.md")
BOARD_STATES = {"DRAFT", "READY", "IN-PROGRESS", "BLOCKED", "DONE", "ABANDONED"}
ROOTS = ("knowledge/INDEX.md", "knowledge/README.md")
TLDR_EXEMPT = ("INDEX.md", "README.md")
PROTECTED = ("knowledge/learning/lessons-log.md", "knowledge/memory/operations.md")
TLDR_RE = re.compile(r"^\s*(?:>\s*)?\*\*TL;DR\b\*{0,2}:?\s*\S", re.MULTILINE)
STATUS_RE = re.compile(
    r"^\s*(?:>\s*)?\*{0,2}KB status:?\*{0,2}\s*(.+?)\s*\*{0,2}\s*$", re.MULTILINE
)


def git(*args, check=True):
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    ).stdout


def is_current_md(path: str) -> bool:
    """Current-scope knowledge .md: not in an archive, not _-prefixed."""
    parts = path.split("/")
    if len(parts) < 2 or parts[0] != "knowledge" or not path.endswith(".md"):
        return False
    if any(part == "archive" or part.endswith("-archive") for part in parts[1:-1]):
        return False
    if any(part == "artifacts" for part in parts[1:-1]):
        return False
    return not parts[-1].startswith("_")


def parse_status(text: str):
    """(mode, token) from the `**KB status:** ...` line; (None, None) when absent.

    Accepts `**KB status:** value` and the fully-bolded `**KB status: value**`.
    """
    m = STATUS_RE.search(text)
    if not m:
        return None, None
    line = m.group(1).strip().rstrip("*").strip()
    mode = "SCAFFOLDED" if line.upper().startswith("SCAFFOLDED") else (
        "VERIFIED" if line.upper().startswith("VERIFIED") else None
    )
    sha = re.search(r"@\s*([0-9a-fA-F]{7,40})", line)
    return mode, (sha.group(1) if sha else None)


def main():
    os.chdir(git("rev-parse", "--show-toplevel").strip())
    entries = git(
        "diff", "--cached", "--name-status", "--no-renames", "-z", "--", "knowledge/"
    ).split("\0")[:-1]
    pairs = list(zip(entries[::2], entries[1::2], strict=True))
    staged = {path: None if status == "D" else git("show", f":{path}") for status, path in pairs}
    problems: list[str] = []

    # 1. Plan Status sections.
    for path, content in staged.items():
        if PLAN_FILE.fullmatch(path) and content is not None:
            m = re.search(r"^## Status\s*\n+\s*(\S+)", content, re.MULTILINE)
            if not m or m.group(1).upper() not in BOARD_STATES:
                problems.append(
                    f"{path}: needs '## Status' with one of {sorted(BOARD_STATES)} "
                    "(plans/README.md rule 2)"
                )

    # 2. Anti-truncation of protected records.
    archive_note = any(
        path.startswith("knowledge/archive/") and content is not None
        for path, content in staged.items()
    )
    for path in PROTECTED:
        if path not in staged:
            continue
        old = git("show", f"HEAD:{path}", check=False)
        new = staged[path] or ""
        if len(new) < len(old) * 0.5 and not archive_note:
            problems.append(
                f"{path}: shrank >50% — silent truncation? If intentional, also stage "
                "an archive/ note explaining the removal."
            )

    if not staged:
        return report(problems)

    # 3. Born-valid: added files carry a TL;DR and a link from another current file.
    head_paths = {p for p in git("ls-tree", "-r", "--name-only", "HEAD", "--", "knowledge/").splitlines() if is_current_md(p)}
    overlay = {p: git("show", f"HEAD:{p}", check=False) for p in head_paths}
    for path, content in staged.items():
        if is_current_md(path):
            overlay[path] = content
    # Raw overlay (no _-filtering): the brief itself is _-prefixed, so its
    # presence must be judged outside the current-md scope.
    raw_paths = (head_paths | set(staged)) - {p for p, c in staged.items() if c is None}
    added = [p for status, p in pairs if status == "A" and is_current_md(p)]
    for path in added:
        if path.rsplit("/", 1)[-1] not in TLDR_EXEMPT and not TLDR_RE.search(staged[path] or ""):
            problems.append(f"{path}: added knowledge file has no TL;DR (kb-maintenance.md)")
        base = os.path.basename(path)
        linked = any(
            other != path and base in (content or "")
            for other, content in overlay.items()
        )
        if not linked:
            problems.append(
                f"{path}: added file is not linked from any current knowledge file — "
                "link it from its topical home or the plans board"
            )

    # 4. KB status line consistency (README + INDEX, on the overlay).
    lines = {}
    for root in ROOTS:
        if root in overlay:
            lines[root] = parse_status(overlay[root])
    if len(lines) == 2:
        (mode_a, sha_a), (mode_b, sha_b) = lines[ROOTS[0]], lines[ROOTS[1]]
        if mode_a is None:
            problems.append(f"{ROOTS[0]}: missing '**KB status:**' line")
        if mode_b is None:
            problems.append(f"{ROOTS[1]}: missing '**KB status:**' line")
        if mode_a and mode_b and mode_a != mode_b:
            problems.append(
                f"KB status lines disagree: {ROOTS[0]}={mode_a}, {ROOTS[1]}={mode_b}"
            )
        brief_present = "knowledge/_bootstrap-brief.md" in raw_paths
        mode = mode_a or mode_b
        if mode == "VERIFIED":
            if brief_present:
                problems.append(
                    "KB status is VERIFIED but knowledge/_bootstrap-brief.md still exists — "
                    "complete the distillation and delete the brief in the same commit "
                    "as the flip"
                )
            for root, (_, sha) in lines.items():
                if not sha:
                    problems.append(f"{root}: VERIFIED status must name a commit: '@ <sha>'")
                elif subprocess.run(  # noqa: S603
                    ["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],  # noqa: S607
                    capture_output=True,
                ).returncode != 0:
                    problems.append(
                        f"{root}: VERIFIED names commit {sha}, which does not exist in "
                        "this repo"
                    )
        elif mode == "SCAFFOLDED" and not brief_present and added:
            # SCAFFOLDED without a brief is legitimate only before the brief was
            # ever created (init on a repo where the user declined it); a fresh
            # addition while SCAFFOLDED with no brief is worth flagging loudly.
            problems.append(
                "KB status is SCAFFOLDED but knowledge/_bootstrap-brief.md is missing — "
                "either restore the brief or flip the status to VERIFIED"
            )
    return report(problems)


def report(problems):
    if problems:
        print("KNOWLEDGE GATE: staged change introduces invalid knowledge state:", *problems, sep="\n  ")
        print("  See knowledge/rules/kb-maintenance.md and knowledge/plans/README.md.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
