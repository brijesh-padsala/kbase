# Per-agent wiring

> **TL;DR:** Tool-specific connection syntax lives in `agents/<name>/WIRING.md` — one file per agent tool — and nowhere else.

When configuring a new agent tool (claude, codex, cursor, factory, gstack, hermes, …):

1. Create `agents/<name>/WIRING.md` describing how THAT tool connects to this KB: which entry-point file it reads natively (AGENTS.md / CLAUDE.md / .cursorrules / …), how it should invoke `scripts/ksearch.py`, and any tool-specific routing.
2. Keep it wiring-only: tool syntax, not project knowledge. Anything another agent would also need belongs in a topical file under `rules/`, `practices/`, etc.
3. If the tool supports native memory/rules stores, they hold routing pointers only ("project knowledge → repo `knowledge/` + INDEX.md") per [write-back-policy.md](../rules/write-back-policy.md).
