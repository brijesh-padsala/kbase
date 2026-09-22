# kb-review — review a change against its plan

> **TL;DR:** Review a defined diff against acceptance criteria, repository rules, and execution evidence. Report actionable findings with source locations, severity, impact, and verification.
> **Invoke when:** the user requests a review or the active plan requires one before completion.

1. Identify the plan and exact review boundary: base commit/branch or specified working-tree changes. Read relevant [quality gates](../../rules/quality-gates.md), KB rules, and acceptance criteria. Separate the proposed change from unrelated uncommitted work.
2. Inspect the diff and affected call paths, using [structural tools](../commands.md) when available. Check correctness, compatibility, error handling, data handling, and whether tests exercise the intended behavior. Verify each finding against source; static maps are leads.
3. Run proportionate checks that the review scope permits, or state which checks were not run and why. Distinguish pre-existing failures from regressions using evidence.
4. Return findings ordered by severity, each with `path:line`, a concrete failure condition, impact, and a suggested verification. If no actionable findings remain, say so and report residual uncertainty. Review does not itself authorize implementation fixes.
5. Record the review outcome and unresolved findings in the active plan when task scope permits that documentation change. Keep review readiness and results as narrative under an existing [board state](../../plans/README.md); mark DONE only when the plan's full completion criteria are met.
