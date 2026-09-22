# Memory and retrieval options for a small project KB

> **TL;DR:** Keep Markdown + git authoritative and measure bounded lexical retrieval first. QMD is the nearest optional local retrieval experiment; Letta offers useful git-memory design ideas. Mem0 and Graphiti address persistent conversational/entity memory and add ingestion, storage, and freshness obligations that this scaffold has not demonstrated a need for.

Research date: **2026-09-22**. Research only: no dependencies installed, credentials requested, services started, or repository content uploaded. Product statements below describe the opened primary documentation/source, not independently reproduced behavior. Default branches and documentation can change; pin versions before an experiment.

The candidate list preserves the research-stage recommendations; see the subsequent [implementation and measurements](2026-09-22-integration.md) for the approved subset delivered in 0.3.

## Decision matrix

“Fit” is this review's judgment for an agent-agnostic, project-specific KB with low token and maintenance cost, not a benchmark result.

| Approach | Dependencies / where state lives | Retrieval and freshness | Fit for kbase |
|---|---|---|---|
| Current kbase | Python standard library; Markdown + git | Reads current notes per search; field-weighted BM25-style ranking, excerpts, paths | Keep as baseline: no ingestion/model service; vocabulary mismatches and missing notes still need measurement. [Local source](../../template/scripts/ksearch.py) |
| QMD | Node ≥22; SQLite, sqlite-vec, node-llama-cpp; local index and optional GGUF models | Separate lexical, vector, and hybrid modes; index maintenance required | Best optional retrieval comparison after lexical misses are established. [Package](https://github.com/tobi/qmd/blob/main/package.json), [official README](https://github.com/tobi/qmd) |
| Letta Agent SDK / MemFS | Letta runtime; local or cloud agent state; git-backed Markdown memory | `system/` files pinned each turn; other files read on demand | Borrow the small pinned layer and versioned memory ideas; adopting its runtime is a separate architectural choice. [Memory](https://docs.letta.com/agent-sdk/memory), [deployment](https://docs.letta.com/agent-sdk/deployment) |
| Mem0 OSS | Memory library + configured LLM/embedder/vector store and SQL history | Extracts durable facts; semantic/keyword/entity signals; explicit correction lifecycle | Consider for cross-session application/user facts, not as an automatic replacement for repository evidence. [Configuration](https://github.com/mem0ai/mem0/blob/main/docs/open-source/configuration.mdx), [data flow](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/how-it-works.mdx) |
| Graphiti / Zep | Graphiti: Python, graph backend, inference and embeddings; Zep is managed infrastructure | Temporal entities/facts, episode provenance, hybrid retrieval | Consider only if temporal or relationship queries repeatedly fail simpler retrieval. [Official repository](https://github.com/getzep/graphiti) |

## What is actually worth borrowing

**QMD:** `search` uses BM25 without an LLM; `query` adds semantic retrieval, expansion, and reranking. Collections and named indexes provide scope; unscoped searches can span default-included collections. `qmd update` refreshes documents; embedding-model changes also require `qmd embed`. Results support line numbers and targeted `get`; `--max-bytes` skips large multi-get files, rather than enforcing a total token budget. Its fixture-based `bench` compares lexical/vector/hybrid/full modes. These are product capabilities, not proof that QMD outperforms kbase on Nitix. [QMD README](https://github.com/tobi/qmd)

The dependency manifest includes native SQLite bindings, vector extensions, and local inference support even when lexical retrieval is the intended use. This is more operational surface than kbase's standard-library script. “Local inference” should not be expanded into an unverified claim of zero network traffic: the reviewed README did not establish a complete telemetry policy. Model download, runtime behavior, and network access need checking for the pinned release before any trial. [QMD package manifest](https://github.com/tobi/qmd/blob/main/package.json)

**Letta:** current Agent SDK documentation describes MemFS as git-backed Markdown. Agent memory becomes durable through commit/push; shared memory repositories expose a file tree and on-demand reads. Background “dreaming” can consolidate conversations through subagents, with configurable triggers including off. These mechanisms reinforce the value of separating always-present rules from retrieved memory, but background consolidation also consumes inference and can introduce unsupported summaries. The last point is this review's inference, not a measured Letta defect. [Memory documentation](https://docs.letta.com/agent-sdk/memory)

The local backend starts an SDK-owned App Server and retains state/tool execution locally; cloud backends retain cloud state even with execution on a user's computer. Local state placement does not by itself establish local model inference or absence of telemetry. Older database memory-block documentation is under the legacy v1 SDK, so compare a selected deployment/version rather than combining both designs. [Deployment](https://docs.letta.com/agent-sdk/deployment), [legacy stateful-agent model](https://docs.letta.com/v1-sdk/concepts/stateful-agents)

**Mem0:** current OSS configuration offers provider choices including Ollama, but still requires operating the selected models/stores. Current docs explicitly distinguish OSS from Platform graph memory. The documented write path is additive: correcting facts requires explicit update/delete operations. Scope searches using user/agent/run identifiers plus project metadata; these scopes are not a substitute for authorization boundaries. For repository use, attach source path, commit, and verification state rather than trusting a remembered fact after code changes. [Configuration](https://github.com/mem0ai/mem0/blob/main/docs/open-source/configuration.mdx), [memory lifecycle](https://github.com/mem0ai/mem0/blob/main/docs/core-concepts/how-it-works.mdx)

Mem0's current Python telemetry code enables PostHog collection by default and supports `MEM0_TELEMETRY=false`. Captured properties include runtime/provider information and the configured collection name. Inspect the pinned implementation and provider settings before a local-only experiment; “self-hosted” does not automatically mean no outbound calls. [Telemetry source](https://github.com/mem0ai/mem0/blob/main/mem0/memory/telemetry.py)

**Graphiti:** the official implementation provides temporal validity, fact invalidation, and links back to input episodes. It needs a graph backend and defaults to OpenAI inference/embedding; local compatible model endpoints are possible, with documented structured-output reliability concerns for smaller models. Graphiti's opt-out telemetry is documented; `GRAPHITI_TELEMETRY_ENABLED=false` disables it. Zep's managed product is a distinct deployment, not a performance guarantee for self-hosted Graphiti. [Graphiti requirements, architecture, and telemetry](https://github.com/getzep/graphiti)

Its edge schema has group identifiers, episode references, and validity/creation timestamps. For a project KB, ingestion would still have to map these to repository, branch/worktree, source revision, and deletion events. Temporal graph history does not independently establish that a remembered code claim remains valid in today's checkout. [Edge schema](https://github.com/getzep/graphiti/blob/main/graphiti_core/edges.py)

## Evidence on cost and task quality

| Primary study | Reported finding | Limits for this decision |
|---|---|---|
| Gloaguen et al., **Evaluating AGENTS.md**, 2026-02-12 | On SWE-bench Lite and 138 AGENTbench tasks, generated context increased costs and generally hurt resolution; human files modestly improved resolution while adding cost. | Python-focused benchmark; one sampled completion per agent/task setting; evaluates context files rather than this on-demand KB. Useful against excessive instructions, not evidence to delete every project rule. [Paper](https://arxiv.org/html/2602.11988v1) |
| Lulla et al., **On the Impact of AGENTS.md Files**, 2026-01-28 | 124 small PR tasks in ten repositories: lower median runtime and output tokens with existing AGENTS.md. | One Codex/model configuration; selected root files and small changes; no comprehensive correctness evaluation. Median input tokens increased, so the output-token result is not a universal reduction in billed context. [Paper](https://arxiv.org/html/2601.20404v1) |
| Qin and Xie, **Agent Retrieval Bench**, 2026-07-27 | 427 samples across 25 repositories; no retrieval family wins all metrics. RepoMap leads one 8K-token budgeted-yield metric; embedding models lead other metrics. | Diagnostic, uneven repository distribution, largely file-level/static retrieval; does not establish end-to-end patch success. Its useful lesson is to test reachability under a budget and include wrong-repository/no-answer cases. [Paper](https://arxiv.org/html/2607.24882v1) |

These studies provide primary research evidence separate from memory-vendor marketing, but are still limited experiments; none is an independent comparison of all four products against kbase/Nitix. Their differing tasks, models, correctness checks, token categories, and contexts explain why opposite headline findings can coexist.

Mem0's authors report over 90% token-cost savings relative to a full-conversation-context baseline on LoCoMo. This is a **vendor-authored system evaluation**, not an apples-to-apples saving over bounded BM25 snippets, nor a measured saving on code repair. Count extraction/update calls and storage/index work when designing a local comparison; do not substitute that headline for a kbase estimate. [Mem0 paper](https://arxiv.org/abs/2504.19413)

QMD's bundled example fixture is developer-provided evidence, not an independent corpus evaluation. Prefer a held-out set of real project questions. None of the reviewed sources establishes that adding every available skill, memory service, or retrieval tool minimizes total task cost.

## Concrete low-cost candidates, in order

These are proposals for a later approved implementation, not changes made in this research pass.

1. **Budget existing retrieval first.** Start experiments at 500–1,000 tokens of retrieved KB text per query; preserve path/heading/line pointers and fetch more only when needed. These are initial test budgets, not universal optima. A result-count limit alone cannot guarantee a token cap.
2. **Measure 30–50 project queries before adding models.** Cover exact symbols/commands, domain synonyms, architecture decisions, past failures, active plans, and handoff recovery. Include stale/deleted notes, two worktrees, archived material, unrelated repositories, and questions with no answer. Record expected notes/spans and acceptable abstention.
3. **Try metadata and lexical fixes.** Test aliases/tags, headings/TL;DR quality, explicit area filters, duplicate removal, and “no useful result” fallback. Preserve source evidence and surface stale verification instead of creating authoritative-sounding summaries.
4. **Optional QMD trial only after real lexical misses.** Use a dedicated project index/collection and matching current-note exclusions. Compare lexical versus vector/hybrid at the same output budget on the same frozen notes, then test edits/deletions and measure refresh lag. Do not install a daemon or enable automatic repository update commands by default.
5. **Defer persistent memory services.** Reconsider Letta integration for a deliberate resident-agent workflow; Mem0 for reusable application/user facts; Graphiti for demonstrated temporal or multi-hop entity questions. Keep the canonical project KB independently readable and exportable.

## Acceptance criteria for any integration

- **Cost accounting:** record uncached input, cached input, output, retrieval-result tokens, model-based ingestion/reranking/consolidation calls, latency, and local CPU/RAM/disk. Record tokenizer or estimation method. Compare cost per successfully completed task as well as raw tokens.
- **Relevance:** use held-out queries, Recall@k/MRR where useful, span-level useful tokens per returned token, and an end-to-end correctness subset. A shorter wrong answer is not a win. Log failure categories locally rather than uploading prompts.
- **Freshness:** record source content hash plus repository revision and dirty/worktree identity. Test note edit, deletion, rename, branch switch, and embedding-model changes. Stale indexes must warn or fall back to live files.
- **Provenance:** every retrieved assertion needs a source pointer; derived memories retain source evidence and verified/provisional status. Preserve git reviewability and explain how corrections invalidate derived copies.
- **Scope:** default to the current project and current notes. Explicit opt-in for archive or cross-project retrieval. Use the same scope in ingestion and querying; never assume a global collection's default is safe for a project-specific answer.
- **Operations:** pin versions, document rebuild/export/delete paths, inspect telemetry and actual provider calls, and report setup/refresh costs. No new backend becomes a required scaffold dependency without measured benefit over the baseline.

The immediate recommendation is a measurable retrieval budget and project query set. The market supports increasingly sophisticated memory, but sophistication alone does not show that this small KB needs another persistent system.
