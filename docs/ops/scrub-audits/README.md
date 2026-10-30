# Scrubbing audits (Q-03-T083; SPEC-341 AC-49; RB-42)

One row per run of `abacus_tools.scrub_audit`, newest first. The report beside each row is the JSON
the `sample` step printed: sinks, delivery and findings with masks only, never a value.

A run counts toward the M9 gate only when it is **clean** on staging and on the production canary.
An inconclusive run is recorded with its reason and repeated; it is never counted.

| Date | Environment | Run | Verdict | Report | Tests added | Notes |
|---|---|---|---|---|---|---|
| — | staging | — | not run yet | — | — | Needs the `ABACUS_SENTRY_AUDIT_TOKEN` ops secret and the metric namespace (RB-42 §1) |
| — | production canary | — | not run yet | — | — | Needs the production compute stack (the ops task and its role are not in `infra/envs/production` yet) |
