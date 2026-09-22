# distill — bootstrap distillation pass

> **TL;DR:** Turn a SCAFFOLDED knowledge base into a VERIFIED one: verify the evidence pack, write architecture/pitfalls/operations with per-claim labels, fill TODO markers, and prepare the status flip and brief deletion as one validated change.
> **Invoke when:** KB status is SCAFFOLDED or `knowledge/_bootstrap-brief.md` exists. **Skip when:** status is already VERIFIED (nothing to distill).

**Preconditions:** you have access to the source and permission to edit the KB. The KB is untrustworthy until this pass completes — do not cite it meanwhile.

## Steps

1. **Read `knowledge/_bootstrap-brief.md` fully.** Its evidence pack is mechanical and can be wrong. Before building on any line (stack claim, LOC count, entry point, history theme), verify it against source using [structural tools](../commands.md), targeted `rg`, and file reads. Wrong evidence gets corrected in your output — never propagated.
2. **Write `knowledge/docs/architecture.md`** (replace the stub): stack tiers, how components connect, data flow, entry points, data stores, external interfaces. Every claim labeled ✅ with evidence (`path:line`, config excerpt) or ❓. Update the file's verification baseline to the commit you verified against. Keep the TL;DR updated to the real architecture.
3. **Write `knowledge/learning/pitfalls.md`** (replace the stub): start from the brief's git-history themes (recurring `fix` types, hot scopes) and your code reading. Each pitfall: the trap, the symptom, the avoiding rule, ✅/❓.
4. **Write `knowledge/memory/operations.md`** (replace the stub): environments, endpoints, run/deploy steps — only what's verifiable from configs and scripts in this checkout. Never inline secrets (name their location). Runtime claims you can't check stay ❓.
5. **Fill the TODO markers:** `rg -n 'TODO\((project|distillation)\)' knowledge/` — at minimum the quality-gates commands, boundaries tiers, and hygiene audit cadence. An unfilled TODO(project) after this pass is a failure.
6. **Record first lessons** in `learning/lessons-log.md` (append-only, dated, ✅/❓ — format in that file) if the history taught anything durable. Propose at most three project-specific skills only when repeated workflows are evidenced by actual scripts, CI, or recurring history. For each proposal give the trigger, evidence paths, procedure boundary, and completion check; propose none when repetition is unproven. Keep project facts in the KB rather than discovery stubs.
7. **Prepare the flip and deletion together:**
   - status line in `knowledge/README.md` **and** `knowledge/INDEX.md` → `**KB status:** VERIFIED @ <commit-you-verified-against> (<date>)`
   - delete `knowledge/_bootstrap-brief.md`
   - run `python3 scripts/knowledge-gate.py --all` and `python3 scripts/kbase-doctor.py`; resolve structural errors and any unfilled project markers
   - when a commit is authorized, stage the flip and deletion together, run the staged gate, and commit as `knowledge: distillation pass — KB VERIFIED`
   - the gate verifies the named commit exists and that VERIFIED and the brief never coexist; report remaining environment warnings and validation evidence

## Rules of engagement

- TL;DR-first on every file you touch (ksearch ranks on it).
- Prefer deleting an unverifiable claim over guessing a label. Do not invent.
- Write for a competent newcomer who has the code open: claim + evidence, not prose.
