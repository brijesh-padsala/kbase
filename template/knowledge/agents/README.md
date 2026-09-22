# Per-agent wiring

> **TL;DR:** Tool-specific connection syntax lives in `agents/<name>/WIRING.md` — one file per agent tool — and nowhere else.

## Shipped adapters

Init defaults to `--agents codex,claude`; select `--agents codex`, `--agents claude`, or `--agents none` to change discovery wiring. Codex uses `.agents/skills/<name>/SKILL.md`. Claude uses `.claude/skills/<name>/SKILL.md` and a `CLAUDE.md` import of `@AGENTS.md`. Existing entry-point instructions are preserved; merge any generated router guidance and verify the selected harness can discover the stubs.

Both adapters point to the same [canonical procedures](../practices/skills/README.md) and root `AGENTS.md` router. Core skills are distill, kb-audit, and kb-handoff; `--workflow` adds discovery for kb-plan, kb-implement, kb-review, and kb-board. The procedures are always present in the KB even when no adapter is selected.

Run `python3 scripts/kbase-doctor.py` after installation or a wiring change. Adapter paths are connection details; they are not additional stores for project facts.

## Additional agents

When configuring a new agent tool (claude, codex, cursor, factory, gstack, hermes, …):

1. Create `agents/<name>/WIRING.md` describing how THAT tool connects to this KB: which entry-point file it reads natively (AGENTS.md / CLAUDE.md / .cursorrules / …), how it should invoke `scripts/ksearch.py`, and any tool-specific routing.
2. Keep it wiring-only: tool syntax, not project knowledge. Anything another agent would also need belongs in a topical file under `rules/`, `practices/`, etc.
3. If the tool supports native memory/rules stores, they hold routing pointers only ("project knowledge → repo `knowledge/` + INDEX.md") per [write-back-policy.md](../rules/write-back-policy.md).

## The librarian role (read-only subagent)

A **librarian** answers "what does the KB say about X?" in its own context and returns a cited summary. Use it when retrieval is an independent subtask; direct search is sufficient for a small lookup.

Role contract (implement per harness in that harness's WIRING.md / agent config):

- **Read-only.** Never edits, never commits.
- **Procedure:** check the KB status line (SCAFFOLDED → say so and stop) → `python3 scripts/ksearch.py "<question>"` → read the top hits' TL;DRs and only the needed sections → answer with file citations (`knowledge/...md`) and the ✅/❓ state of each claim.
- **Honesty rules:** report "not in the KB" rather than guessing; flag claims whose baselines are old; never resolve code questions by reading source beyond what the KB cites — that's the caller's job with ripgrep/structural tools.
- **No facts in the role prompt** — same rule as skills; the prompt names the procedure, the KB holds the truth.
