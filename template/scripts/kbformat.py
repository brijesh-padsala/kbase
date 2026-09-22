#!/usr/bin/env python3
"""kbformat — the knowledge-note format, declared once.

The single authority for "what a valid knowledge note is": the TL;DR
convention, the current-file scope, the field split ksearch ranks on, and
the KB status-line grammar. ksearch and knowledge-gate import this module
instead of re-implementing it; kbase-init imports it to write status lines
with the same grammar the gate parses. If a format rule changes, it changes
here and every consumer follows.

Python 3.10+, standard library only.
"""

import re

# --- TL;DR --------------------------------------------------------------------

# Group 1 captures the text after the marker ("" when the marker stands
# alone); has_tldr() applies the stricter non-empty rule the gate enforces.
TLDR_RE = re.compile(r"^\s*(?:>\s*)?\*\*TL;DR\b\*{0,2}:?\s*(.*)$")
TLDR_SCAN_LINES = 10  # house style keeps the TL;DR blockquote near the top


def has_tldr(text: str) -> bool:
    """True when a non-empty TL;DR sits within the first TLDR_SCAN_LINES lines."""
    for line in text.splitlines()[:TLDR_SCAN_LINES]:
        m = TLDR_RE.match(line)
        # strip emphasis/colon noise first: `> **TL;DR:**` alone is a marker,
        # not a TL;DR (same normalization split_fields applies to the text).
        if m and m.group(1).strip().strip("*:").strip():
            return True
    return False


# --- current-file scope --------------------------------------------------------


def is_excluded_dir(name: str) -> bool:
    """archive/ and *-archive/ hold history; artifacts/ holds supporting material."""
    return name == "archive" or name.endswith("-archive") or name == "artifacts"


def is_current_md(path: str) -> bool:
    """Current-scope knowledge note: knowledge/**/*.md, not archived, not _-prefixed.

    One predicate for both consumers: what ksearch indexes by default and
    what the gate polices. `ksearch --include-archive` widens retrieval;
    the enforcement scope never widens.
    """
    parts = path.split("/")
    if len(parts) < 2 or parts[0] != "knowledge" or not path.endswith(".md"):
        return False
    if any(is_excluded_dir(part) for part in parts[1:-1]):
        return False
    return not parts[-1].startswith("_")


# --- searchable fields ---------------------------------------------------------

FRONTMATTER_DESC_RE = re.compile(r"^description:\s*(.*)$")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$")


def split_fields(text: str):
    """Split a knowledge file into weighted searchable fields.

    Returns (description, tldr, headings, body):
      description — leading YAML frontmatter `description:` value ("" when absent)
      tldr        — the `> **TL;DR:** ...` blockquote line(s) near the top ("" when absent)
      headings    — all markdown heading text, newline-joined
      body        — every remaining line
    Each line lands in exactly one field, so no token is double-counted.
    """
    lines = text.splitlines()
    start = 0
    desc = ""
    if lines and lines[0].strip() == "---":
        close = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if close is not None:
            for ln in lines[1:close]:
                m = FRONTMATTER_DESC_RE.match(ln)
                if m:
                    val = m.group(1).strip()
                    if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
                        val = val[1:-1].strip()
                    desc = val
                    break
            start = close + 1

    tldr = ""
    tldr_span = range(0)
    for i in range(start, min(start + TLDR_SCAN_LINES, len(lines))):
        m = TLDR_RE.match(lines[i])
        if m:
            parts = [m.group(1).strip().strip("*:").strip()]
            j = i + 1  # continuation blockquote lines extend the TL;DR
            while j < len(lines) and lines[j].lstrip().startswith(">"):
                parts.append(lines[j].lstrip().lstrip(">").strip())
                j += 1
            tldr = " ".join(p for p in parts if p)
            tldr_span = range(i, j)
            break

    headings, body = [], []
    for i in range(start, len(lines)):
        if i in tldr_span:
            continue
        ln = lines[i]
        m = HEADING_RE.match(ln)
        if m:
            headings.append(m.group(1).strip())
        else:
            body.append(ln)
    return desc, tldr, "\n".join(headings), "\n".join(body)


# --- KB status line ------------------------------------------------------------

STATUS_MODES = ("SCAFFOLDED", "VERIFIED")
STATUS_RE = re.compile(
    r"^\s*(?:>\s*)?\*{0,2}KB status:?\*{0,2}\s*(.+?)\s*\*{0,2}\s*$", re.MULTILINE
)


def render_status(mode: str, sha: str, date: str, note: str = "") -> str:
    """The status value kbase-init writes — the exact grammar parse_status reads."""
    line = f"{mode} @ {sha} ({date})"
    return f"{line} — {note}" if note else line


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
