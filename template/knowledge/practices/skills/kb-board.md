# kb-board — maintain the shared work queue

> **TL;DR:** Inspect plans, reconcile their board rows, and make requested ownership or state changes using the six canonical states. Preserve an explicit next action for unfinished work.
> **Invoke when:** listing priorities, finding active work, assigning ownership, or updating plan state.

1. Read the [board](../../plans/README.md) and relevant linked plans. For a status-only request, report status, owner, blocker, and next action without changing files.
2. For an authorized update, reconcile each affected row with its plan's Status and owner. Use only DRAFT, READY, IN-PROGRESS, BLOCKED, DONE, or ABANDONED. Check ownership before reassignment; record the reason for a state change in the plan.
3. Keep review readiness in the plan narrative. DONE requires evidence that acceptance criteria and required checks/review are satisfied. BLOCKED records the dependency and action needed to proceed; ABANDONED records why work stopped.
4. Follow the board's archive rules for completed or abandoned plans, update their links, and leave unfinished plans with a concrete next action. Run `python3 scripts/knowledge-gate.py --all` after edits.
5. Return the affected plan paths, state/owner changes, and outstanding blockers. Creating a queue entry does not authorize implementation.
