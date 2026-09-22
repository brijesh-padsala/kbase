#!/usr/bin/env python3
"""ksearch — keyword search over this repo's knowledge base.

Returns ranked excerpts with file pointers, so agents read ~500 tokens
instead of whole files. BM25-style scoring with per-field weights (description/TL;DR
above headings above body) so files that are ABOUT a term outrank incidental mentions.
The note format and current-file scope come from kbformat (shared with
knowledge-gate — one declaration, no drift). Python standard library only.

Usage:
  ksearch <query> [--json] [--limit N] [--dir SUBDIR]
  ksearch <query> --include-archive  # opt into archived/artifact material

KB location: $KB_ROOT, else <script_dir>/../knowledge.
Exit codes: 0 = hits, 1 = no hits.
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


def tokenize(text: str):
    return [
        t.lower()
        for t in re.findall(r"[A-Za-z0-9_.\-/]+", text)
        if t.lower() not in STOPWORDS and len(t) > 1
    ]


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


def best_excerpt(text: str, terms: list[str], width: int = 320) -> str:
    """Return the line-window with the highest term density."""
    lines = text.splitlines()
    best_score, best_i = -1.0, 0
    for i, line in enumerate(lines):
        low = line.lower()
        score = sum(low.count(t) for t in terms)
        if score > best_score:
            best_score, best_i = score, i
    lo = max(0, best_i - 2)
    hi = min(len(lines), best_i + 4)
    out = " ⏎ ".join(line.strip() for line in lines[lo:hi] if line.strip())
    return out[: width * 2]


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


def render_human(scored: list, descs: dict, docs: dict, terms: list[str], n: int, root: str):
    print(f"top {len(scored)} of {n} files | KB: {root}")
    for s, f in scored:
        rel = os.path.relpath(f, root)
        print(f"\n{s:.2f}  {rel}")
        if descs[f]:
            print(f"      {descs[f]}")  # description ahead of the computed excerpt
        print(f"      {best_excerpt(docs[f], terms)}")
    print("\nread less: ksearch again narrower, or read only the cited section")


def render_json(scored: list, descs: dict, docs: dict, terms: list[str], root: str):
    print(
        json.dumps(
            [
                {
                    "score": round(s, 3),
                    "file": os.path.relpath(f, root),
                    "description": descs[f] or None,
                    "excerpt": best_excerpt(docs[f], terms),
                }
                for s, f in scored
            ],
            indent=1,
        )
    )


def search(
    query: str,
    limit: int,
    subdir: str | None,
    as_json: bool,
    include_archive: bool = False,
    root: str | None = None,
):
    root = root if root is not None else resolve_kb_root()
    terms = list(dict.fromkeys(tokenize(query)))
    if not terms:
        print("query has no searchable terms", file=sys.stderr)
        return 1
    files = list_md_files(subdir, include_archive, root)
    if not files:
        print(f"no .md files under {root}", file=sys.stderr)
        return 1

    docs = read_docs(files)
    scored, descs = score(terms, docs)
    scored = scored[:limit]

    # usage logging for KB evaluation (zero-hit audit — see rules/hygiene.md).
    # Logged BEFORE the no-match return so zero-hit queries are auditable too.
    if not as_json and not os.environ.get("KSEARCH_NO_LOG"):
        try:
            log_query(query, scored, root)
        except OSError:
            pass

    if not scored:
        print("no matches")
        return 1

    if as_json:
        render_json(scored, descs, docs, terms, root)
    else:
        render_human(scored, descs, docs, terms, len(docs), root)
    return 0


def main():
    ap = argparse.ArgumentParser(prog="ksearch")
    ap.add_argument("query", nargs="?", help="search terms")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--dir", help="restrict to knowledge/ subdir (e.g. docs, rules)")
    ap.add_argument(
        "--include-archive", action="store_true", help="include archived and artifacts directories"
    )
    a = ap.parse_args()
    if a.limit < 1:
        ap.error("--limit must be positive")
    if a.dir and (os.path.isabs(a.dir) or ".." in a.dir.split(os.sep)):
        ap.error("--dir must be a subdirectory within knowledge/")
    if not a.query:
        ap.print_help()
        return 2
    return search(a.query, a.limit, a.dir, a.json, a.include_archive)


if __name__ == "__main__":
    sys.exit(main())
