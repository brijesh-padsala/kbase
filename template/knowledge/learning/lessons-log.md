# Lessons Log

> **TL;DR:** Append-only, dated lessons — each entry `✅/⚠/❓`-labeled with domain, retrieval cue, and evidence. The project's canonical lessons home.

Format for entries (append at the end, newest last; never rewrite history — corrections become new entries):

```markdown
- ✅ — **Title of the lesson (YYYY-MM-DD).**
  **Domain:** the area of work it governs (`ci`, `migrations`, `knowledge/` itself).
  **Cue:** the shape of situation where this lesson should fire — the pattern,
  not this task's facts; it must still trigger on a different task.
  **Lesson:** the rule going forward.
  **Evidence:** the file, command output, or commit the lesson rests on.
```

Rules:

1. Append-only. A wrong lesson is corrected by a new entry that names it, not by editing it.
2. One lesson per bullet; if an entry needs its own page, it belongs in `pitfalls.md` or `docs/` with a pointer here.
3. Evidence or ❓ — no unlabeled claims. The gate rejects staged ✅/⚠ entries that name no evidence; a lesson the record does not support is worse than no entry — leave it out.
4. Write the **cue** as a retrieval key: the situation pattern a future session will be inside ("a config file was renamed"), never task facts that fire once ("the fee rose on Jan 1"). The **domain** groups the log by area of work so related lessons sit together in search.
5. Distill recurring lessons into [pitfalls.md](pitfalls.md); the log keeps the history, the pitfalls file keeps the current truth.
