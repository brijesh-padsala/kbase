# Agent contract

> **TL;DR:** Start at INDEX.md, search before acting, respect the KB status line, route questions to the cheapest tool, write back per policy.

Every agent session on this repo agrees to:

1. **Start at [INDEX.md](../INDEX.md)** and check the **KB status line**. SCAFFOLDED → complete `knowledge/_bootstrap-brief.md` before citing knowledge/ as truth. VERIFIED → cite freely, recheck runtime claims against the target environment.
2. **Search before acting.** Knowledge questions → `python3 scripts/ksearch.py "<query>"`. Code questions (who-calls-what, blast radius, where to start) → `ripwire --for/--callers/--impact` (or targeted `rg` + read) BEFORE a broad grep-and-read. String literals/configs → `rg`.
3. **Read the TL;DR first.** Every knowledge file opens with one; read it and only descend into sections you need.
4. **Revalidate dated knowledge** against the current checkout; revalidate runtime claims against the target environment. A ✅ from an old baseline is a lead, not a fact.
5. **Write back per [write-back-policy.md](write-back-policy.md)** — default don't write; knowledge commits with the code that taught it.
6. **Never** store project knowledge in agent-native memory; never bypass hooks for code; never commit secrets.
