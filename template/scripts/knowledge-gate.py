#!/usr/bin/env python3
"""knowledge-gate — validate knowledge/ (self-contained).

By default checks use the Git index, so another session's unstaged WIP can
never fail this gate. --all validates the complete working tree instead:

1. Plan files need a `## Status` section with a board state; plan numbers
   (`plans/<NNN>-<slug>.md`) must be unique.
2. lessons-log.md / memory/operations.md may not shrink >50% without a
   staged archive/ note (anti-truncation).
3. Added knowledge files (all current notes with --all) need a TL;DR and a
   reference from another current file. --all also checks local Markdown links.
4. KB status line (README.md + INDEX.md): present in both, modes and SHAs agree;
   VERIFIED names a commit that exists; a present _bootstrap-brief.md
   requires SCAFFOLDED (flip and brief deletion happen in one commit).
   SCAFFOLDED requires the brief. --all skips historical anti-truncation checks.
5. New ✅/⚠ lessons-log entries must name their evidence (❓ entries are open
   observations and stay exempt). --all checks every entry in the log.
6. Credential-shaped filenames or content never enter knowledge/ — a tripwire
   on the write boundary, not a scanner.
7. `scripts/*.py` paths invoked in note prose must resolve — staged mode checks
   the post-commit index, --all the working tree.

The note format, current-file scope, and status-line grammar come from
kbformat (shared with ksearch — one declaration, no drift).
Exit 0 = pass, 1 = blocked (reasons printed).
"""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

import kbformat
from kbformat import has_tldr, is_current_md, parse_status

PLAN_FILE = re.compile(r"knowledge/plans/(\d{3})-[^/]+\.md")
BOARD_STATES = {"DRAFT", "READY", "IN-PROGRESS", "BLOCKED", "DONE", "ABANDONED"}
ROOTS = ("knowledge/INDEX.md", "knowledge/README.md")
TLDR_EXEMPT = ("INDEX.md", "README.md")
PROTECTED = ("knowledge/learning/lessons-log.md", "knowledge/memory/operations.md")
LESSONS_FILE = PROTECTED[0]
LESSON_ENTRY = re.compile(r"^-\s*(✅|⚠|❓)")
SCRIPT_REF = re.compile(r"scripts/[a-z0-9][a-z0-9_-]*\.py")
SECRET_NAME = re.compile(
    r"^\.env|\.(env|pem|key|p12|pfx|keystore|jks)$|^id_(rsa|ed25519|ecdsa)\b", re.IGNORECASE
)
SECRET_MARKERS = (
    ("PEM private key block", re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----")),
    ("AWS access key id", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHub token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{20,}\b|\bgithub_pat_[A-Za-z0-9_]{22,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("OpenAI-style key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("Google API key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("JWT", re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")),
)
SECRET_SCAN_SUFFIXES = frozenset(
    {".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".yaml", ".yml", ".log", ""}
)


def git(*args, check=True):
    return subprocess.run(  # noqa: S603
        ["git", *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=check,
    ).stdout


# --- checks: pure functions over content maps ---------------------------------
# main() does the git plumbing and builds the maps; every rule below is
# testable without a repository.


def check_plan_status(staged: dict[str, str | None]) -> list[str]:
    problems = []
    for path, content in staged.items():
        if PLAN_FILE.fullmatch(path) and content is not None:
            m = re.search(r"^## Status\s*\n+\s*(\S+)", content, re.MULTILINE)
            if not m or m.group(1).upper() not in BOARD_STATES:
                problems.append(
                    f"{path}: needs '## Status' with one of {sorted(BOARD_STATES)} "
                    "(plans/README.md rule 2)"
                )
    return problems


def check_protected_shrink(staged: dict[str, str | None], head: dict[str, str], head_mode) -> list[str]:
    """Anti-truncation of protected records — only once the KB is VERIFIED.

    The SCAFFOLDED→VERIFIED distillation legitimately rewrites the stubs
    wholesale; the guard protects accumulated history, which starts existing
    at the flip.
    """
    if head_mode == "SCAFFOLDED":
        return []
    archive_note = any(
        path.startswith("knowledge/archive/") and content is not None
        for path, content in staged.items()
    )
    problems = []
    for path in PROTECTED:
        if path not in staged:
            continue
        old = head.get(path, "")
        new = staged[path] or ""
        if len(new) < len(old) * 0.5 and not archive_note:
            problems.append(
                f"{path}: shrank >50% — silent truncation? If intentional, also stage "
                "an archive/ note explaining the removal."
            )
    return problems


def check_born_valid(added: list[str], staged: dict[str, str | None], overlay: dict[str, str], *, all_notes=False) -> list[str]:
    problems = []
    label = "knowledge file" if all_notes else "added knowledge file"
    for path in added:
        if path.rsplit("/", 1)[-1] not in TLDR_EXEMPT and not has_tldr(staged[path] or ""):
            problems.append(f"{path}: {label} has no TL;DR (kb-maintenance.md)")
        base = os.path.basename(path)
        linked = any(
            other != path and base in (content or "")
            for other, content in overlay.items()
        )
        if not linked:
            problems.append(
                f"{path}: {label} is not linked from any current knowledge file — "
                "link it from its topical home or the plans board"
            )
    return problems


def check_status_lines(lines: dict, brief_present: bool, added: list[str], commit_exists) -> list[str]:
    """lines: {root: (mode, sha)} for the ROOTS present on the overlay.
    commit_exists(sha) -> bool is the repository seam."""
    problems = []
    for root in ROOTS:
        if root not in lines:
            problems.append(f"{root}: required knowledge root is missing — restore it")
    (mode_a, sha_a), (mode_b, sha_b) = (lines.get(root, (None, None)) for root in ROOTS)
    if ROOTS[0] in lines and mode_a is None:
        problems.append(f"{ROOTS[0]}: missing '**KB status:**' line")
    if ROOTS[1] in lines and mode_b is None:
        problems.append(f"{ROOTS[1]}: missing '**KB status:**' line")
    if mode_a and mode_b and mode_a != mode_b:
        problems.append(
            f"KB status lines disagree: {ROOTS[0]}={mode_a}, {ROOTS[1]}={mode_b}"
        )
    if mode_a and mode_b and (sha_a or "").lower() != (sha_b or "").lower():
        problems.append(
            f"KB status SHAs disagree: {ROOTS[0]}={sha_a or '(missing)'}, "
            f"{ROOTS[1]}={sha_b or '(missing)'}"
        )
    modes = {mode_a, mode_b}
    if "VERIFIED" in modes:
        if brief_present:
            problems.append(
                "KB status is VERIFIED but knowledge/_bootstrap-brief.md still exists — "
                "complete the distillation and delete the brief in the same commit "
                "as the flip"
            )
        for root, (mode, sha) in lines.items():
            if mode != "VERIFIED":
                continue
            if not sha:
                problems.append(f"{root}: VERIFIED status must name a commit: '@ <sha>'")
            elif not commit_exists(sha):
                problems.append(
                    f"{root}: VERIFIED names commit {sha}, which does not exist in "
                    "this repo"
                )
    if "SCAFFOLDED" in modes and not brief_present:
        problems.append(
            "KB status is SCAFFOLDED but knowledge/_bootstrap-brief.md is missing — "
            "either restore the brief or flip the status to VERIFIED"
        )
    return problems


def prose_lines(content):
    """Lines outside fenced code blocks — fences mark examples, not prose."""
    fence = None
    for line in content.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is None:
            yield line


def lesson_entries(content):
    """Parse the log into (label, lines): a `- ✅/⚠/❓` bullet opens an entry,
    indented/blank/quote lines continue it, anything else closes it. Fenced
    blocks are format examples, not entries."""
    entries, label, chunk, fence = [], None, [], None
    for line in content.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue
        m = LESSON_ENTRY.match(line)
        if m:
            if label is not None:
                entries.append((label, chunk))
            label, chunk = m.group(1), [line]
        elif label is not None and (not line.strip() or line[0] in " \t>"):
            chunk.append(line)
        elif label is not None:
            entries.append((label, chunk))
            label, chunk = None, []
    if label is not None:
        entries.append((label, chunk))
    return entries


def check_lesson_evidence(content, added_bullets=None):
    """✅/⚠ lesson entries must name their evidence; ❓ entries are open
    observations and exempt. `added_bullets` narrows the check to the entries a
    commit introduced; None checks every entry in the file."""
    problems = []
    for label, chunk in lesson_entries(content):
        if label == "❓" or "evidence" in "\n".join(chunk).lower():
            continue
        if added_bullets is not None and chunk[0].strip() not in added_bullets:
            continue
        problems.append(
            f"{LESSONS_FILE}: lesson '{chunk[0].lstrip('- ').strip()[:60]}' names no "
            "evidence — cite the file, command output, or commit it rests on, "
            "or label it ❓"
        )
    return problems


def check_plan_numbers(paths) -> list[str]:
    """One number per plan — a duplicate means two plans answer to the same
    board row and one silently shadows the other."""
    seen = {}
    problems = []
    for path in sorted(paths):
        m = PLAN_FILE.fullmatch(path)
        if not m:
            continue
        if m.group(1) in seen:
            problems.append(
                f"{path}: plan number {m.group(1)} is also used by "
                f"{seen[m.group(1)]} — pick the next free number (plans/README.md rule 1)"
            )
        else:
            seen[m.group(1)] = path
    return problems


def check_no_secrets(paths, bodies: dict[str, str]) -> list[str]:
    """Credential material never enters the KB — a tripwire on the write
    boundary, not a scanner. Names are checked across every file under
    knowledge/; bodies are scanned only in text-suffixed files (fences count —
    a key in a code block is still committed). Spell placeholders `<redacted>`
    or `<TOKEN>` — the gate cannot tell a fake from a leak."""
    problems = []
    for path in sorted(paths):
        if SECRET_NAME.search(path.rsplit("/", 1)[-1]):
            problems.append(
                f"{path}: filename looks like credential material — secrets never "
                "enter knowledge/; name their location instead"
            )
    for path in sorted(bodies):
        if Path(path).suffix.lower() not in SECRET_SCAN_SUFFIXES:
            continue
        label = next((l for l, rx in SECRET_MARKERS if rx.search(bodies[path])), None)
        if label:
            problems.append(
                f"{path}: contains a {label}-shaped value — redact it "
                "(`<redacted>`), or record where the secret lives, never the secret"
            )
    return problems


def check_script_refs(notes: dict[str, str], existing_scripts: set[str]) -> list[str]:
    """`scripts/*.py` invocations must resolve — a dead pointer fails silently at
    run time, not in review. Fenced examples do not count."""
    problems = []
    for path, content in notes.items():
        refs = {m for line in prose_lines(content) for m in SCRIPT_REF.findall(line)}
        for ref in sorted(refs - existing_scripts):
            problems.append(
                f"{path}: invokes `{ref}`, which does not exist — create it or "
                "fix the reference"
            )
    return problems


def check_local_links(notes: dict[str, str]) -> list[str]:
    """Check file/directory destinations in inline and reference Markdown links.

    URLs and same-page anchors are out of scope. Ignore fenced examples and
    inline code; this is a filesystem check, not a Markdown anchor validator.
    Called only in --all mode, where filesystem existence is authoritative.
    """
    problems = []
    inline = re.compile(r"\[[^\]\n]*\]\(\s*(<[^>\n]+>|[^\s)\n]+)")
    reference = re.compile(r"^\s{0,3}\[[^\]\n]+\]:\s*(<[^>\n]+>|\S+)", re.MULTILINE)
    for path, content in notes.items():
        text = "\n".join(re.sub(r"(`+).*?\1", "", line) for line in prose_lines(content))
        for destination in dict.fromkeys(inline.findall(text) + reference.findall(text)):
            target = destination.strip("<>")
            try:
                parsed = urlsplit(target)
            except ValueError:
                problems.append(f"{path}: malformed Markdown link: {target}")
                continue
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            relative = unquote(parsed.path)
            resolved = Path(relative.lstrip("/")) if relative.startswith("/") else Path(path).parent / relative
            if not resolved.exists():
                problems.append(f"{path}: broken local Markdown link: {target}")
    return problems


def commit_exists(sha):
    return subprocess.run(  # noqa: S603
        ["git", "rev-parse", "--verify", "--quiet", f"{sha}^{{commit}}"],  # noqa: S607
        capture_output=True,
    ).returncode == 0


def check_roots(notes: dict[str, str], raw_paths: set[str], added: list[str]) -> list[str]:
    lines = {root: parse_status(notes[root]) for root in ROOTS if root in notes}
    return check_status_lines(
        lines,
        brief_present="knowledge/_bootstrap-brief.md" in raw_paths,
        added=added,
        commit_exists=commit_exists,
    )


def validate_staged() -> list[str]:
    entries = git(
        "diff", "--cached", "--name-status", "--no-renames", "-z", "--", "knowledge/"
    ).split("\0")[:-1]
    pairs = list(zip(entries[::2], entries[1::2], strict=True))
    staged = {path: None if status == "D" else git("show", f":{path}") for status, path in pairs}

    if not staged:
        return []

    problems = []
    problems += check_plan_status(staged)

    head_mode, _ = parse_status(git("show", "HEAD:knowledge/README.md", check=False))
    head = {p: git("show", f"HEAD:{p}", check=False) for p in PROTECTED}
    problems += check_protected_shrink(staged, head, head_mode)

    # The index is exactly HEAD plus staged changes, with deletions already
    # removed. Keep raw paths separate: _bootstrap-brief.md is not a current note.
    raw_paths = set(git("ls-files", "--cached", "-z", "--", "knowledge/").split("\0")) - {""}
    overlay = {p: git("show", f":{p}") for p in sorted(raw_paths) if is_current_md(p)}
    added = [p for status, p in pairs if status == "A" and is_current_md(p)]
    problems += check_born_valid(added, staged, overlay)

    # Lessons appended by this commit must carry evidence. Entries are parsed
    # from the staged post-image so continuation lines count even when the diff
    # shows only the bullet.
    if staged.get(LESSONS_FILE):
        diff = git("diff", "--cached", "-U0", "--no-renames", "--", LESSONS_FILE)
        added_bullets = {
            ln[1:].strip() for ln in diff.splitlines()
            if ln.startswith("+") and not ln.startswith("+++") and LESSON_ENTRY.match(ln[1:])
        }
        problems += check_lesson_evidence(staged[LESSONS_FILE], added_bullets)

    # Notes must not invoke scripts that will not exist once this commit lands.
    scripts = {p for p in git("ls-files", "-z", "--", "scripts").split("\0") if p.endswith(".py")}
    problems += check_script_refs(overlay, scripts)

    # Write-boundary tripwires check the post-commit tree, not just the commit's
    # own files: a secret committed earlier is still a secret in the index.
    problems += check_plan_numbers(raw_paths)
    bodies = {
        p: git("show", f":{p}") for p in sorted(raw_paths)
        if Path(p).suffix.lower() in SECRET_SCAN_SUFFIXES
    }
    problems += check_no_secrets(raw_paths, bodies)

    problems += check_roots(overlay, raw_paths, added)
    return problems


def validate_all() -> list[str]:
    if not Path("knowledge").is_dir():
        return ["knowledge/ is missing — initialize the knowledge base first"]
    raw_paths = {p.as_posix() for p in Path("knowledge").rglob("*") if p.is_file()}
    notes = {p: Path(p).read_text(encoding="utf-8") for p in sorted(raw_paths) if is_current_md(p)}
    scripts = {p.as_posix() for p in Path("scripts").rglob("*.py")}
    bodies = {
        p: Path(p).read_text(encoding="utf-8", errors="replace")
        for p in sorted(raw_paths)
        if Path(p).suffix.lower() in SECRET_SCAN_SUFFIXES
    }
    problems = (
        check_plan_status(notes)
        + check_plan_numbers(raw_paths)
        + check_born_valid(list(notes), notes, notes, all_notes=True)
        + check_local_links(notes)
        + check_no_secrets(raw_paths, bodies)
        + check_script_refs(notes, scripts)
        + check_roots(notes, raw_paths, list(notes))
    )
    if LESSONS_FILE in notes:
        problems += check_lesson_evidence(notes[LESSONS_FILE])
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="validate all current working-tree notes, without staging")
    args = parser.parse_args(argv)
    try:
        os.chdir(git("rev-parse", "--show-toplevel").strip())
        problems = validate_all() if args.all else validate_staged()
    except subprocess.CalledProcessError as exc:
        reason = (exc.stderr or "Git could not read the requested repository state").strip()
        problems = [f"cannot inspect Git state: {reason} — run inside a Git repo and resolve any index conflicts"]
    except (OSError, UnicodeError, ValueError) as exc:
        problems = [f"cannot read knowledge state: {exc}"]
    return report(problems, scope="working tree" if args.all else "staged change")


def report(problems, scope="staged change"):
    if problems:
        print(f"KNOWLEDGE GATE: {scope} has invalid knowledge state:", *problems, sep="\n  ")
        print("  See knowledge/rules/kb-maintenance.md and knowledge/plans/README.md.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
