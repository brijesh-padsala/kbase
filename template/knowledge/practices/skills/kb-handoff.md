# kb-handoff — save or resume an active task

> **TL;DR:** Keep one resumable task record in the active plan: objective, progress, files, test evidence, open questions, and the next action. Resume by checking the current checkout and ownership before editing.
> **Invoke when:** saving progress, transferring a task, or resuming after a context reset.

## Save

1. Read the [plans board](../../plans/README.md) and locate the task's plan. If none exists, create the next numbered plan from the [template](../../plans/artifacts/plan-template.md), with a TL;DR and board link.
2. Inspect `git status --short`, the current branch/HEAD, and the relevant diff. Record the objective and acceptance criteria; completed and remaining work; exact changed files and their owners; test commands, outcomes, and the checkout they exercised; open questions or blockers; and one concrete next action. Identify uncommitted work explicitly.
3. Update the plan's handoff section and keep board status/owner consistent. Preserve the current owner's unrelated work; record any ownership transfer explicitly. A pause alone does not mean BLOCKED or DONE.
4. Run `python3 scripts/knowledge-gate.py --all` and report the plan path, next action, and any unresolved validation failures. The handoff is complete when another session can resume from that record without reconstructing the conversation.

## Resume

1. Read the board row, plan status, and latest handoff. Recheck branch/HEAD, `git status --short`, and relevant diffs against the recorded baseline; older test results are historical evidence.
2. Confirm file ownership and task scope still match the current work. Resolve conflicting ownership or unexplained changes before editing those files; preserve other sessions' changes.
3. Revalidate assumptions affected by intervening changes, then continue from the recorded next action within the user's authorization. Update the plan with the new baseline and ownership before implementation.
