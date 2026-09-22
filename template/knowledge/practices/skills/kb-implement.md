# kb-implement — execute an authorized plan

> **TL;DR:** Execute the active plan within its authorized scope, preserve other work, and record actual verification results before declaring completion.
> **Invoke when:** the user authorizes execution of a READY or resumable IN-PROGRESS plan.

1. Read the plan, [board](../../plans/README.md), and [quality gates](../../rules/quality-gates.md). Apply the resume checks in [kb-handoff](kb-handoff.md); confirm objective, ownership, and acceptance criteria against the current checkout.
2. Set plan and board to IN-PROGRESS with an owner. Inspect relevant source and existing implementations before editing. For parallel work, assign disjoint file ownership and preserve all other changes.
3. Implement the scoped steps, recording progress and changes that affect the plan. Resolve material scope changes through the user's instructions and [boundaries](../../rules/boundaries.md); record blockers rather than silently changing acceptance criteria.
4. Run the actual lint/typecheck/tests selected from the toolchain and plan. Use [ripwire guidance](../commands.md) when available; `--test-gate` does not execute tests. Record commands, outcomes, and remaining failures. Apply the [write-back policy](../../rules/write-back-policy.md) to durable discoveries.
5. Review the resulting diff against acceptance criteria and run `python3 scripts/knowledge-gate.py --all`. Record review readiness in the plan narrative. Keep IN-PROGRESS if required review or checks remain; set DONE only when acceptance and required review are satisfied. Report changed behavior, verification, and remaining limitations; commit or deploy only within the user's authorization.
