# Plans — status board

> **TL;DR:** Shared queue of plans/specs/proposals with ownership and status. Any agent can pick up any plan — check the board before starting.

## Board

| # | Plan | Status | Owner |
|---|---|---|---|
| — | *(no plans yet — add rows as `<NNN>-<slug>.md` links)* | — | — |

## Rules

1. One numbered file per plan: `plans/<NNN>-<slug>.md` (next free number, zero-padded 3). Supporting material goes in `plans/artifacts/`, never in a second `NNN-` file.
2. Every plan file has a `## Status` section: DRAFT / READY / IN-PROGRESS / BLOCKED / DONE / ABANDONED. The plan file's Status section — not a runtime flag — is the completion record.
3. The board row links exactly one plan file in its title cell; status and owner live in their own cells.
4. Plans land here ONLY — never in an agent's native plans dir ([write-back-policy.md](../rules/write-back-policy.md)).
5. DONE/ABANDONED plans move to `plans-archive/` (history; never cite as current).
6. Claim a plan by setting Owner before starting work; update Status as it moves.
