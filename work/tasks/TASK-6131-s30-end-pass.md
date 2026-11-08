---
id: TASK-6131
title: "S30 end pass: gates, targeted tests, security review, fixes"
spec: SPEC-000  # end pass
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: S30
plan_key: S30-END
branch: s30-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s30
created: 2026-11-08
updated: 2026-11-08
---

## Objective
One comprehensive pass over the S30 stack (#1409 to #1442): stage-1 gates, targeted tests over every
changed and registry-sensitive suite, workflow histories, regenerate, a security review of the red
diffs, one round of fixes and one re-review.

## Plan
- Merge main (#1407) into the stack's tip.
- `make check-fast`; targeted unit, contract, workflow and infra tests; integration tests for
  the S30 migrations (0710 to 0714), the human-only drift, the schema check and tenant isolation
  of the new tables; vitest on the changed screens; portal and firm builds with budgets.
- Record histories: agent-run-backfill (completed, resumed), form5500-tieout (tied).
- Security review (DEC-2716) and gate repairs.

## Progress log
- 2026-11-08: gates and targeted tests run; two security fixes and the gate repairs in DEC-2716.
  Not run locally: WeasyPrint render tests (no glib on this machine; CI runs them), Playwright
  journeys and specs (need the stack), real parity and eval runs.
- 2026-11-08: CI round on #1443 (12 red jobs; the one fix round). S30's own: 0712's two
  `clock_timestamp()` defaults broke the sixty-second CHECK on every link (now one
  `statement_timestamp()`); the textract module's tflint versions; the backfill workflow and
  activity counts; the Form5500TieOut history alias; the related-parties fake answer cited a date
  its quote doesn't show (C2); A-06-T33's tests assumed whole-number amounts and an entity
  heading for a plan's lines; A-07 §4.8's four emailed kinds; `rep_letter` is registered now;
  s27p's fixture still set the retired flag, not the `assurance_completion` entitlement; J03/J04's
  completion steps never rendered (no `audits.cockpit`, AUD-15/16 unregistered as screen
  scenarios, no Northwind ids, AUD-20 without the cockpit handler), which hid an AUD-16
  `role="row"` with no grid (axe critical). Main's own reds fixed too: G1's decided day compared
  in UTC against the firm's business date (every letter test red from 00:00 to 05:00 UTC; now
  the firm's zone in letter_flow and record), schema_check_db's reviewed lists behind S29/S30
  (update and insert columns; three definers, reviewed: pinned search_path, tenant-scoped, own
  system actor only), statement_notes' trigger function. Not fixed: gallery axe o1-o6 part 1 (a
  page-load timeout; the other three parts passed) and main's scenario_loader flake.
- 2026-11-08: infra `checks` (trivy config) red on every PR since Oct 30 (#858): AWS-0054 on the
  staging API listener and AWS-0104 on the tasks' egress. Both by design and now said beside the
  resource with `#trivy:ignore` (the previews module's precedent): the ALB is internal and admits
  only CloudFront's origin-facing prefix list through the VPC origin (TLS ends at CloudFront; an
  HTTPS listener waits for a private certificate); the tasks reach AWS APIs and WorkOS through
  NAT. Revisit the listener when production gets its private CA.

## Decisions made during this task
DEC-2716.
