# kbase — agent-agnostic knowledge base scaffold

> **TL;DR:** Scaffold shared project memory into a Git repo: `knowledge/`, a small `AGENTS.md` router, bounded search with source-line citations, retrieval evaluations, and a commit-time knowledge gate. An evidence-based bootstrap brief helps agents verify existing projects. Python standard library only; no daemon, vector database, or external API.

## Quickstart

```bash
git clone https://github.com/brijesh-padsala/kbase.git   # private; your account
cd your-project
python3 /path/to/kbase/bin/kbase-init                    # auto-detects mode
# Equivalent entry point, with optional workflow skills:
python3 /path/to/kbase/bin/kbase init . --workflow
```

Requirements: Python ≥ 3.10 and a Git repo with at least one commit. The scripts
are standard-library only. `pre-commit` activates commit-time enforcement;
`rg` and `ripwire` are optional search tools. Init does not install dependencies.

Init installs Codex and Claude discovery adapters by default. Use
`--agents codex`, `--agents claude`, or `--agents none` to choose. Core skills are
`distill`, `kb-audit`, and `kb-handoff`; `--workflow` also exposes `kb-plan`,
`kb-implement`, `kb-review`, and `kb-board`. Pass `--source-dir src` (repeatable)
to record source roots for structural search; otherwise init detects conventional
source directories, falling back to `.`.

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
CLAUDE.md                    # @AGENTS.md import when Claude is selected
.kbase.json                  # template version, adapters, source roots, generated-file hashes
.pre-commit-config.yaml      # knowledge-gate hook (created, or snippet to merge)
scripts/kbformat.py          # the note format, scope, and status grammar — shared
scripts/ksearch.py           # BM25 search over knowledge/ — excerpts, not files
scripts/ksearch-eval.py      # project query judgments, retrieval quality, output bytes
scripts/knowledge-gate.py    # commit-time gate (see below)
scripts/kbase-doctor.py      # read-only installation and tooling diagnostics
.agents/skills/…/SKILL.md     # Codex discovery stubs, when selected
.claude/skills/…/SKILL.md     # Claude discovery stubs, when selected
knowledge/
  INDEX.md                   # entry point — "Where to look first" + KB status line
  README.md                  # charter + the KB status line
  docs/agent-memory-architecture.md   # the design (why files+git+CLI, what's excluded)
  docs/architecture.md       # stub → filled by distillation (or first real commit)
  rules/                     # agent-contract, write-back-policy, hygiene, quality-gates,
                             # boundaries, new-agent-onboarding, kb-maintenance
  practices/commands.md      # ksearch/ripgrep usage + TODO(project) build commands
  practices/skills/          # canonical maintenance, handoff, and workflow procedures
  learning/                  # append-only lessons log + pitfalls
  evals/cases.jsonl           # starter retrieval judgments; extend with project questions
  memory/operations.md       # environments, runbooks, incidents (never secrets)
  plans/README.md            # numbered-plan status board
  plans/artifacts/plan-template.md   # acceptance, verification, review, and handoff template
  agents/README.md           # per-agent WIRING pattern + the librarian subagent role
knowledge/_bootstrap-brief.md        # existing mode only — deleted at VERIFIED flip
```

## Skills & subagents

Skills ship as **canonical procedures in `knowledge/practices/skills/`** with
thin discovery stubs in the selected agent directories. Project facts stay in
the KB; stubs point to the shared procedure.

- **`/distill`** — runs the bootstrap brief end-to-end and lands the gate-checked
  SCAFFOLDED → VERIFIED flip.
- **`/kb-audit`** — the consolidation loop: query-log zero-hit review, aging-✅
  spot-checks, reference audit, file splits.
- **`/kb-handoff`** — save or resume objective, progress, file ownership, test
  evidence, open questions, and the next action in the active plan.

The optional workflow pack adds **kb-plan / kb-implement / kb-review / kb-board**.
It uses the existing six plan states; review readiness is narrative, not a new
state. Canonical workflow procedures are available even without discovery stubs.
Distillation can propose up to three additional project skills from evidenced,
recurring work. New skills carry no provider/model pins or implied deployment
authorization.

Existing `AGENTS.md`, `CLAUDE.md`, and hook configuration are preserved, with
explicit merge snippets where needed. Run doctor after merging those pointers
and confirm skill discovery in the selected agent.

One subagent role is specified (harness-agnostically, in the scaffold's
`agents/README.md`): the read-only **librarian**, which answers "what does the KB
say about X" in its own context and returns citations — the token-efficient way to
query the KB from a busy main thread.

## The gate (commit-time, deterministic)

`scripts/knowledge-gate.py` runs via pre-commit and blocks, scoped to the staged
overlay so unstaged WIP can't fail it:

1. plan files need `## Status` with a board state;
2. `lessons-log.md` / `operations.md` can't shrink >50% without an archived note (anti-truncation);
3. added knowledge files are born with a TL;DR and a link from another current file;
4. KB status line: present in README+INDEX, modes and SHAs agree, VERIFIED names an existing
   commit, SCAFFOLDED requires the brief.

`--all` checks the full current working tree, including unstaged/untracked notes,
local Markdown link destinations, and bootstrap state. It skips the historical
anti-truncation check, which remains a staged-commit rule. A clean Git index is
not evidence that the full knowledge tree is valid.

## Check the installation

From the initialized repository:

```bash
python3 scripts/knowledge-gate.py --all
python3 scripts/kbase-doctor.py
python3 scripts/kbase-doctor.py --json
python3 scripts/kbase-doctor.py --strict
python3 scripts/kbase-doctor.py --context-only --json
# Once pre-commit is installed through your project's tooling:
pre-commit install
```

Doctor checks generated files, search execution, selected discovery layouts,
source directories, unresolved project markers, and hook/tool availability.
Structural failures return 1. Setup warnings return 0 unless `--strict` is used;
fresh scaffolds normally warn about project placeholders and inactive hooks.
Doctor makes no repairs or dependency installations and does not write a search
query log. Adapter checks validate files and pointers, not a running agent's UI.

`--context-only` inventories local instruction files and imports, the required
INDEX read, and skill discovery metadata without running diagnostic subprocesses.
It reports exact UTF-8 bytes and characters, plus a labeled `ceil(chars / 4)` token
estimate. This is a static inventory, not the model's actual context or billing.
The normal doctor includes the same inventory and advisory size warnings.

The source checkout also provides `bin/kbase doctor <repo>` and
`bin/kbase check <repo>`. Use the full-tree check for KB structure in CI; keep
project lint/typecheck/tests in the project's actual toolchain.

## Keep retrieval small and test its usefulness

```bash
python3 scripts/ksearch.py "schema migrations" --limit 3 --max-bytes 1600
python3 scripts/ksearch.py "session handoff" --json
python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root knowledge
# Equivalent wrapper, from the scaffold checkout:
python3 /path/to/kbase/bin/kbase eval /path/to/project --json
```

Search returns at most five results and **2,400 UTF-8 bytes on stdout by default**,
including citations and JSON syntax. `--max-bytes 0` explicitly removes the byte
cap. Results include source line ranges, heading, and a truncation flag; JSON
remains an array with the original fields. If the budget omits results, a brief
notice goes to stderr. A budget too small for the top citation fails explicitly.
Bytes are enforceable without a tokenizer; they are not model tokens.

The evaluation command separates raw ranking quality from the results that fit
the budget, and reports output bytes including stderr. The supplied 16 cases
check scaffold behavior only. Add real project questions and expected notes,
including no-answer cases, before judging retrieval quality or adding embeddings.
See the [evaluation guide](template/knowledge/practices/retrieval-evaluation.md)
for the format, metrics, and exit codes.

## Ripwire integration

The generated command guide routes task orientation to `--for`, change impact
to `--impact` / `--uses`, and reuse discovery to `--exemplar`. Completion guidance
includes `--quality-delta` and `--test-gate`. Install ripwire from a trusted source
appropriate to your environment, then check its version and `--help`; doctor
reports availability without installing it or configuring an MCP server.

Ripwire is optional and its results are static evidence. `--test-gate` selects
test obligations; it does not run tests. Calibrate source roots and findings
before making advisory output blocking. Actual source, lint, typecheck, and test
results remain authoritative.

## Update generated tooling

```bash
python3 /path/to/kbase/bin/kbase update /path/to/project          # preview only
python3 /path/to/kbase/bin/kbase update /path/to/project --apply  # apply eligible changes
python3 /path/to/kbase/bin/kbase doctor /path/to/project
```

The `.kbase.json` manifest records template version and installed content hashes.
Updates preview diffs and check every managed destination before writing. Local
edits, deletions, symlinks, or unowned collisions block application; files already
matching the new template are accepted. The updater touches only generated
scripts, discovery stubs, and the manifest. Authored knowledge, routers, hook
configuration, and project policy stay unchanged. Adding a new skill requires
its canonical procedure to exist first.

Upgrading a 0.2 installation adds the evaluator script but preserves its knowledge
tree. Supply your own fixture with `kbase eval <repo> --cases <file>`, or review
and copy `template/knowledge/evals/cases.jsonl` plus the evaluation guide first.
Review the updated command/design notes separately; the updater does not overwrite them.

Older installations without a manifest need manual reconciliation; the updater
does not guess ownership. `kbase-init --force` is a deliberate template reset,
not an upgrade command: it overwrites template knowledge files. Incompatible
bootstrap mode changes with a modified/unowned brief are rejected before writes.

## Design

The [design](template/knowledge/docs/agent-memory-architecture.md) uses four memory
tiers, fast retrieval, and deliberate consolidation. Markdown and Git remain the
shared source of truth; agent adapters handle discovery. Search reads live notes,
so there is no persistent index to refresh. Optional retrieval services must earn
their place through measured relevance, cost, freshness, and project isolation.

The September 2026 research covers [agent context standards](docs/research/2026-09-22-agent-context-standards.md)
and [QMD, Letta, Mem0, Graphiti, and retrieval studies](docs/research/2026-09-22-memory-retrieval-market.md).
Those are documented capabilities and research findings, not local product benchmarks.
The [integration report](docs/research/2026-09-22-integration.md) records the changes,
local measurements, validation, and limits.

## Repo layout (this repo)

```
bin/kbase-init        # the scaffolder (mode detection, evidence pack, brief generator)
bin/kbase             # init / doctor / check / eval / update
VERSION               # version written into installation manifests
template/             # everything that gets copied into target repos
tests/                # stdlib unittest suite: python3 -m unittest discover -s tests
```

## License

MIT — see [LICENSE](LICENSE). Scaffolded repos own their copies outright; no attribution
beyond the license is required in projects initialized with kbase.


Test it on a scratch repo before real use: `bin/kbase-init /tmp/scratch`.
