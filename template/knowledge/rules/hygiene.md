# Hygiene — stale material, surfaced failures, pruning

> **TL;DR:** Stale code/docs get removed in the same commit that found them; surfaced preexisting failures get analyzed (fix, delete-stale-test, or plan) — never ignored; the KB gets pruned on a regular audit cadence.

## In-commit hygiene

- Stale code, dead docs, or outdated claims you surface during work get **removed or updated in the same commit** — never left "for later."
- A preexisting test failure you surface must be **analyzed**: fix it, delete the stale test with a recorded reason, or open a plan. Ignoring it is not an option.
- Renames: grep agent configs (`.claude/`, `.codex/`, `.agents/`, `AGENTS.md`) as well as source — prompts rot with renames.

## Pruning cadence

The knowledge base is not an append-only log. On the audit cadence (weekly or monthly — set it in the line below):

**Audit cadence: TODO(project) — e.g. "weekly, Monday"**

Run the canonical procedure: [practices/skills/kb-audit.md](../practices/skills/kb-audit.md) — query-log review, label spot-check, reference audit, size/splits.

Any agent may prune mid-cadence using the same procedure. Intentional large pruning of protected files needs a staged `archive/` note ([kb-maintenance.md](kb-maintenance.md)).

## Disposition rules

- Superseded but historically valuable → move under `archive/` with a dated note; never cite as current.
- Wrong and dangerous → delete outright; record the correction in `learning/lessons-log.md` if a future session could repeat the mistake.
- Dated records (incident notes, handoffs) keep their date; their claims may go ⚠ STALE — the date explains the label.
