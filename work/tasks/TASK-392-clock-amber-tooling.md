---
id: TASK-392
title: Adopt kernel.clock in amber modules and tooling (F-04-T16)
spec: SPEC-002
acceptance_criteria: [F-04.4]
risk_zone: amber
status: done
epic: F-04
plan_key: F-04-T16
branch: f04-t16-clock-amber
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"`engagements`, `communications` and `abacus_tools` call sites use `now` or `system_now`
correctly."

## Plan
Same classification as F-04-T11 (TASK-391). No migration, flag or registry edit. Rollback:
revert the commit.

## What changed
- `engagements/setup.py`: the time independence is concluded is business time, `now(ctx.tenant)`. It used to be the server's local time.
- `communications/transport.py`: the file sink's sent time is `system_now()`, a transport record.
- `abacus_tools` uses `system_now()` in:
  - `signup_codes`: code expiry;
  - `access_review`: generated-at;
  - `agent_stage`;
  - the eval runner and the eval suites (`upload_review`, `entry_assessment`, `guidance_drafting`, `matching`): started and finished times;
  - `ci/coverage_floor`;
  - `codegen/feature_flags`: flag expiry;
  - the OIDC and identity fakes: token and code expiry.
- The only direct clock call left in `src/` is `kernel/config.py` (see TASK-391), outside `kernel/clock.py`.

## Progress log
- 2026-10-22: built per the S3 batch rules (static checks only). ruff and pyright are clean, and `make check-generated` passes.
