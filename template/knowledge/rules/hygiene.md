# Hygiene — stale material, surfaced failures, pruning

> **TL;DR:** Stale code/docs get removed in the same commit that found them; surfaced preexisting failures get analyzed (fix, delete-stale-test, or plan) — never ignored; the KB gets pruned on a regular audit cadence.

## In-commit hygiene

- Stale code, dead docs, or outdated claims you surface during work get **removed or updated in the same commit** — never left "for later."
- A preexisting test failure you surface must be **analyzed**: fix it, delete the stale test with a recorded reason, or open a plan. Ignoring it is not an option.
- Renames: grep agent configs (`.claude/`, `.codex/`, `.agents/`, `AGENTS.md`) as well as source — prompts rot with renames.

## Pruning cadence

The knowledge base is not an append-only log. On the audit cadence (weekly or monthly — set it in the line below):

**Audit cadence: TODO(project) — e.g. "weekly, Monday"**

1. **Zero/weak-hit audit:** review `_ksearch-log.tsv` (queries logged with their top hit). For every query that returned nothing or the wrong file, add the missing vocabulary to the relevant TL;DRs — this is the system's substitute for embeddings.
2. **Label audit:** spot-check ✅ claims whose evidence commits are old; downgrade or re-verify.
3. **Size audit:** any file over ~400 lines is a split candidate; archive material nobody cited in the last audit window.

Any agent may prune mid-cadence using the same rules. For intentional large pruning (>50% of a protected file: lessons log, operations record), stage an `archive/` note explaining the removal and preserving relevant history. `scripts/knowledge-gate.py` guards against silent truncation at commit time.

## Disposition rules

- Superseded but historically valuable → move under `archive/` with a dated note; never cite as current.
- Wrong and dangerous → delete outright; record the correction in `learning/lessons-log.md` if a future session could repeat the mistake.
- Dated records (incident notes, handoffs) keep their date; their claims may go ⚠ STALE — the date explains the label.
