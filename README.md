# kbase — agent-agnostic knowledge base scaffold

> **TL;DR:** One command scaffolds a production-shaped agent memory into any git repo: `knowledge/` (4-tier memory: rules / practices / docs+memory / learning / plans), `ksearch` (BM25, stdlib-only, ranked ~500-token excerpts), a `knowledge-gate` pre-commit hook, and a root `AGENTS.md` router. For repos with real history, init generates a **bootstrap brief** — a mechanical evidence pack + distillation checklist — so the first agent session turns a SCAFFOLDED KB into a VERIFIED one. No daemons, no vector DB, no external APIs.

## Quickstart

```bash
git clone https://github.com/brijesh-padsala/kbase.git   # private; your account
cd your-project
python3 /path/to/kbase/bin/kbase-init                    # auto-detects mode
```

Requirements: python3 ≥ 3.10, a git repo with at least one commit. That's it —
both scripts are standard-library only.

Then open an agent session (claude, codex, cursor, …) and say **"read AGENTS.md"**.
That is the entire interface:

- **Existing repo** (≥ ~25 source files, ≥ ~15 commits, auto-detected): the KB starts
  `SCAFFOLDED` and `knowledge/_bootstrap-brief.md` exists. The router's standing rule
  sends the first agent to the brief; it verifies the evidence pack, writes
  `architecture.md` / `pitfalls.md` / `operations.md` with per-claim ✅/❓ labels, fills
  the `TODO(project)` markers, then flips the status to `VERIFIED @ <commit>` and
  deletes the brief in one commit. `knowledge-gate` verifies the flip: VERIFIED must
  name a real commit, and VERIFIED + brief can never coexist.
- **Greenfield**: no brief; the init commit is the baseline and the write-back policy
  grows the KB (knowledge commits ride with the code that taught them).

## What lands in the target repo

```
AGENTS.md                    # router: search-don't-read table + KB status rule
.pre-commit-config.yaml      # knowledge-gate hook (created, or snippet to merge)
scripts/ksearch.py           # BM25 search over knowledge/ — excerpts, not files
scripts/knowledge-gate.py    # commit-time gate (see below)
knowledge/
  INDEX.md                   # entry point — "Where to look first" + KB status line
  README.md                  # charter + the KB status line
  docs/agent-memory-architecture.md   # the design (why files+git+CLI, what's excluded)
  docs/architecture.md       # stub → filled by distillation (or first real commit)
  rules/                     # agent-contract, write-back-policy, hygiene, quality-gates,
                             # boundaries, new-agent-onboarding, kb-maintenance
  practices/commands.md      # ksearch/ripgrep usage + TODO(project) build commands
  learning/                  # append-only lessons log + pitfalls
  memory/operations.md       # environments, runbooks, incidents (never secrets)
  plans/README.md            # numbered-plan status board
  agents/README.md           # per-agent WIRING.md pattern
knowledge/_bootstrap-brief.md        # existing mode only — deleted at VERIFIED flip
```

## The gate (commit-time, deterministic)

`scripts/knowledge-gate.py` runs via pre-commit and blocks, scoped to the staged
overlay so unstaged WIP can't fail it:

1. plan files need `## Status` with a board state;
2. `lessons-log.md` / `operations.md` can't shrink >50% without an archived note (anti-truncation);
3. added knowledge files are born with a TL;DR and a link from another current file;
4. KB status line: present in README+INDEX, modes agree, VERIFIED names an existing
   commit, SCAFFOLDED requires the brief.

## Design

The full rationale — 4-tier memory, dual loop (fast retrieval / slow consolidation),
deterministic forgetting, and the explicitly rejected tool classes (memory servers,
LLM-indexed knowledge graphs, vector-first retrieval) — ships inside every scaffolded
KB as `knowledge/docs/agent-memory-architecture.md`. Short version: markdown + git +
CLI is the only memory substrate every agent reads natively; anything that adds a
daemon, an index to keep fresh, or an LLM API in the path recreates a failure mode
this design exists to avoid.

## Repo layout (this repo)

```
bin/kbase-init        # the scaffolder (mode detection, evidence pack, brief generator)
template/             # everything that gets copied into target repos
```

Test it on a scratch repo before real use: `bin/kbase-init /tmp/scratch`.
