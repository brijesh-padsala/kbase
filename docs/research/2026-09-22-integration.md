# Research-driven retrieval and context improvements

> **TL;DR:** Keep the shared Markdown/Git KB and small skill set. Version 0.3 adds bounded search with source lines, fixes lost titles, measures retrieval quality, and inventories startup context. The evidence supports these changes before introducing another memory backend.

## Decision and implementation

The [standards review](2026-09-22-agent-context-standards.md) supports a small shared entry point with skills and references loaded when needed. The [market review](2026-09-22-memory-retrieval-market.md) identifies QMD as a useful optional retrieval comparison and distinguishes Letta, Mem0, and Graphiti's different memory use cases. Published features are not evidence that these products improve this project's tasks.

The approved scope was bounded retrieval and citations, the title-indexing fix, local retrieval evaluation, startup diagnostics, and updated research/design notes. Implemented:

- **Search:** default 2,400-byte UTF-8 stdout budget, explicit unbounded mode, ranked passages with line ranges/headings, truncation status, and compatible JSON arrays. Too-small budgets fail explicitly. Excerpt matching and scoring share token boundaries.
- **Indexing:** preserve titles and pre-TL;DR text without double-counting the summary. Normalize leading dashes so queries for CLI flags match their spelling in notes.
- **Evaluation:** JSONL project judgments, raw versus displayed MRR/recall/any-hit, no-answer cases, exact stdout/stderr bytes, and corpus fingerprint. Starter questions exercise the scaffold; they are not a real-project benchmark.
- **Context inventory:** exact local instruction/import sizes, required INDEX reading separately, and skill metadata per selected adapter. Estimates use characters/4, with explicit limits on what the report models.
- **Integration:** `kbase eval`, `doctor --context-only`, generated-tool updates, documentation and audit workflow. The three default skills and the root router remain unchanged.

No new runtime dependencies, services, model calls, or persistent search index were added. More default skills were not justified: discovery metadata itself uses context. Existing thin adapters remain the compatibility layer.

## Local diagnostic comparison

Compared original retrieval at commit `94f31ce` against the final implementation on a frozen rendered 0.2 scaffold and the existing Nitix knowledge tree, read-only. Sixteen illustrative queries were fixed before implementation: eight scaffold questions and eight project questions. These were diagnostic queries with plausible target files, not independently judged gold labels or an end-to-end task benchmark.

| Measure | Original | Updated |
|---|---:|---:|
| Total human-format stdout across 16 queries | 45,798 bytes | 34,839 bytes |
| Largest individual stdout | 3,580 bytes | 2,400 bytes |
| Scaffold notes with title-only words lost by the parser | 17 / 25 | 0 / 25 |
| Nitix notes with title-only words lost by the parser | 76 / 156 | 0 / 156 |
| Canonical onboarding note for `new agent onboarding` | Not ranked | Rank 1 |
| Canonical handoff note for `kb-handoff` | Not ranked | Rank 1 |

That is **23.9% less stdout**, not a token-billing or task-cost saving. The comparison excludes stderr notices, and some illustrative questions still rank their plausible target poorly. The separate evaluator includes diagnostic overhead and makes lost recall visible. Do not infer global retrieval improvement from the two fixed title regressions.

Measurement method: render the original scaffold once, run its old retrieval modules, then swap only `ksearch.py` and `kbformat.py` while preserving note contents and queries. Use `KSEARCH_NO_LOG=1`; measure encoded UTF-8 output rather than estimated tokens. The Nitix tree was read without edits. Scratch artifacts are `/tmp/kbase-retrieval-audit-20260922.jsonl` and `/tmp/kbase-retrieval-audit-final-20260922.jsonl`; they are local session evidence, not portable fixtures. The checked-in evaluator and starter cases support repeatable future comparisons on a chosen project corpus.

## Starter evaluation and startup inventory

On one generated 0.3 scaffold with default adapters, workflow discovery off, the same 16 starter judgments and limit 5 produced:

| Stdout budget per query | Displayed recall@5 | Stdout bytes, all queries | Stderr bytes | Total output bytes |
|---|---:|---:|---:|---:|
| 2,400 (default) | 0.9423 | 29,792 | 483 | 30,275 |
| 1,600 | 0.8654 | 20,361 | 828 | 21,189 |
| Unbounded | 0.9423 | 34,627 | 0 | 34,627 |

All three runs passed 16/16 cases: every positive query displayed at least one relevant file, and the three no-answer cases abstained. MRR was 0.8333 throughout. The default saved **12.6% of total output bytes** against unbounded output with the same displayed recall on this fixture. A smaller budget saved more bytes but lost recall despite passing every case. These JSON measurements use the new implementation in all three runs; they are a different comparison from the old-versus-new human output above.

The shared corpus fingerprint was `86686a9045fa42e8aa4a87e746a3549a6b91519e36bd07c347a1d46fbed9d8e4`. A generated project's name and baseline commit affect rendered notes and this fingerprint. The fixture remains unchanged across runs; it establishes scaffold behavior, not Nitix task quality.

The default context inventory measured 2,194 bytes for AGENTS plus the Claude import bridge, 2,648 bytes for the separate required INDEX read, and 485 bytes of skill metadata per adapter. The unique router-plus-INDEX total was 4,842 bytes (approximately 1,205 tokens by `ceil(chars/4)`). Do not add both adapters' metadata as if one client necessarily loads both. No missing/skipped imports were reported. These startup sizes have not been reduced by this change; the new diagnostics make their cost visible.

Session reproduction script and outputs: `/tmp/kbase-final-measurements-20260922-_2wjv78l/measure.py` and `summary.json`. Run the script with the kbase checkout and a new empty output directory. Portable future evaluations use the checked-in fixture and CLI documented in the evaluation guide.

## Validation and remaining evidence

- **136 unit/integration tests pass**, including Unicode budgets, precise citations, empty results, schema compatibility, evaluator failures, context import deduplication, and installed commands.
- A real **0.2 → 0.3 upgrade** from `94f31ce` added the evaluator while preserving all authored knowledge bytes; the full-tree gate and 16 starter evaluations passed afterward using an explicit fixture.
- Python source compilation and `git diff --check` passed. Ripwire quality/test guidance was inspected; its static findings include complexity, test duplication, compatibility helpers, and subprocess-driven paths it cannot map. The executed test suite is the verification evidence; the static reports are not all-green quality verdicts.

Next evidence should come from 30–50 real project questions and a held-out task set, with actual model input/cache/output usage and correctness. Compare an optional QMD index only after identifying persistent lexical misses; test freshness and project/worktree scope separately. Startup inventory does not model global instructions, every native client scope, or actual skill triggering. See the shipped [evaluation guide](../../template/knowledge/practices/retrieval-evaluation.md) for commands, metrics, and limits.
