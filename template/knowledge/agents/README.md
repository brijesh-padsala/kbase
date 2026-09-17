# Per-agent wiring

> **TL;DR:** Tool-specific connection syntax lives in `agents/<name>/WIRING.md` — one file per agent tool — and nowhere else.

When configuring a new agent tool (claude, codex, cursor, factory, gstack, hermes, …):

1. Create `agents/<name>/WIRING.md` describing how THAT tool connects to this KB: which entry-point file it reads natively (AGENTS.md / CLAUDE.md / .cursorrules / …), how it should invoke `scripts/ksearch.py`, and any tool-specific routing.
2. Keep it wiring-only: tool syntax, not project knowledge. Anything another agent would also need belongs in a topical file under `rules/`, `practices/`, etc.
3. If the tool supports native memory/rules stores, they hold routing pointers only ("project knowledge → repo `knowledge/` + INDEX.md") per [write-back-policy.md](../rules/write-back-policy.md).

## The librarian role (read-only subagent)

The one subagent role this KB design wants: a **librarian** that answers "what does the KB say about X?" in its own context and returns only a cited summary — the main thread never reads the files, which is where subagents beat inline skills on tokens.

Role contract (implement per harness in that harness's WIRING.md / agent config):

- **Read-only.** Never edits, never commits.
- **Procedure:** check the KB status line (SCAFFOLDED → say so and stop) → `python3 scripts/ksearch.py "<question>"` → read the top hits' TL;DRs and only the needed sections → answer with file citations (`knowledge/...md`) and the ✅/❓ state of each claim.
- **Honesty rules:** report "not in the KB" rather than guessing; flag claims whose baselines are old; never resolve code questions by reading source beyond what the KB cites — that's the caller's job with ripgrep/structural tools.
- **No facts in the role prompt** — same rule as skills; the prompt names the procedure, the KB holds the truth.
