# Agent context standards and portable discovery

> **TL;DR:** Keep one canonical project KB, a small startup router, and task-triggered procedures. Current standards support this shape; adding more automatically discovered material still spends context. Improve compatibility diagnostics and measure startup/retrieval cost before adding adapters or skills.

Research date: 2026-09-22. Primary documentation was opened and read; this is research only. Product behavior below is **published behavior**, not independently tested behavior. Recommendations are **inferences** for kbase. No vendor token-saving percentage is treated as a measurement of this repository.

The candidate list preserves the research-stage recommendations; see the subsequent [implementation and measurements](2026-09-22-integration.md) for the approved subset delivered in 0.3.

## Published loading contracts

| Surface | What loads broadly | What loads conditionally | Constraint / source |
|---|---|---|---|
| AGENTS.md | Applicable project instructions | Nested instructions for the relevant subtree | Plain Markdown, no mandatory schema; nearest instructions take precedence. Individual harnesses decide discovery details. [Official format](https://agents.md/) |
| Agent Skills | Skill name and description for discovery | Full skill on activation; references/resources as needed | Spec guidance: metadata approximately 100 tokens per skill, body below 5,000 tokens recommended, SKILL.md below 500 lines. These are guidance, not universal runtime limits. [Specification](https://agentskills.io/specification) |
| Claude Code memory | Root/ancestor instruction files; unscoped rules | Nested files and path-scoped rules when matching files are read | `@` imports expand eagerly; moving content into imported files does not remove startup cost. [Memory docs](https://code.claude.com/docs/en/memory) |
| Claude Code skills | Names/descriptions by default | Skill bodies on invocation | Manual-only skills can omit descriptions from context; invoked content persists across subsequent turns. [Skills docs](https://code.claude.com/docs/en/skills) |
| Cursor rules | `alwaysApply: true` content | Glob-matched, relevance-selected, or manually mentioned rules | `.cursor/rules` requires `.mdc`; ordinary `.md` is ignored there. Root and nested AGENTS.md are supported. [Rules docs](https://cursor.com/docs/rules) |
| Copilot instructions | Repository-wide instruction file | Path-specific files matching `applyTo`; agent files on supported surfaces | Support varies by IDE and Copilot feature. [Instruction guide](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions), [support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support) |

## Important portability details

### AGENTS.md is a shared entry point, not a shared enforcement engine

The format intentionally has no required headings. Its official guidance supports nested files and gives explicit user prompts precedence over file instructions. This establishes a useful common document surface, but does not prove identical loading, precedence, or compliance in every client. [Official format](https://agents.md/)

**Implication:** retain kbase's root router and canonical `knowledge/` files; describe tested clients and fallbacks rather than promising every client automatically discovers every adapter.

### Claude: retain the import adapter, avoid importing the whole KB

Current docs describe native AGENTS.md support from v2.1.277, subject to session/feature availability and the presence of CLAUDE.md files. A CLAUDE.md containing `@AGENTS.md` remains supported and is deduplicated. Relative imports resolve against their containing file; import recursion is limited to four hops. Rules without `paths` load at launch; scoped rules activate on matching reads. Anthropic recommends CLAUDE.md under 200 lines. [Memory docs](https://code.claude.com/docs/en/memory)

**Implication:** kbase's import is a compatibility bridge. Keep it pointing only to the compact router; use ordinary links or explicit read instructions for task-specific KB material. Adding CLAUDE imports for every knowledge directory would undo that boundary.

### Skills: portability has a small common core

The standard requires `name` and `description`; names must match their directory, with length/character restrictions. `allowed-tools` is experimental. Relative references resolve from the skill root, and the spec recommends shallow reference chains. Product-specific invocation flags should not be assumed portable merely because SKILL.md is shared. [Specification](https://agentskills.io/specification)

Claude project skills live under `.claude/skills`. `disable-model-invocation: true` hides the description from normal context and requires user invocation; `user-invocable: false` does not remove its discovery cost. Claude's description listing has a context-dependent budget and may shorten descriptions; `/doctor` and `/context` expose diagnostics. Its current docs also describe compaction budgets for invoked skills. These are client/version details, not cross-client guarantees. [Claude skills](https://code.claude.com/docs/en/skills)

**Implication:** retain concise frontmatter and avoid default model pins, tool permission grants, or harness execution syntax in canonical procedures. Keep core discovery small and make additional workflows optional.

### Cursor: existing project stubs already cover much of the integration

Cursor documents discovery in `.agents/skills/` and `.cursor/skills/`, plus compatibility with `.claude/skills/` and `.codex/skills/`. It supports `paths` scoping and manual-only invocation. Its user-level `~/.agents/skills` is not copied automatically to remote/cloud sessions; repository skills travel with the checkout. [Cursor skills](https://cursor.com/docs/skills)

Cursor recommends focused rules, canonical references instead of duplicated material, and adding rules after observed repeated mistakes. Always-applied rules ignore glob/description conditions; use matching or relevance-based rules for local concerns. [Cursor rules](https://cursor.com/docs/rules)

**Implication:** do not generate another set of `.cursor/skills` by default. With kbase's dual adapters, Cursor can encounter same-name skills in `.agents` and `.claude`; actual duplicate handling/precedence needs a client test before claiming either doubled cost or deduplication.

### Copilot: select the target surface before adding an adapter

Repository-wide instructions use `.github/copilot-instructions.md`; scoped instructions use `.github/instructions/*.instructions.md` with `applyTo` globs. Applicable repository-wide and scoped instructions are combined. [Instruction guide](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions)

The support matrix lists AGENTS.md for cloud agent and several IDE/CLI contexts, while GitHub.com Chat lists repository-wide instructions rather than agent files. Therefore “Copilot supports AGENTS.md” is insufficient to promise coverage for every Copilot user. [Support matrix](https://docs.github.com/en/copilot/reference/custom-instructions-support)

**Implication:** a future Copilot adapter should be opt-in and tested for the chosen surface. Avoid copying the whole KB into its repository-wide file or assuming a Markdown link automatically imports its target.

## Grounding in the current kbase template

- [Root router](../../template/AGENTS.md.tmpl) already distinguishes KB retrieval, structural code queries, and literals. It requires reading INDEX first and the plan board before edits; these required reads are part of practical session cost even though they are not automatically injected by every client.
- [Skills catalog](../../template/knowledge/practices/skills/README.md) already separates three core skills from four optional workflow skills. This is aligned with conditional discovery rather than shipping every available skill by default.
- [Handoff stub](../../template/skills/kb-handoff/SKILL.md) points outside its own directory to the canonical KB. That works as repository wiring; copying only the skill directory into another product leaves its dependency behind. This is a packaging limitation, not a violation of the skill format.
- [Distill procedure](../../template/knowledge/practices/skills/distill.md) derives a bounded number of skills from real recurring work. Agent Skills guidance likewise favors project artifacts and execution traces, and recommends removing instructions that do not improve results. [Authoring guidance](https://agentskills.io/skill-creation/best-practices)

## Minimal candidate integrations — proposals, not implemented

1. **Add a context-cost report to doctor.** Inventory the router, configured eager imports, required first-read files, and discovered skill descriptions per selected harness. Report exact bytes/lines first; label token counts as estimates unless a model tokenizer is used. Detect duplicate skill names and unresolved adapter links. This would expose cost without introducing a retrieval service.
2. **Make adapter compatibility explicit.** Track tested discovery paths, import behavior, and minimum versions only where verified. Keep CLAUDE's current bridge; reuse `.agents` for Cursor; add Copilot wiring only for a requested target. A static doctor can verify files, but cannot prove the live client loaded them.
3. **Reduce unconditional navigation only after measuring it.** Compare current INDEX-plus-board startup with a compact router that reads the board for active/resumed work and retrieves only relevant sections. Keep critical constraints reachable and test task correctness before adopting a shorter route.
4. **Offer scoped instructions only for proven subsystem needs.** Start with nested AGENTS.md where supported; generate harness-specific `paths`/`globs`/`applyTo` wrappers from one canonical rule if required. Test each glob against real paths. Do not make all KB rules unconditional startup rules.
5. **Declare repository-bound versus standalone skills.** Keep stubs as the default; if export is requested, materialize the canonical procedure and required resources into a self-contained skill package, then validate its links. This avoids maintaining duplicate source procedures.

## Verification needed before claiming lower token consumption

- A fixed set of tasks: fresh onboarding, rule lookup, code change, review, and handoff/resume.
- For each supported harness, record discovered files/skills, actual startup context where available, requested file bytes, tool-output size, retrieval calls, latency, and task correctness.
- Compare current and proposed routing under the same task/model/settings. Separate cached-input billing from actual context volume; smaller disk files alone do not prove a cheaper conversation.
- Validate skill triggering with both matching and near-miss requests. Fewer loaded instructions are useful only if required rules and evidence remain available.

The convergence visible in these documents is toward a small common entry point plus scoped or activated content. It supports kbase's basic design. It does **not** establish that more defaults, one universal adapter, or any particular token-saving percentage will improve this repository without measurement.
