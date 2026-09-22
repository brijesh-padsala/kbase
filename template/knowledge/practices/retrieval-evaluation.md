# Retrieval evaluation and context size

> **TL;DR:** Test ksearch on project questions with expected note paths and explicit no-answer cases. Compare raw ranking with evidence that fits the output budget. Measure bytes exactly; token estimates and starter cases do not establish real task savings.
> **Read when:** changing retrieval, auditing misses, or evaluating a new backend. **Skip when:** you only need a [search command](commands.md).

## Query judgments

The starter [cases.jsonl](../evals/cases.jsonl) checks scaffold behavior. Add 30–50 representative project questions before drawing project-level conclusions: domain terms, commands, architecture decisions, past failures, plan/handoff recovery, and questions the KB cannot answer. Split development questions from a held-out set; do not rewrite expected answers merely to make a retrieval change pass.

Each nonblank JSONL line is an object. Paths are relative to `knowledge/`, must exist in current-note scope, and must fall within `dir` when provided:

```json
{"id":"handoff","query":"resume work ownership","relevant":["practices/skills/kb-handoff.md"]}
{"id":"rules","query":"link at birth","dir":"rules","relevant":["rules/kb-maintenance.md"]}
{"id":"absent","query":"absenttermzzzx","relevant":[]}
```

`id` and `dir` are optional. `query` and `relevant` are required. Unknown fields, duplicate IDs/paths, missing or excluded gold files, empty fixtures, and unsearchable queries fail validation. `relevant: []` explicitly means search should return no results. Current lexical search may return incidental term matches; such cases should reveal its limitation rather than imply reliable semantic abstention.

## Run and interpret

```bash
python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root knowledge
python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root knowledge --max-bytes 1600 --json
python3 scripts/ksearch-eval.py knowledge/evals/cases.jsonl --root knowledge --max-bytes 0 --json
python3 scripts/kbase-doctor.py --context-only --json
```

Evaluation uses the current notes and actual JSON search output. It disables query logging and bytecode writes. A corpus SHA-256 in JSON supports comparing runs on identical note content. Keep the fixture, corpus, limit, budget, and tool revision with measurements. Avoid editing notes during a run.

| Measure | Meaning |
|---|---|
| Raw MRR | Mean reciprocal rank of the first relevant file, before the result limit or byte cap |
| Raw recall@limit / any-hit | Relevant files recovered / at least one relevant file in the first N ranks |
| Displayed MRR / recall / any-hit | The same measures for files actually serialized within the budget |
| Abstention | Fraction of no-answer cases returning no results; not confidence calibration |
| Output bytes | Exact stdout and stderr byte totals from search; includes JSON/citations and omission notices |
| Estimated tokens | Unicode characters / 4; a heuristic, not a model tokenizer or billing measurement |

Exit **0** means every positive case displayed at least one relevant file and every no-answer case abstained. Exit **1** means at least one quality miss; partial recall can still pass. Exit **2** means invalid input, a runtime failure, or an unusable byte budget. Full metrics remain necessary: a pass is neither perfect recall nor answer/patch correctness.

The evaluator measures JSON search output; human formatting has a different byte cost. Search's hard cap covers stdout, while stderr notices are counted separately in evaluation. `--max-bytes 0` disables the cap for a comparison baseline. Save verbose JSON reports locally rather than feeding the whole report back into an agent; the text summary or failing cases usually suffice.

## Startup and overall task cost

Doctor's inventory deduplicates local instruction imports, separates the required INDEX read, and reports skill name/description metadata per adapter. It does not load full skill bodies into the estimate. Treat warnings as prompts to inspect duplication and move optional detail behind links; preserve necessary project constraints.

For an end-to-end comparison, also record actual uncached input, cached input, output, model-based indexing/reranking calls, latency, and task correctness with the same model and harness. Retrieval evaluation alone measures file discovery and serialization. Before adopting a persistent index, separately test edits/deletions, archives, branch switches, and worktree/project isolation as described in the [design](../docs/agent-memory-architecture.md).
