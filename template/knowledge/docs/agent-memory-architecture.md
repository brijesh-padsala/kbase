# Agent memory and context architecture

> **TL;DR:** Markdown and Git hold shared project knowledge. Small agent entry points route to current notes, bounded search returns cited evidence, and deliberate consolidation keeps it useful. Measure relevance and output size before adding a retrieval backend or memory service.
> **Read when:** extending the KB or evaluating a memory/context tool. **Skip when:** you need [behavioral rules](../rules/agent-contract.md) or [commands](../practices/commands.md).

**Baseline:** design policy, informed by a production project KB and primary-source research on 2026-09-22. The [write-back policy](../rules/write-back-policy.md) governs project facts; product documentation below describes capabilities, not locally benchmarked results.

## Shared memory, thin adapters

`knowledge/` is the reviewable source of truth. Root `AGENTS.md` and the required [INDEX](../INDEX.md) provide routing and critical policy; details are read when needed. Skill discovery exposes names/descriptions, with thin stubs pointing to canonical procedures. Keep project facts out of duplicate agent stores.

[AGENTS.md](https://agents.md/) and [Agent Skills](https://agentskills.io/specification) provide portable conventions, but discovery and instruction precedence depend on the harness. Verify the selected adapter in its actual client. Importing another instruction file can load it eagerly; an import is not automatically a token saving.

## Four memory tiers

| Tier | Location | Use |
|---|---|---|
| Working | Current task context | Objective and just enough evidence to act |
| Episodic | [Plans and handoffs](../plans/README.md) | Progress, ownership, decisions, next action; archives are history |
| Semantic | [Architecture](architecture.md), [operations](../memory/operations.md), verified notes | Current facts with source and verification baseline |
| Procedural | [Rules](../rules/agent-contract.md), [practices](../practices/commands.md), skills | Constraints and repeatable procedures |

**Fast loop:** route the question → retrieve relevant evidence → inspect cited source as needed → act. Use ksearch for knowledge, optional structural tools for code, and `rg` for literals.

**Consolidation loop:** record costly-to-rediscover facts with the code that taught them, recheck changed evidence, correct or remove stale notes, and evaluate retrieval through [kb-audit](../practices/skills/kb-audit.md). Critical rules do not decay because they are rarely queried. Archives preserve history without entering default retrieval.

## Enforce output size; measure relevance

ksearch reads current files on each call, field-weights descriptions/TL;DRs above headings above body, and returns one cited passage per file. It caps successful stdout at 2,400 UTF-8 bytes by default, including serialization and source pointers. A result limit alone does not bound output. Budget omissions are explicit; `--max-bytes 0` is a deliberate unbounded read.

The [evaluation guide](../practices/retrieval-evaluation.md) separates raw ranking from results visible within the budget. Use real questions, expected files, no-answer cases, and a held-out set. Diagnose missing knowledge, vocabulary mismatch, wrong rank, and budget omissions separately. A shorter irrelevant result is not an improvement.

Doctor reports local instruction/import sizes, required INDEX reading, and per-adapter skill metadata separately. Character-based token estimates are rough: actual tokenization, cached input, tool definitions, harness instructions, and repeated turns determine total cost. Neither the static inventory nor the starter fixture establishes end-to-end task savings.

These choices follow the just-in-time retrieval and minimal high-signal context principles in [Anthropic's context engineering guidance](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), and bounded tool output plus evaluation in its [tool design guidance](https://www.anthropic.com/engineering/writing-tools-for-agents).

## Optional tools: adopt for a demonstrated gap

| Approach | Useful capability | Adoption evidence needed |
|---|---|---|
| [QMD](https://github.com/tobi/qmd) | Local lexical/vector/hybrid retrieval and reranking | Held-out conceptual misses improved at equal output budgets; justify dependencies, index refresh and model cost |
| [Letta MemFS](https://docs.letta.com/agent-sdk/memory) | Git-backed Markdown memory with pinned and on-demand files | A resident-agent workflow needs its runtime; shared project facts stay exportable and reviewable |
| [Mem0](https://github.com/mem0ai/mem0) | Extraction and retrieval of durable application/user facts | Fact correction and project scoping work; account for extraction, inference, embedding and storage costs |
| [Graphiti](https://github.com/getzep/graphiti) | Temporal relationships and episode provenance | Repeated relationship/time queries need a graph; verify evidence invalidation and ingestion freshness |

These are optional experiments, not default dependencies or blanket rejections. Local model/provider configurations vary; inspect a pinned version's actual network behavior and telemetry rather than inferring it from a product category.

Any derived index must be regenerable from canonical notes, scoped to the project, and tested after edits, deletions, renames, and branch/worktree changes. Compare against bounded lexical retrieval on the same frozen corpus; measure relevance, task correctness, output cost, latency, setup, and refresh effort. Warn or fall back to live files when stale. Do not turn retrieved or extracted text into a higher-priority instruction source.
