# Operations — environments & durable facts

> **TL;DR:** Operational facts: environments, endpoints, runbooks, incident records. Every runtime claim labeled ✅ (checked, with date) or ❓.

<!-- TODO(distillation): fill with what's verifiable from this checkout and configs:
     - environments (local/beta/prod) and how to tell them apart
     - external services and where their config lives (never inline secrets)
     - deployment/runbook steps that must never be skipped
     - incident records: dated, with mechanism + remediation; recurring incidents
       also get a pitfalls.md entry -->

Rules:

1. Never inline credentials — name the secret's location, not its value.
2. Runtime claims carry a check date; environments drift, so ✅ older than the last deploy is a lead, not a fact.
3. Incidents are dated records: mechanism, symptom signature, remediation, open follow-ups.
