# kb-plan — prepare an executable plan

> **TL;DR:** Translate an agreed objective into a numbered plan with scoped files, evidence, acceptance criteria, and verification commands. Planning completes with a reviewable artifact and explicit unresolved decisions.
> **Invoke when:** the user requests a plan or the repository's planning rules require one.

1. Read the [board](../../plans/README.md), [boundaries](../../rules/boundaries.md), and relevant KB search results. State the objective, exclusions, and acceptance criteria; identify existing work that already covers it.
2. Inspect the relevant source and actual toolchain. Use the structural and reuse checks in [commands](../commands.md) when available. Record supporting paths and uncertainties; distinguish observed behavior from proposed behavior.
3. Create or update one numbered plan using the [template](../../plans/artifacts/plan-template.md). Assign file ownership, list implementation steps, risks/rollback, and exact lint/typecheck/test commands. Give every step a checkable result.
4. Add or update the board row. Keep DRAFT while required decisions are unresolved; use READY once scope and verification are sufficient and any required approval is recorded. READY describes the plan's state, not independent permission to execute it.
5. Run `python3 scripts/knowledge-gate.py --all`. Return the plan path, material decisions, and remaining questions. Implementation follows the user's existing authorization and the repo's boundaries.
