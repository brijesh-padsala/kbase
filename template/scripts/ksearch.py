#!/usr/bin/env python3
"""ksearch — keyword search over this repo's knowledge base.

Returns ranked excerpts with line citations, bounded to 2400 UTF-8 bytes by
default. BM25-style scoring with per-field weights (description/TL;DR
above headings above body) so files that are ABOUT a term outrank incidental mentions.
The note format and current-file scope come from kbformat (shared with
knowledge-gate — one declaration, no drift). Python standard library only.

Usage:
  ksearch <query> [--json] [--limit N] [--dir SUBDIR] [--max-bytes N]
  ksearch <query> --include-archive  # opt into archived/artifact material

KB location: $KB_ROOT, else <script_dir>/../knowledge.
Exit codes: 0 = hits, 1 = no hits, 2 = invalid arguments or insufficient budget.
The byte budget covers complete successful stdout, including metadata/newline.
Use --max-bytes 0 for no total budget. Budget omissions are reported on stderr.
"""

import argparse
import json
import math
import os
import re
import sys
from collections import Counter

import kbformat
from kbformat import split_fields

STOPWORDS = {
    "the",
    "a",
    "an",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "to",
    "of",
    "in",
    "on",
    "for",
    "with",
    "and",
    "or",
    "not",
    "how",
    "what",
    "when",
    "where",
    "which",
    "does",
    "do",
    "did",
    "can",
    "should",
    "this",
    "that",
    "it",
    "its",
    "as",
    "by",
    "at",
    "from",
    "we",
    "you",
    "i",
}

# Field weights: a term in the description/TL;DR marks the file as ABOUT the
# term; a heading is a weaker about-ness signal; a body hit may be an
# incidental mention. Exact numbers are tunable — the goal is about-ness
# beats passing mention.
FIELD_WEIGHTS = {"desc": 4.0, "tldr": 4.0, "head": 2.0, "body": 1.0}


def _token_spans(text: str):
    """Share exact term normalization between ranking and excerpt selection."""
    for match in re.finditer(r"[A-Za-z0-9_.\-/]+", text):
        term = match.group().lower().lstrip("-")
        if term not in STOPWORDS and len(term) > 1:
            yield term, match.start(), match.end()


def tokenize(text: str):
    return [term for term, _, _ in _token_spans(text)]


def resolve_kb_root() -> str:
    """KB location: $KB_ROOT, else <script_dir>/../knowledge. Read per call,
    so tests and embedders can point ksearch at any knowledge tree."""
    root = os.environ.get(
        "KB_ROOT",
        os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "knowledge"),
    )
    return os.path.realpath(root)


def list_md_files(subdir: str | None, include_archive: bool = False, root: str | None = None):
    root = root if root is not None else resolve_kb_root()
    base = root if not subdir else os.path.join(root, subdir)
    if not include_archive and any(
        kbformat.is_excluded_dir(part)
        for part in os.path.relpath(base, root).split(os.sep)
    ):
        return []
    files = []
    for dirpath, dirs, names in os.walk(base):
        dirs[:] = [
            d
            for d in dirs
            if not d.startswith(".")
            and (include_archive or not kbformat.is_excluded_dir(d))
        ]
        for n in names:
            if n.endswith(".md") and not n.startswith("_"):
                files.append(os.path.join(dirpath, n))
    return sorted(files)


def read_docs(files: list[str]) -> dict[str, str]:
    docs = {}
    for f in files:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                docs[f] = fh.read()
        except OSError:
            continue
    return docs


def score(terms: list[str], docs: dict[str, str]):
    """BM25 over kbformat-weighted fields.

    Pure: given search terms and {path: text}, return (ranked, descriptions)
    where ranked is [(score, path)] best-first and descriptions carries each
    file's frontmatter description ("" when absent). Term frequency counts
    per field (description / TL;DR / headings / body) and each field
    contributes its weight times its count, so about-ness beats incidental
    mention; a term naming the file boosts its score.
    """
    n = len(docs)
    tf = {}
    descs = {}
    df = Counter()
    for f, text in docs.items():
        desc, tldr, heads, body = split_fields(text)
        descs[f] = desc
        fc = {
            "desc": Counter(tokenize(desc)),
            "tldr": Counter(tokenize(tldr)),
            "head": Counter(tokenize(heads)),
            "body": Counter(tokenize(body)),
        }
        tf[f] = fc
        for t in terms:
            if any(fc[name].get(t) for name in FIELD_WEIGHTS):
                df[t] += 1

    k1, b = 1.5, 0.75
    # Document length for BM25 normalization = plain total tokens across all
    # fields (unweighted): length normalization reflects physical file size,
    # field weights amplify only the term-frequency contribution.
    dls = {f: sum(sum(c.values()) for c in fc.values()) for f, fc in tf.items()}
    avgdl = sum(dls.values()) / max(n, 1)
    scored = []
    for f in docs:
        dl = dls[f]
        s = 0.0
        for t in terms:
            if df[t] == 0:
                continue
            idf = math.log(1 + (n - df[t] + 0.5) / (df[t] + 0.5))
            fqt = sum(FIELD_WEIGHTS[name] * tf[f][name].get(t, 0) for name in FIELD_WEIGHTS)
            s += idf * (fqt * (k1 + 1)) / (fqt + k1 * (1 - b + b * dl / max(avgdl, 1)))
        # boost: term in filename (field weighting above replaces the old
        # first-400-chars boost — TL;DR and title heading now score as fields)
        base = os.path.basename(f).lower()
        for t in terms:
            if t in base:
                s *= 1.5
        if s > 0:
            scored.append((s, f))

    scored.sort(reverse=True)
    return scored, descs


def select_passage(text: str, terms: list[str]) -> dict:
    """Select matching content, preferring prose to frontmatter and navigation."""
    lines = text.splitlines()
    query_terms = set(terms)
    front_end = 0
    if lines and lines[0].strip() == "---":
        front_end = next((i + 1 for i in range(1, len(lines)) if lines[i].strip() == "---"), 0)
    toc = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*\[[^\]]+\]\(#[^)]+\)\s*$")
    candidates, headings = [], []
    heading, fence = None, None
    for i, line in enumerate(lines):
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker.group(1)
            if fence is None:
                fence = run
            elif run[0] == fence[0] and len(run) >= len(fence):
                fence = None
        title = kbformat.HEADING_RE.match(line) if i >= front_end and fence is None else None
        if title:
            heading = title.group(1)
        headings.append(heading)
        matches = [(term, start, end) for term, start, end in _token_spans(line) if term in query_terms]
        if matches:
            preferred = i >= front_end and not toc.match(line) and fence is None and not marker
            quality = (preferred, len({term for term, _, _ in matches}), len(matches), -i)
            candidates.append((quality, i, matches[0][1:]))
    if candidates:
        _, best_i, anchor = max(candidates)
    else:
        best_i, anchor = min(front_end, max(len(lines) - 1, 0)), (0, 1)
    hi = min(len(lines), best_i + 3)
    for i in range(best_i + 1, hi):
        if kbformat.HEADING_RE.match(lines[i]) or toc.match(lines[i]):
            hi = i
            break
    while hi > best_i + 1 and not lines[hi - 1].strip():
        hi -= 1
    return {
        "text": "\n".join(lines[best_i:hi]), "anchor": anchor,
        "line_start": best_i + 1, "heading": headings[best_i] if headings else None,
    }


def crop_text(text: str, max_bytes: int, anchor=(0, 1)):
    """Fit a contiguous UTF-8 slice around a complete match, with visible ellipses.

    Return (display text, source start, source end, truncated), or None when
    even the match and truncation markers cannot fit. Offsets are characters.
    """
    if len(text.encode("utf-8")) <= max_bytes:
        return text, 0, len(text), False
    start, end = anchor[0], min(anchor[1], len(text))
    used = len(text[start:end].encode("utf-8"))
    # Reserve both ellipses; reclaiming a few bytes at a boundary is unnecessary.
    available = max_bytes - 3 * (start > 0) - 3 * (end < len(text))
    if used > available:
        return None
    left_open, right_open = start > 0, end < len(text)
    while left_open or right_open:
        if left_open:
            cost = len(text[start - 1].encode("utf-8"))
            if used + cost <= available:
                start -= 1
                used += cost
                left_open = start > 0
            else:
                left_open = False
        if right_open:
            cost = len(text[end].encode("utf-8"))
            if used + cost <= available:
                end += 1
                used += cost
                right_open = end < len(text)
            else:
                right_open = False
    shown = ("…" if start else "") + text[start:end] + ("…" if end < len(text) else "")
    return shown, start, end, True


def best_excerpt(text: str, terms: list[str], width: int = 320) -> str:
    """Compatibility helper: a bounded excerpt; search also returns its citation."""
    passage = select_passage(text, terms)
    cropped = crop_text(passage["text"], width * 2, passage["anchor"])
    return cropped[0] if cropped else ""


def log_query(query: str, scored: list, root: str):
    """Usage logging for the KB evaluation zero-hit audit (rules/hygiene.md):
    timestamp, query, top hit, hit count."""
    import datetime

    logf = os.path.join(root, "_ksearch-log.tsv")
    with open(logf, "a", encoding="utf-8") as fh:
        top = os.path.relpath(scored[0][1], root) if scored else "-"
        fh.write(
            f"{datetime.datetime.now().isoformat(timespec='seconds')}\t{' '.join(query.split())}\t{top}\t{len(scored)}\n"
        )


def result_row(candidate: dict, excerpt_bytes=640, include_description=True):
    passage = candidate["passage"]
    cropped = crop_text(passage["text"], excerpt_bytes, passage["anchor"])
    if cropped is None:
        return None
    excerpt, start, end, truncated = cropped
    description = candidate["description"] or ""
    heading = passage["heading"] or ""
    desc_crop = crop_text(description, 160) if include_description else ("", 0, 0, bool(description))
    head_crop = crop_text(heading, 120)
    line_start = passage["line_start"] + passage["text"][:start].count("\n")
    # A trailing newline belongs to the preceding source line, not an empty one.
    line_end = line_start + passage["text"][start:end].rstrip("\n").count("\n")
    return {
        "score": candidate["score"], "file": candidate["file"],
        "description": desc_crop[0] or None, "excerpt": excerpt,
        "line_start": line_start, "line_end": line_end, "heading": head_crop[0] or None,
        "truncated": truncated or desc_crop[3] or head_crop[3],
    }


def render_output(rows: list[dict], as_json: bool, total: int, n: int) -> str:
    if as_json:
        return json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n"
    lines = [f"top {len(rows)} of {total} matches | {n} notes"]
    for row in rows:
        lines.append(f"\n{row['score']:.2f}  {row['file']}:{row['line_start']}-{row['line_end']}")
        if row["heading"]:
            lines.append(f"  {row['heading']}")
        if row["description"]:
            lines.append(f"  {row['description']}")
        lines.append("  " + row["excerpt"].replace("\n", "\n  "))
        if row["truncated"]:
            lines.append("  [truncated]")
    return "\n".join(lines) + "\n"


def fit_results(candidates: list[dict], as_json: bool, total: int, n: int, max_bytes: int):
    """Pack a ranked prefix, shortening the last passage around its match."""
    rows = []
    for candidate in candidates:
        passage = candidate["passage"]
        start, end = passage["anchor"]
        natural_width = max(640, len(passage["text"][start:end].encode("utf-8")) + 6)
        row = result_row(candidate, natural_width)
        output = render_output(rows + [row], as_json, total, n) if row else ""
        if row and (not max_bytes or len(output.encode("utf-8")) <= max_bytes):
            rows.append(row)
            continue
        # Drop a redundant description before reducing the actual evidence.
        best, low, high = None, 1, natural_width
        while low <= high:
            middle = (low + high) // 2
            shorter = result_row(candidate, middle, include_description=False)
            if shorter is None:
                low = middle + 1
                continue
            trial = render_output(rows + [shorter], as_json, total, n)
            if len(trial.encode("utf-8")) <= max_bytes:
                best, low = shorter, middle + 1
            else:
                high = middle - 1
        if best is not None:
            rows.append(best)
        break
    return rows


def _no_matches(as_json: bool, max_bytes: int, error: str | None = None):
    output = "[]\n" if as_json else ("" if error else "no matches\n")
    if max_bytes and len(output.encode("utf-8")) > max_bytes:
        print("--max-bytes too small for an empty result; increase it or use 0", file=sys.stderr)
        return 2
    if error:
        print(error, file=sys.stderr)
    sys.stdout.write(output)
    return 1


def search(
    query: str,
    limit: int,
    subdir: str | None,
    as_json: bool,
    include_archive: bool = False,
    root: str | None = None,
    *,
    max_bytes: int = 2400,
):
    if max_bytes < 0:
        print("--max-bytes must be nonnegative (0 disables the budget)", file=sys.stderr)
        return 2
    root = root if root is not None else resolve_kb_root()
    terms = list(dict.fromkeys(tokenize(query)))
    if not terms:
        return _no_matches(as_json, max_bytes, "query has no searchable terms")
    files = list_md_files(subdir, include_archive, root)
    if not files:
        return _no_matches(as_json, max_bytes, f"no .md files under {root}")

    docs = read_docs(files)
    scored, descs = score(terms, docs)

    # usage logging for KB evaluation (zero-hit audit — see rules/hygiene.md).
    # Logged BEFORE the no-match return so zero-hit queries are auditable too.
    if not as_json and not os.environ.get("KSEARCH_NO_LOG"):
        try:
            log_query(query, scored, root)
        except OSError:
            pass

    if not scored:
        return _no_matches(as_json, max_bytes)

    candidates = [
        {"score": round(s, 3), "file": os.path.relpath(f, root), "description": descs[f],
         "passage": select_passage(docs[f], terms)}
        for s, f in scored[:limit]
    ]
    rows = fit_results(candidates, as_json, len(scored), len(docs), max_bytes)
    if not rows:
        print("--max-bytes too small for the top citation; increase it or use 0", file=sys.stderr)
        return 2
    sys.stdout.write(render_output(rows, as_json, len(scored), len(docs)))
    omitted = len(candidates) - len(rows)
    if omitted:
        print(f"budget omitted {omitted} result(s); increase --max-bytes or narrow the query", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="ksearch")
    ap.add_argument("query", nargs="?", help="search terms")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--max-bytes", type=int, default=2400, help="hard UTF-8 stdout budget (default: 2400; 0: unbounded)")
    ap.add_argument("--dir", help="restrict to knowledge/ subdir (e.g. docs, rules)")
    ap.add_argument(
        "--include-archive", action="store_true", help="include archived and artifacts directories"
    )
    a = ap.parse_args()
    if a.limit < 1:
        ap.error("--limit must be positive")
    if a.max_bytes < 0:
        ap.error("--max-bytes must be nonnegative")
    if a.dir and (os.path.isabs(a.dir) or ".." in a.dir.split(os.sep)):
        ap.error("--dir must be a subdirectory within knowledge/")
    if not a.query:
        ap.print_help()
        return 2
    return search(a.query, a.limit, a.dir, a.json, a.include_archive, max_bytes=a.max_bytes)


if __name__ == "__main__":
    sys.exit(main())
