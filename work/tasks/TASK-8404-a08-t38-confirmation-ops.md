---
id: TASK-8404
title: "A-08-T38: Ops: WAF code path, respondent-link and JE scoring alarms, RB-91, canary plan"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
branch: a08-t38-confirmation-ops
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T38
---

## Objective
Spec section: docs/plan/epics/A-08.md §1 (flags), §7 ops. WAF rule 6 path for /v1/confirm/*/code*, alarms for OTP failure spikes, 410 bursts and JE scoring duration, the confirmation-links runbook (revoke, kill switch, reissue, suspected phishing), POR-17 in the Nov 2028 delta pen-test scope, canary flip plan with rollback.

## Plan (red)
1. `infra/modules/waf`: rule 0 (chapter 06 rule 6, auth and code rate) also counts `code_path_regex` (`^/v1/confirm/[^/]+/code(?:/verify)?$`), with a validation.
2. API log events (identifiers only): `confirm.code_failed` (every refused respondent code), `confirm.expired_view` (every uniform expired view, the family's 410-equivalent); workers: `je_scoring.completed` with `duration_ms`.
3. `infra/envs/staging/confirmation_links.tf`: three metric filters and alarms (code-failure spike, expired-view burst, JE scoring p95) naming RB-91; thresholds as variables.
4. `docs/runbooks/RB-91-confirmation-links.md` (revoke, kill switch under 5 minutes, reissue, suspected phishing, alarms, canary and rollback, pen-test scope) and the README index row.
5. Rollback: revert the WAF variable and the staging file; the log lines are inert without the filters.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5404). terraform fmt clean; ruff and pyright clean; validate_docs green. Partial: the staging drill (kill switch on, every link paused in under 5 minutes, logged) needs a staging apply and a person at the console; `terraform validate`/plan are not run here (no staging credentials in this session); the expired view answers 200 with the uniform view, not a 410, so the burst alarm counts that view. Gates and tests run once at the S48 end pass (build first, test last).
