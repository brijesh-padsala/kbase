#!/usr/bin/env python3
"""Check a scaffold's files, search, discovery adapters, and local tooling.

Read-only: no query log, hook installation, dependency downloads, or repairs.
Exit 1 for errors; --strict also treats setup warnings as failures.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
from kbformat import is_current_md

SCRIPTS = ("kbformat.py", "ksearch.py", "ksearch-eval.py", "knowledge-gate.py", "kbase-doctor.py")
CORE_SKILLS = ("distill", "kb-audit", "kb-handoff")
WORKFLOW_SKILLS = ("kb-plan", "kb-implement", "kb-review", "kb-board")
AGENT_DIRS = {"codex": ".agents", "claude": ".claude"}
CONTEXT_BYTES_ADVISORY = 6000
DESCRIPTION_BYTES_ADVISORY = 600


def text_metrics(text):
    """Exact UTF-8 text sizes, plus an explicitly heuristic token estimate."""
    return {
        "bytes": len(text.encode("utf-8")), "chars": len(text),
        "lines": len(text.splitlines()), "estimated_tokens": (len(text) + 3) // 4,
    }


def total_metrics(items):
    totals = {key: sum(item[key] for item in items) for key in ("bytes", "chars", "lines")}
    totals["estimated_tokens"] = (totals["chars"] + 3) // 4
    return totals


def local_imports(text):
    """Recognize simple @path tokens, excluding fenced and inline code."""
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence:
            continue
        line = re.sub(r"(`+).*?\1", "", line)
        for token in re.findall(r"(?<![\w/@])@([^\s`<>\"']+)", line):
            yield token.rstrip(".,;:!?)]}")


def context_path(root, source, reference):
    """Only ordinary in-repo instruction documents are eligible imports."""
    if "://" in reference or Path(reference).is_absolute() or "\\" in reference:
        raise ValueError("absolute, remote, or non-portable import skipped")
    path = Path(os.path.abspath(source.parent / reference))
    if not path.is_relative_to(root):
        raise ValueError("import leaves repository; not read")
    parts = [part.lower() for part in path.relative_to(root).parts]
    if any(part.startswith((".env", "credential", ".credential", "secret", ".secret")) or part in (".ssh", ".aws", ".gnupg") for part in parts):
        raise ValueError("potentially sensitive import skipped")
    if path.suffix.lower() not in (".md", ".markdown", ".mdx", ".txt") and path.name not in ("README", "AGENTS", "CLAUDE"):
        raise ValueError("non-document import skipped")
    return managed_path(root, path.relative_to(root).as_posix())


def skill_metadata(text):
    """Read the portable single-line fields used by generated stubs, not YAML generally."""
    lines = text.splitlines()
    if not lines or lines[0] != "---" or "---" not in lines[1:]:
        raise ValueError("skill frontmatter missing")
    frontmatter = lines[1:lines.index("---", 1)]
    fields = {}
    for key in ("name", "description"):
        matches = [line.split(":", 1)[1].strip() for line in frontmatter if line.startswith(key + ":")]
        if len(matches) != 1 or not matches[0] or matches[0][0] in "|>":
            raise ValueError("context inventory supports single-line name/description only")
        value = matches[0]
        if value.startswith('"'):
            value = json.loads(value)
        elif value.startswith("'"):
            if not value.endswith("'") or len(value) < 2:
                raise ValueError("invalid quoted skill metadata")
            value = value[1:-1].replace("''", "'")
        else:
            value = re.sub(r"\s+#.*$", "", value)
        if not isinstance(value, str) or not value:
            raise ValueError("skill name/description must be nonempty strings")
        fields[key] = value
    return fields


def context_inventory(root, manifest):
    """Inventory repository inputs, not an agent's exact active prompt."""
    files, unavailable, seen = {}, [], set()

    def read_file(path):
        rel = path.relative_to(root).as_posix()
        path = managed_path(root, rel)
        # Decode bytes directly so CRLF and Unicode measurements remain exact.
        text = path.read_bytes().decode("utf-8")
        return text, {"path": rel, **text_metrics(text)}

    # Claude can expand imports in AGENTS.md; other clients need not do so.
    claude = "claude" in manifest["agents"]
    pending = [(root / "CLAUDE.md", True)] if claude else []
    pending.append((root / "AGENTS.md", claude))
    while pending:
        path, imports = pending.pop()
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            continue
        seen.add(rel)
        try:
            text, metrics = read_file(path)
        except (OSError, ValueError) as exc:
            unavailable.append({"path": rel, "reason": str(exc)})
            continue
        files[rel] = metrics
        if imports:
            for reference in local_imports(text):
                try:
                    imported = context_path(root, path, reference)
                except ValueError as exc:
                    unavailable.append({"path": reference, "from": rel, "reason": str(exc)})
                    continue
                pending.append((imported, True))
    required = []
    try:
        _, index = read_file(root / "knowledge/INDEX.md")
        required.append({**index, "already_in_startup": index["path"] in files})
    except (OSError, ValueError) as exc:
        unavailable.append({"path": "knowledge/INDEX.md", "reason": str(exc)})
    adapters, names = {}, {}
    for agent in manifest["agents"]:
        entries = []
        directory = managed_path(root, f"{AGENT_DIRS[agent]}/skills")
        for path in sorted(directory.rglob("SKILL.md")):
            rel = path.relative_to(root).as_posix()
            try:
                text, _ = read_file(path)
                fields = skill_metadata(text)
            except (OSError, ValueError) as exc:
                unavailable.append({"path": rel, "reason": str(exc)})
                continue
            payload = fields["name"] + "\n" + fields["description"] + "\n"
            entries.append({"path": rel, **fields, **text_metrics(payload),
                            "description_bytes": len(fields["description"].encode("utf-8"))})
            names.setdefault(fields["name"], []).append({"agent": agent, "path": rel})
        adapters[agent] = {"files": entries, "totals": total_metrics(entries)}
    combined = {**files, **{item["path"]: item for item in required}}
    return {
        "measurement": "UTF-8 bytes, Unicode characters, splitlines; estimated_tokens = ceil(chars/4), not a model tokenizer",
        "startup": {"files": list(files.values()), "totals": total_metrics(list(files.values()))},
        "required_reads": {"files": required, "totals": total_metrics(required)},
        "unique_router_and_required_reads": total_metrics(list(combined.values())),
        "skill_metadata": adapters,
        "duplicate_skill_names": {name: locations for name, locations in names.items() if len(locations) > 1},
        "unavailable": unavailable,
        "limits": [
            "Repository input inventory, not exact active context or cached-input billing; adapter metadata is never summed across harnesses.",
            "Only simple local @path document imports outside fenced/inline code are recognized; imports are deduplicated and cycles stopped.",
            "Native scopes, user/global instructions, client import-depth limits, non-document imports, and actual client loading are unmodeled.",
            "Skill sizes measure normalized name + newline + description + newline; bodies are on demand and client rendering can differ.",
        ],
    }


def context_checks(context):
    checks = []
    size = context["unique_router_and_required_reads"]["bytes"]
    if size > CONTEXT_BYTES_ADVISORY:
        checks.append(("WARN", f"Router/imports plus required INDEX total {size} bytes; advisory budget is {CONTEXT_BYTES_ADVISORY} bytes"))
    for adapter in context["skill_metadata"].values():
        for entry in adapter["files"]:
            if entry["description_bytes"] > DESCRIPTION_BYTES_ADVISORY:
                checks.append(("WARN", f"{entry['path']}: description exceeds advisory {DESCRIPTION_BYTES_ADVISORY}-byte budget"))
    if context["unavailable"]:
        checks.append(("WARN", f"Context inventory has {len(context['unavailable'])} unavailable/skipped input(s); see JSON details"))
    if context["duplicate_skill_names"]:
        checks.append(("INFO", "Same-name skills across adapters may also be visible in Cursor; client precedence/deduplication is unmeasured, costs are not added"))
    return checks


def print_context(context):
    startup, required = context["startup"]["totals"], context["required_reads"]["totals"]
    print(f"CONTEXT: router/imports {startup['bytes']} bytes; required INDEX {required['bytes']} bytes (reported separately)")
    for agent, metadata in context["skill_metadata"].items():
        totals = metadata["totals"]
        print(f"CONTEXT: {agent} skill names/descriptions {totals['bytes']} bytes, ~{totals['estimated_tokens']} heuristic tokens; bodies on demand")
    total = context["unique_router_and_required_reads"]
    print(f"CONTEXT: unique router + required reads ~{total['estimated_tokens']} tokens by ceil(chars/4), not exact active context or cached-input cost")


def managed_path(root, relative):
    """Resolve manifest paths without traversing outside the repo or symlinks."""
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "\\" in relative:
        raise ValueError(f"invalid repository path: {relative!r}")
    target = root / path
    if any(p.is_symlink() for p in (target, *target.parents) if p != root and root in p.parents):
        raise ValueError(f"symlink in managed path: {relative}")
    for parent in target.parents:
        if parent == root:
            break
        if root in parent.parents and parent.exists() and not parent.is_dir():
            raise ValueError(f"managed path parent is not a directory: {parent.relative_to(root)}")
    if not target.resolve().is_relative_to(root):
        raise ValueError(f"path leaves repository: {relative}")
    return target


def load_manifest(root):
    manifest = json.loads(managed_path(root, ".kbase.json").read_text(encoding="utf-8"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported .kbase.json schema_version (expected 1)")
    agents = manifest.get("agents")
    if not isinstance(agents, list) or any(not isinstance(a, str) or a not in AGENT_DIRS for a in agents):
        raise ValueError("manifest agents must contain codex and/or claude")
    if len(set(agents)) != len(agents) or not isinstance(manifest.get("workflow"), bool):
        raise ValueError("manifest has duplicate agents or an invalid workflow setting")
    if not isinstance(manifest.get("template_version"), str):
        raise ValueError("manifest template_version is missing")
    roots = manifest.get("source_roots")
    files = manifest.get("managed_files")
    if not isinstance(roots, list) or not roots or any(not isinstance(p, str) for p in roots):
        raise ValueError("manifest source_roots must be a nonempty list of paths")
    if not isinstance(files, dict) or not files:
        raise ValueError("manifest managed_files is missing")
    for rel, digest in files.items():
        managed_path(root, rel)
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"invalid SHA256 for {rel}")
    for rel in roots:
        managed_path(root, rel)
    return manifest


def run(root, *args, env=None):
    child_env = dict(os.environ if env is None else env, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(args, cwd=root, env=child_env, capture_output=True, text=True, timeout=30)


def check_adapters(root, manifest):
    checks = []
    skills = CORE_SKILLS + (WORKFLOW_SKILLS if manifest["workflow"] else ())
    for agent in manifest["agents"]:
        for skill in skills:
            rel = f"{AGENT_DIRS[agent]}/skills/{skill}/SKILL.md"
            stub = managed_path(root, rel)
            canonical = root / "knowledge/practices/skills" / f"{skill}.md"
            if not stub.is_file() or not canonical.is_file():
                checks.append(("FAIL", f"{agent}: missing {rel} or its canonical procedure"))
            elif f"knowledge/practices/skills/{skill}.md" not in stub.read_text(encoding="utf-8"):
                checks.append(("FAIL", f"{rel}: canonical procedure pointer is missing"))
    if not checks:
        checks.append(("PASS", "Selected skill discovery layouts and canonical procedures exist"))
    router = root / "AGENTS.md"
    if not router.is_file() or "knowledge/INDEX.md" not in router.read_text(encoding="utf-8"):
        checks.append(("WARN", "Merge the KB router into AGENTS.md (knowledge/INDEX.md pointer missing)"))
    if "claude" in manifest["agents"]:
        claude = root / "CLAUDE.md"
        if not claude.is_file() or "@AGENTS.md" not in claude.read_text(encoding="utf-8"):
            checks.append(("WARN", "Claude adapter: merge @AGENTS.md into CLAUDE.md or verify native AGENTS.md loading"))
    return checks


def diagnose(root):
    checks = [("PASS" if sys.version_info >= (3, 10) else "FAIL", "Python >= 3.10 required")]
    if not shutil.which("git"):
        return checks + [("FAIL", "git is not on PATH")]
    git = run(root, "git", "rev-parse", "--show-toplevel")
    if git.returncode or Path(git.stdout.strip()).resolve() != root:
        return checks + [("FAIL", "Target must be the Git repository root")]
    try:
        manifest = load_manifest(root)
    except (OSError, ValueError) as exc:
        return checks + [("FAIL", f"Cannot read installation manifest: {exc}")]
    checks.append(("PASS", f"Template version {manifest['template_version']}"))
    for rel, digest in manifest["managed_files"].items():
        path = managed_path(root, rel)
        if not path.is_file():
            checks.append(("FAIL", f"Missing managed file: {rel}"))
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            checks.append(("WARN", f"Locally modified managed file (update will preserve it): {rel}"))
    for name in SCRIPTS:
        if not (root / "scripts" / name).is_file():
            checks.append(("FAIL", f"Missing scripts/{name}"))
    checks.extend(check_adapters(root, manifest))
    for rel in manifest["source_roots"]:
        if not managed_path(root, rel).is_dir():
            checks.append(("FAIL", f"Configured source directory is missing: {rel}"))
    if any(level == "FAIL" for level, _ in checks):
        return checks
    gate = run(root, sys.executable, "scripts/knowledge-gate.py", "--all")
    checks.append(("FAIL", (gate.stdout + gate.stderr).strip() or "Knowledge validation failed") if gate.returncode else ("PASS", "Full working-tree knowledge validation"))
    env = dict(os.environ, KB_ROOT=str(root / "knowledge"), KSEARCH_NO_LOG="1", PYTHONDONTWRITEBYTECODE="1")
    search = run(root, sys.executable, "scripts/ksearch.py", "knowledge", "--limit", "1", "--max-bytes", "0", env=env)
    no_hits = search.returncode == 1 and search.stdout.strip() == "no matches" and not search.stderr
    checks.append(("PASS", "Search script runs without writing a query log") if (search.returncode == 0 and not search.stderr) or no_hits else ("FAIL", "Search script failed: " + (search.stderr or search.stdout).strip()))
    todo = []
    for path in (root / "knowledge").rglob("*.md"):
        if is_current_md(path.relative_to(root).as_posix()) and re.search(r"TODO\((?:project|distillation)\)", path.read_text(encoding="utf-8")):
            todo.append(str(path.relative_to(root)))
    if todo:
        checks.append(("WARN", "Fill project placeholders: " + ", ".join(sorted(todo))))
    hook_result = run(root, "git", "rev-parse", "--git-path", "hooks/pre-commit")
    hook = root / hook_result.stdout.strip()
    config = root / ".pre-commit-config.yaml"
    configured = config.is_file() and re.search(r"\bid:\s*knowledge-gate\b", config.read_text(encoding="utf-8"))
    activated = hook.is_file() and os.access(hook, os.X_OK) and "pre_commit" in hook.read_text(encoding="utf-8", errors="replace")
    if not configured or not activated or not shutil.which("pre-commit"):
        checks.append(("WARN", "Merge the knowledge-gate hook configuration, install pre-commit, then run pre-commit install"))
    else:
        checks.append(("PASS", "pre-commit executable, knowledge-gate config, and installed hook detected"))
    for name in ("rg", "ripwire"):
        if shutil.which(name):
            version = run(root, name, "--version")
            lines = (version.stdout or version.stderr).splitlines()
            checks.append(("PASS" if version.returncode == 0 else "WARN", lines[0] if lines else f"{name}: no version output"))
        else:
            checks.append(("WARN", f"Optional {name} unavailable; use available targeted text search"))
    return checks


def collect_report(root, context_only=False):
    """Keep the no-subprocess inventory preflight separate from runtime diagnosis."""
    if context_only:
        marker = managed_path(root, ".git")
        git_directory = marker.is_dir() and (marker / "HEAD").is_file() and (marker / "objects").is_dir()
        git_worktree = marker.is_file() and marker.read_bytes().startswith(b"gitdir: ")
        if not root.is_dir() or not (git_directory or git_worktree):
            raise ValueError("Target must be a repository root with a .git directory or worktree marker")
        manifest = load_manifest(root)
        checks = [("PASS", "Repository marker and installation manifest validated; runtime checks skipped (--context-only)")]
    else:
        checks = diagnose(root)
        try:
            manifest = load_manifest(root)
        except (OSError, ValueError):
            return checks, None  # diagnose already reports the installation failure.
    context = context_inventory(root, manifest)
    return checks + context_checks(context), context


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--strict", action="store_true", help="fail on setup warnings too")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--context-only", action="store_true", help="inventory context inputs without running Git, gates, search, or tool probes")
    args = parser.parse_args()
    context = None
    try:
        checks, context = collect_report(Path(args.target).resolve(), args.context_only)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        checks = [("FAIL", str(exc))]
    failed = any(level == "FAIL" or (args.strict and level == "WARN") for level, _ in checks)
    if args.json:
        print(json.dumps({"ok": not failed, "checks": [{"level": level, "message": message} for level, message in checks], "context": context}, indent=2))
    else:
        for level, message in checks:
            print(f"{level}: {message}")
        if context is not None:
            print_context(context)
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
