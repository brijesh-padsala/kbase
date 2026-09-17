# Skills — index & authoring rules

> **TL;DR:** Skills are procedures, never facts. Canonical content lives here; per-harness stubs (`.agents/skills/<name>/SKILL.md`) are 6-line pointers. Ship: `distill` (bootstrap pass) and `kb-audit` (consolidation loop).

## Available skills

| Skill | Invoke when | Procedure |
|---|---|---|
| `distill` | KB status is SCAFFOLDED / `knowledge/_bootstrap-brief.md` exists | [distill.md](distill.md) |
| `kb-audit` | the hygiene audit cadence fires (see [rules/hygiene.md](../../rules/hygiene.md)), or on demand | [kb-audit.md](kb-audit.md) |

## Authoring rules

1. **Procedures here, facts nowhere in prompts.** A skill file tells an agent HOW to do something repeatable; everything project-specific it needs is read from `knowledge/` at runtime. A skill prompt containing project facts is agent-native memory in disguise — forbidden by the [write-back policy](../../rules/write-back-policy.md).
2. **Thin stubs only.** Each harness gets a discovery stub (e.g. `.agents/skills/<name>/SKILL.md`) that points here and nothing else: *"Canonical content: `knowledge/practices/skills/<name>.md` — read that file; this stub exists only for tool-native discovery."* Stubs rot silently; 6-line pointers can't.
3. **Deterministic completion.** A skill's steps end in a state a machine can check (a commit, a gate pass, a status flip). If completion is vibes, it's not a skill.
4. New skill: canonical file here (TL;DR-first, like every knowledge file) + stub + a row above, in the same commit.
