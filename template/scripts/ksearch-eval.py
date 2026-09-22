#!/usr/bin/env python3
"""Evaluate local KB retrieval, not answer or patch correctness.

Usage: ksearch-eval.py cases.jsonl [--root knowledge] [--limit 5]
                       [--max-bytes 2400] [--json]
Each JSONL row: {"id": "optional", "query": "required", "relevant":
["rules/example.md"], "dir": "optional/subdir"}. An empty relevant list
means the query should return no results. Exits: 0 all cases pass, 1 quality
misses, 2 malformed fixtures or runtime failures. Python standard library only.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys

# Importing the shipped search module must not write into the target checkout.
sys.dont_write_bytecode = True
import ksearch  # noqa: E402


def relative_path(value, label):
    if not isinstance(value, str) or not value or "\\" in value:
        raise ValueError(f"{label}: expected a nonempty relative POSIX path")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value:
        raise ValueError(f"{label}: path must be normalized and relative to the KB")
    return path


def load_cases(path, root, available):
    """Validate every case before running searches; invalid gold is not a miss."""
    cases, ids = [], set()
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        label = f"{path}:{number}"
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{label}: invalid JSON: {exc.msg}") from exc
        if not isinstance(case, dict) or set(case) - {"id", "query", "relevant", "dir"}:
            raise ValueError(f"{label}: expected an object with id/query/relevant/dir fields only")
        query = case.get("query")
        if not isinstance(query, str) or not query.strip() or not ksearch.tokenize(query):
            raise ValueError(f"{label}: query must contain searchable text")
        relevant = case.get("relevant")
        if not isinstance(relevant, list):
            raise ValueError(f"{label}: relevant must be a list; [] means expected no-answer")
        case_id = case.get("id", f"line-{number}")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in ids:
            raise ValueError(f"{label}: id must be a unique nonempty string")
        ids.add(case_id)
        directory = case.get("dir")
        if "dir" in case:
            directory = relative_path(directory, f"{label} dir").as_posix()
            resolved = (root / directory).resolve()
            if not resolved.is_relative_to(root) or not resolved.is_dir():
                raise ValueError(f"{label}: dir must exist inside the KB")
            if any(part.startswith(".") or ksearch.kbformat.is_excluded_dir(part)
                   for part in PurePosixPath(directory).parts):
                raise ValueError(f"{label}: dir is outside current-note scope")
        normalized = []
        for gold in relevant:
            gold = relative_path(gold, f"{label} relevant").as_posix()
            if gold in normalized:
                raise ValueError(f"{label}: duplicate relevant path: {gold}")
            if gold not in available or not (root / gold).resolve().is_relative_to(root):
                raise ValueError(f"{label}: relevant path is missing or outside current-note scope: {gold}")
            if directory and not PurePosixPath(gold).is_relative_to(directory):
                raise ValueError(f"{label}: relevant path is outside dir: {gold}")
            normalized.append(gold)
        cases.append({"id": case_id, "query": query, "relevant": normalized, "dir": directory})
    if not cases:
        raise ValueError(f"{path}: fixture has no cases")
    return cases


def displayed_results(case, root, limit, max_bytes):
    """Measure the actual CLI serialization, including diagnostic overhead."""
    command = [sys.executable, "-B", str(Path(__file__).resolve().with_name("ksearch.py")),
               "--json", "--limit", str(limit), "--max-bytes", str(max_bytes)]
    if case["dir"]:
        command.extend(["--dir", case["dir"]])
    command.extend(["--", case["query"]])
    env = dict(os.environ, KB_ROOT=str(root), KSEARCH_NO_LOG="1", PYTHONDONTWRITEBYTECODE="1")
    run = subprocess.run(command, cwd=root, env=env, capture_output=True, timeout=60)
    stdout, stderr = run.stdout.decode("utf-8"), run.stderr.decode("utf-8")
    if run.returncode not in (0, 1):
        raise ValueError(f"{case['id']}: ksearch failed (exit {run.returncode}): {stderr.strip()}")
    if max_bytes and len(run.stdout) > max_bytes:
        raise ValueError(f"{case['id']}: ksearch stdout exceeded --max-bytes")
    try:
        rows = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{case['id']}: ksearch returned invalid JSON") from exc
    if not isinstance(rows, list) or any(not isinstance(row, dict) or not isinstance(row.get("file"), str)
                                         for row in rows):
        raise ValueError(f"{case['id']}: ksearch JSON must be an array of result objects with file paths")
    if (run.returncode == 1) != (len(rows) == 0):
        raise ValueError(f"{case['id']}: ksearch result count does not match its exit status")
    return rows, {
        "stdout_bytes": len(run.stdout), "stderr_bytes": len(run.stderr),
        "total_output_bytes": len(run.stdout) + len(run.stderr),
        "stdout_estimated_tokens": round(len(stdout) / 4, 2),
        "total_estimated_tokens": round((len(stdout) + len(stderr)) / 4, 2),
    }


def rank_metrics(paths, gold, limit):
    if not gold:
        return {"first_relevant_rank": None, "reciprocal_rank": None, "recall_at_limit": None}
    rank = next((index for index, path in enumerate(paths, 1) if path in gold), None)
    return {"first_relevant_rank": rank, "reciprocal_rank": 1 / rank if rank else 0,
            "recall_at_limit": len(set(paths[:limit]) & gold) / len(gold)}


def evaluate(cases, docs, root, limit, max_bytes):
    results = []
    for case in cases:
        scoped = {path: text for path, text in docs.items()
                  if not case["dir"] or PurePosixPath(path).is_relative_to(case["dir"])}
        ranked, _ = ksearch.score(list(dict.fromkeys(ksearch.tokenize(case["query"]))), scoped)
        raw_paths = [path for _, path in ranked]
        rows, output = displayed_results(case, root, limit, max_bytes)
        shown = [row["file"] for row in rows]
        if len(shown) > limit or len(set(shown)) != len(shown) or any(path not in scoped for path in shown):
            raise ValueError(f"{case['id']}: ksearch returned duplicate, out-of-scope, or excess results")
        gold = set(case["relevant"])
        passed = bool(gold & set(shown)) if gold else not shown
        results.append({"id": case["id"], "query": case["query"], "relevant": case["relevant"],
                        "dir": case["dir"], "passed": passed, "raw_files": raw_paths[:limit],
                        "displayed_files": shown, "raw": rank_metrics(raw_paths, gold, limit),
                        "displayed": rank_metrics(shown, gold, limit), **output})
    positive = [case for case in results if case["relevant"]]
    no_answer = [case for case in results if not case["relevant"]]
    summary = {"cases": len(results), "passed": sum(case["passed"] for case in results),
               "positive_cases": len(positive), "no_answer_cases": len(no_answer),
               "raw_any_hit_at_limit": mean([case["raw"]["recall_at_limit"] > 0 for case in positive]),
               "displayed_any_hit_rate": mean([case["passed"] for case in positive]),
               "abstention_rate": mean([case["passed"] for case in no_answer])}
    for mode in ("raw", "displayed"):
        summary[f"{mode}_mrr"] = mean([case[mode]["reciprocal_rank"] for case in positive])
        summary[f"{mode}_recall_at_limit"] = mean([case[mode]["recall_at_limit"] for case in positive])
    for field in ("stdout_bytes", "stderr_bytes", "total_output_bytes", "stdout_estimated_tokens", "total_estimated_tokens"):
        summary[field] = sum(case[field] for case in results)
    return summary, results


def mean(values):
    return sum(values) / len(values) if values else None


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cases", type=Path, help="JSONL query/relevance judgments")
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent / "knowledge")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--max-bytes", type=int, default=2400, help="stdout byte cap per query; 0 disables it")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.limit < 1 or args.max_bytes < 0:
        ap.error("--limit must be positive and --max-bytes must be nonnegative")
    try:
        root = args.root.resolve()
        if not root.is_dir():
            raise ValueError(f"KB root is not a directory: {root}")
        paths = ksearch.list_md_files(None, False, str(root))
        # Unlike interactive search, an evaluator must not silently skip unreadable input.
        docs = {}
        for path in paths:
            source = Path(path)
            if not source.resolve().is_relative_to(root):
                raise ValueError(f"current note resolves outside the KB: {source}")
            docs[source.relative_to(root).as_posix()] = source.read_text(encoding="utf-8")
        cases = load_cases(args.cases, root, docs)
        summary, results = evaluate(cases, docs, root, args.limit, args.max_bytes)
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ksearch-eval: {exc}", file=sys.stderr)
        return 2
    fingerprint = hashlib.sha256(json.dumps(docs, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()
    report = {"root": str(root), "corpus_sha256": fingerprint, "limit": args.limit,
              "max_bytes": args.max_bytes, "token_estimate": "Unicode characters / 4; heuristic, not model tokenization",
              "scope": "file retrieval only; not answer or patch correctness", "summary": summary, "results": results}
    if args.json:
        print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    else:
        print(f"Retrieval cases: {summary['passed']}/{summary['cases']} pass; file retrieval only, not task correctness")
        print(f"Raw MRR: {summary['raw_mrr']}; displayed MRR: {summary['displayed_mrr']}; "
              f"displayed recall@{args.limit}: {summary['displayed_recall_at_limit']}")
        print(f"Any relevant displayed: {summary['displayed_any_hit_rate']}; no-answer abstention: {summary['abstention_rate']}")
        print(f"Output: {summary['stdout_bytes']} stdout bytes; {summary['total_output_bytes']} including stderr; "
              f"~{summary['total_estimated_tokens']} tokens (characters/4 heuristic)")
        for case in results:
            print(f"{'PASS' if case['passed'] else 'MISS'} {case['id']}: {', '.join(case['displayed_files']) or '(no results)'}")
    return 0 if summary["passed"] == summary["cases"] else 1


if __name__ == "__main__":
    sys.exit(main())
