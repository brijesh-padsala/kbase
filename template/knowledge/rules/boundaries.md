# Boundaries — Always / Ask-first / Never

> **TL;DR:** Hard action tiers. "Always" is the floor; "Ask first" requires owner sign-off before acting; "Never" is flat-out forbidden.

## Always

- Search before acting (`ksearch` for knowledge, `ripwire`/`rg` for code) — see [agent-contract.md](agent-contract.md).
- Lint + related tests before done.
- Commit knowledge updates with the code that taught them.
- Stale code/docs found during work get removed in the same commit.
- Surfaced preexisting failures get analyzed (fix, delete-stale-test, or plan) — never ignored.

## Ask first

- Non-additive schema migrations.
- New heavy dependencies.
- Deploys to shared/production environments.
- Changes to protected paths — **TODO(project): list the files/dirs where caution outranks speed here)**.

## Never

- Commit secrets or `.env*` files.
- Bypass hooks for code.
- Store project knowledge in agent-native memory.
- Hand-edit script-generated files (their generator is named beside them).
- **TODO(project): add the project-specific Never tier at distillation.**
