---
id: TASK-2029
title: Q-03-T083 Pre-shadow scrubbing audit (ADR-031)
spec: SPEC-341
acceptance_criteria: [AC-49]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T083
branch: s15c-q03-t083
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Sampled CloudWatch logs, Sentry events and metric attributes from staging and the production canary
checked for Restricted, TRI or TIN values with the classification scrubber's seeded cases; each miss
becomes a test in `test_classification_scrubbing.py`.

## Plan (red: written before the code)
- **Tool** `backend/src/abacus_tools/scrub_audit.py`: `seed` (inside the audited environment's ops
  task: the offline suite's seeded SSN, EIN and ITIN plus a tagged model's bank account, date of
  birth and IP PIN, through the kernel logger, `error_tracking.report` and the scrubbing meter, each
  line carrying a run marker), `sample` (CloudWatch Logs under `/abacus/<env>/`, Sentry project
  events, CloudWatch metric dimensions; bounded per sink) and `check` (offline, saved samples).
  Verdict: clean only when every sink received the marker and nothing was found; inconclusive
  otherwise (DEC-1065). Reports hold locations and masks, never values.
- **Wiring**: the ops allowlist (`release.OPS_COMMANDS`) and `ops-task.yml` options; the staging ops
  role reads `/abacus/staging/*` log groups and lists metrics; the Sentry read token is an ops
  secret (`ABACUS_SENTRY_AUDIT_TOKEN`), created by hand.
- **Docs**: RB-42 (seed, read back, verdict, leak handling: a test per miss, fix, purge, re-run),
  `docs/ops/scrub-audits/README.md` (the run log), SPEC-341 AC-49.
- **Tests** (TDD, run at the end review): `backend/tests/unit/tools/test_scrub_audit.py`.
- **Rollback**: delete the tool and the two allowlist entries; the IAM statements are read only.

## Not done here (needs the environments)
- The staging run: needs the Sentry read token secret and the OTLP collector's metric namespace.
- The production-canary run: `infra/envs/production` has no compute stack or ops task yet; the same
  IAM statements go into it when it lands.
- Any miss found becomes a test then; none can be found before a run.

## Progress log
- 2026-10-30: tool, tests, wiring, RB-42 and the run log built (S15 group C, build first; tests run
  at the end review).
