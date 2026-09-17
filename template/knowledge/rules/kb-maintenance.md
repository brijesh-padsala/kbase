# KB maintenance — file format, labels, baselines

> **TL;DR:** The conventions that make `ksearch` work and keep claims trustworthy: TL;DR-first format, ✅/❓ labels, verification baselines, link-at-birth.

## File format (load-bearing for retrieval)

Every knowledge file opens with:

```markdown
# Title
> **TL;DR:** one-to-three sentences a `ksearch` query can rank.
> **Read when:** the situations this file serves. **Skip when:** where to go instead.
```

`ksearch` field-weights TL;DR/description above headings above body — a file without a TL;DR is both harder to retrieve and more expensive to read. Keep the TL;DR vocabulary aligned with the words people actually query (audited via `_ksearch-log.tsv`, see [hygiene.md](hygiene.md)).

## Labels and baselines

- Factual claims carry ✅ VERIFIED (with evidence: `file:line`, command output, or commit) or ❓ UNVERIFIED. Dated records may carry ⚠ STALE.
- Verification baselines name the commit they were checked against (`VERIFIED @ <short-sha> (<date>)`). When a source changes, its claims require rechecking — the baseline is what makes that detectable.
- Prefer deleting an unverifiable claim over guessing a label.

## Birth and structure

- New files: TL;DR + a link from their topical home (or the plans board) in the same commit — `scripts/knowledge-gate.py` enforces both.
- One topic per file; a file over ~400 lines is a split candidate.
- Numbered plans: one file per plan number, `## Status` section with DRAFT/READY/IN-PROGRESS/BLOCKED/DONE/ABANDONED; supporting material in `plans/artifacts/`.
- Protected files (`learning/lessons-log.md`, `memory/operations.md`) may not shrink >50% in a commit without a staged `archive/` note — the anti-truncation guard.

## Status line

The KB carries one status line (README + INDEX, must agree): `SCAFFOLDED @ <commit>` or `VERIFIED @ <commit>`. Flipping to VERIFIED requires the distillation pass done and names the flip commit; the gate verifies the named commit exists.
