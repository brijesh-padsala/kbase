# kb-audit — knowledge base consolidation pass

> **TL;DR:** Review the ksearch query log for misses, spot-check aging ✅ claims, verify file references, and split overgrown files. Finish with a validated change and an evidence summary.
> **Invoke when:** the audit cadence in [rules/hygiene.md](../../rules/hygiene.md) fires, or on demand (after big refactors, before milestones). **Skip when:** KB status is SCAFFOLDED — run `distill` first.

## Steps

1. **Zero/weak-hit audit.** Read `knowledge/_ksearch-log.tsv` (timestamp, query, top hit, hit count). For every query with 0 hits, or whose top hit looks wrong for the intent, add the missing vocabulary or aliases to the relevant file's TL;DR. This is the system's substitute for embeddings — measure, then patch words.
2. **Label spot-check.** Pick ~5 ✅ claims whose evidence is oldest (baseline commits near the project start). Re-verify each against the current checkout; downgrade to ⚠/❓ with a note, or re-verify with the new baseline.
3. **Reference audit.** Extract file references from `docs/` and `memory/` — backticked paths and `path:line` mentions (`rg -o '[\w./-]+\.(py|ts|tsx|js|rs|go|java|rb|php|cs|sql|ya?ml|toml|json)(:\d+)?' knowledge/docs knowledge/memory`). Verify each path exists (`rg --files`). Broken references: fix the path, or mark the claim ⚠ STALE and consider archiving the file.
4. **Size/structure audit.** Files over ~400 lines are split candidates. Anything nobody queried since the last audit is an archive candidate — move to `archive/` with a dated note if superseded.
5. **Validate and report.** Run `python3 scripts/knowledge-gate.py --all` and `python3 scripts/kbase-doctor.py`. Protected files (`lessons-log.md`, `operations.md`) shrinking >50% need a staged `archive/` note — the staged gate enforces this. When a commit is authorized, stage the audit changes, run the staged gate, and commit as `knowledge: audit pass (<date>) — <N> fixes`.

## Rules of engagement

- Audit fixes are small and mechanical: vocabulary, labels, paths, splits. New analysis belongs in a plan, not smuggled into an audit commit.
- Report how many queries were audited, how many claims were checked, what was broken, and any remaining warnings; include this evidence in a commit body when committing.
