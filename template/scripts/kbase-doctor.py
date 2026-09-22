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

SCRIPTS = ("kbformat.py", "ksearch.py", "knowledge-gate.py", "kbase-doctor.py")
CORE_SKILLS = ("distill", "kb-audit", "kb-handoff")
WORKFLOW_SKILLS = ("kb-plan", "kb-implement", "kb-review", "kb-board")
AGENT_DIRS = {"codex": ".agents", "claude": ".claude"}


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
    search = run(root, sys.executable, "scripts/ksearch.py", "knowledge", "--limit", "1", env=env)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--strict", action="store_true", help="fail on setup warnings too")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        checks = diagnose(Path(args.target).resolve())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        checks = [("FAIL", str(exc))]
    failed = any(level == "FAIL" or (args.strict and level == "WARN") for level, _ in checks)
    if args.json:
        print(json.dumps({"ok": not failed, "checks": [{"level": level, "message": message} for level, message in checks]}, indent=2))
    else:
        for level, message in checks:
            print(f"{level}: {message}")
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
