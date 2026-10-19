# kb-refine — evidence-checked KB refinement

> **TL;DR:** Refine retrieval-facing knowledge as a measured experiment, not a rewrite: propose a few targeted edits, probe each on a scratch copy of `knowledge/` with the eval fixture, and keep only what the probe supports.
> **Invoke when:** the query log or eval fixture shows misses worth fixing, or wording, routing, or structure changes deserve evidence before landing. **Skip when:** KB status is SCAFFOLDED — run [distill](distill.md) first — or the fix is a plain factual correction, which [hygiene](../../rules/hygiene.md) handles in-commit.

**Preconditions:** KB VERIFIED; `knowledge/evals/cases.jsonl` carries project-derived cases, not only the starter fixture (see [retrieval-evaluation](../retrieval-evaluation.md)).

## Steps

1. **Baseline.** Run `python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root knowledge --json`; record per-case ranks and budget omissions. Mine `knowledge/_ksearch-log.tsv` for real queries that missed — promote convincing misses into the fixture BEFORE proposing edits.
2. **Propose.** Pick at most three candidate edits, each targeting one mechanism: a TL;DR's vocabulary, a heading, an INDEX routing row, a file split, a stub description. Write each as a hypothesis — "this edit makes queries shaped X reach note Y." An edit with no hypothesis is taste, not refinement; drop it.
3. **Probe.** For each candidate: `cp -r knowledge /tmp/kb-probe-<n>`, apply only that edit inside the copy, then run `python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root /tmp/kb-probe-<n> --json`. One eval run is one probe. A candidate that regresses any previously passing case is unsafe, whatever it bought.
4. **Compose.** Apply the survivors to the real tree together; re-run the eval on `knowledge/` and `python3 scripts/knowledge-gate.py --all`. Record kept / revised / dropped per candidate with its eval delta, so the next pass can audit the reasoning — a decision without evidence attached is a decision nobody can audit.
5. **Write-back.** A durable retrieval lesson (e.g. "queries name symptoms, not modules — TL;DRs carry symptom words") goes to [the lessons log](../../learning/lessons-log.md) with `domain: knowledge/`. When a commit is authorized, stage fixture additions, kept edits, and the lesson together; commit as `knowledge: refine pass — <N> kept, <M> dropped`.

## Rules of engagement

- The eval fixture is a set of claims about the project. Grow it from real misses; never tune notes to the starter cases.
- Label each candidate **invariant** (helps any query shape — needs the stronger evidence bar, it generalizes) or **domain** (project vocabulary only); name the kind in your report.
- When several edits shipped together and the probe can't isolate which one helped, record `confounded` — a real verdict. An invented attribution poisons the log for every later pass.
- "No candidate was supported" is a real result — land nothing and say so.
- Refinement changes how knowledge is *found*, not what it *claims*. Stale facts and corrections belong to the audit loop: [kb-audit](kb-audit.md).
