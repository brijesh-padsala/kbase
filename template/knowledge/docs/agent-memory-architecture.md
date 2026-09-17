# Agent memory & context architecture (knowledge/ as the unified agent stack)

> **TL;DR:** `knowledge/` IS this project's agent memory and context system: a 4-tier memory hierarchy plus a dual loop (fast per-session retrieval, slow consolidation) implemented as plain files + git + CLI retrieval — `ksearch` for knowledge, `ripgrep`/`rg` for code, `rg` for literals. Deliberately excluded: memory servers (Letta/Zep-class), vector-first retrieval, and LLM-indexed knowledge graphs (GraphRAG/Cognee/graphify). Evaluating a memory or context-engineering tool? Read §5 before installing anything.
> **Read when:** deciding where new knowledge should live; explaining or extending the KB design; evaluating a memory/context tool. **Skip when:** you need behavioral rules ([rules/](../rules/)) or commands ([practices/commands.md](../practices/commands.md)) — this page is the design map, not the rules.

**Baseline:** design/policy record (not code claims). Behavioral authority is [write-back-policy.md](../rules/write-back-policy.md) — when this page and a rule disagree, the rule wins and this page gets patched. Provenance: design distilled from a production trading-system KB (2026-09).

## 1. Design goals

| Goal | How the design meets it |
|---|---|
| **Agent-agnostic** | Markdown + git + CLI is the only substrate every agent reads natively. No daemon, no service, no per-agent store; tool-specific wiring is quarantined in `agents/<name>/WIRING.md`. |
| **Unified** | One source of truth for all agents, entered via [INDEX.md](../INDEX.md). Agent-native memory is forbidden by the [write-back policy](../rules/write-back-policy.md) — native stores may carry routing pointers only. |
| **Token-cheap** | Agents retrieve excerpts, never whole files: `ksearch` returns ranked ~500-token excerpts with file pointers; `rg`/structural tools answer who-calls-what without reading bodies. The routing table in root `AGENTS.md` picks the cheapest tool per question type. |

## 2. The four memory tiers

The standard agent-memory hierarchy, mapped onto this repo:

| Tier | Location | Authority |
|---|---|---|
| **Working** (this session) | the agent's own context window; files pulled on demand via the routing table | root `AGENTS.md` "Search, don't read" |
| **Episodic** (what happened) | [plans/](../plans/README.md) board + handoff artifacts; `plans-archive/` is history, never cited as current | plans board README |
| **Semantic** (what's true) | [docs/](architecture.md) verified architecture + specs; [memory/operations.md](../memory/operations.md) operational facts | per-file verification baselines |
| **Procedural** (how to act) | [rules/agent-contract.md](../rules/agent-contract.md) constraints; [practices/](../practices/commands.md) conventions | rules/ + practices/ |

Every session starts at [INDEX.md](../INDEX.md); its "Where to look first" table is the memory router.

## 3. The dual loop

**Fast loop (per session):** INDEX.md → route by question type (`ksearch` / structural code query / `rg`) → act → write back per policy. Nothing enters context that retrieval didn't rank first.

**Slow loop (consolidation):** knowledge commits ride with the code that taught them; [hygiene](../rules/hygiene.md) removes stale material in the same commit; the periodic audit prunes and fixes retrieval vocabulary; lessons distill into [learning/](../learning/lessons-log.md). The slow loop is what keeps the fast loop's answers trustworthy.

## 4. Forgetting is deterministic, not decay

No Ebbinghaus-style fading. A memory must be either verified-current or explicitly pruned — never silently weakened: decay scoring cannot distinguish a live critical-path doc from an obsolete note. Mechanisms: the dated-record vs live distinction (README legend), verification baselines per file, and in-commit hygiene removal.

## 5. Deliberately excluded (evaluated — do not re-litigate without new evidence)

| Excluded class | Examples | Why rejected |
|---|---|---|
| Memory servers | Letta/MemGPT, Zep | Agent-native memory by another name — forbidden by the write-back policy; adds a daemon, index staleness, and vendor lock-in |
| LLM-indexed knowledge graphs | GraphRAG, Cognee, graphify | Enrichment ships repo content through external LLM APIs (egress); a second graph over docs+code becomes a stale second source of truth; no equivalents of deterministic commit-time gates |
| Vector-first retrieval | embedding indexes | Unmeasured need: BM25 + field weights serves a curated KB; embeddings add a second index that can drift. Revisit only if the `_ksearch-log.tsv` zero-hit audit proves fuzzy-recall misses |

**Adoption bar for any future memory/context tool:** it must beat "files + git + CLI" on agent-agnosticism AND token cost AND add a workflow gate verb. Otherwise it may exist only as a derived, regenerable VIEW — never as the memory itself.

## 6. Token economy & retrieval-quality measurement

- The TL;DR-first file format is load-bearing: ksearch field-weights TL;DR/description above headings above body. A file without a TL;DR is both harder to retrieve and more expensive to read.
- ksearch logs every query with its top hit (`knowledge/_ksearch-log.tsv`). Periodically auditing zero/weak-hit queries is this system's substitute for embeddings: fix misses by adding the missing vocabulary to the relevant TL;DRs.
- If that audit ever proves fuzzy-conceptual misses BM25 cannot serve, the sanctioned upgrade is LOCAL embeddings as a fallback layer inside ksearch (index regenerable from files, no external API) — not a memory service.
