# Write-back policy (all agents)

> **TL;DR:** Knowledge lives in `knowledge/`, committed with the code that taught it. Agent-native memory is routing pointers only. Default answer to "should I remember this?" is no.

## Rules

1. **Default is DON'T write.** Record only what a future session would otherwise re-derive painfully or dangerously. When in doubt, don't — hygiene prunes more reliably than hindsight restores.
2. **New facts, lessons, pitfalls, rules → `knowledge/`**, in the right subdir per [INDEX.md](../INDEX.md):
   - hard constraints → `rules/`
   - how-we-build (commands, conventions) → `practices/`
   - verified architecture/specs → `docs/`
   - operational facts (environments, incidents, endpoints) → `memory/`
   - dated lessons → `learning/lessons-log.md` (append-only); distilled pitfalls → `learning/pitfalls.md`
   - plans/specs/proposals → `plans/` (one numbered file per plan, `## Status` section required)
3. **Plans/specs/proposals → `knowledge/plans/` ONLY.** Whatever plan tool your framework gives you (plan mode, mission specs), the output file lands in `plans/<NNN>-<slug>.md`; update the board in `plans/README.md`. Never your native plans dir.
4. **Commit knowledge changes with the code that taught them.** A lesson without its evidence commit is an unverifiable claim.
5. **Stale code/docs found during work get REMOVED/updated in the same commit** — see [hygiene.md](hygiene.md).
6. **Don't duplicate**: `ksearch "<topic>"` first; patch the existing file instead of creating a near-copy.
7. **Your native memory is routing only** — at most a pointer: "project knowledge → repo `knowledge/` + INDEX.md". Tool-specific wiring syntax may live in `agents/<name>/WIRING.md` and nowhere else.

## Why

Files + git are the only agent-agnostic memory substrate: every agent reads them, they diff and review, and they survive tool churn. The design is spelled out in [docs/agent-memory-architecture.md](../docs/agent-memory-architecture.md).
