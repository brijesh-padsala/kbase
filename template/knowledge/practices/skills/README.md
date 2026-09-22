# Skills — index & authoring rules

> **TL;DR:** Skills are shared procedures; agent adapters contain only discovery pointers. Core discovery includes distill, kb-audit, and kb-handoff. The optional workflow pack adds planning, implementation, review, and board management.

## Available skills

| Skill | Discovery | Invoke when | Procedure |
|---|---|---|---|
| `distill` | Core | KB status is SCAFFOLDED / bootstrap brief exists | [distill.md](distill.md) |
| `kb-audit` | Core | [hygiene audit cadence](../../rules/hygiene.md) fires, or an audit is requested | [kb-audit.md](kb-audit.md) |
| `kb-handoff` | Core | saving progress, handing off, or resuming an active task | [kb-handoff.md](kb-handoff.md) |
| `kb-plan` | Optional workflow | a task needs an executable plan | [kb-plan.md](kb-plan.md) |
| `kb-implement` | Optional workflow | an authorized plan is ready to execute | [kb-implement.md](kb-implement.md) |
| `kb-review` | Optional workflow | evaluating a change against its plan and repo rules | [kb-review.md](kb-review.md) |
| `kb-board` | Optional workflow | inspecting the queue, assigning ownership, or updating plan state | [kb-board.md](kb-board.md) |

All procedures ship in `knowledge/`; `--workflow` at init enables the four optional discovery stubs. See [agent wiring](../../agents/README.md) for Codex and Claude paths. Calling a skill follows the user's existing scope and authorization; implementation, commits, publication, and deployment remain separate actions.

## Authoring rules

1. **Procedures here, facts nowhere in prompts.** A skill file tells an agent HOW to do something repeatable; everything project-specific it needs is read from `knowledge/` at runtime. A skill prompt containing project facts is agent-native memory in disguise — forbidden by the [write-back policy](../../rules/write-back-policy.md).
2. **Thin stubs only.** Each harness gets a discovery stub with a short trigger description and a link here. Keep steps in the canonical procedure; update its stub only when the trigger or path changes.
3. **Checkable completion.** State the expected artifact, validation evidence, and unresolved issues. A commit is required only when the task authorizes one.
4. New skill: canonical file here (TL;DR-first, like every knowledge file) + stub + a row above, in the same commit.
