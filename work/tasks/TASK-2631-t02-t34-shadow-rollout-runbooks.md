---
id: TASK-2631
title: T-02-T34 shadow and rollout runbook; K-1 bounce, resend and mis-release runbook
spec: SPEC-502
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: T-02
plan_key: T-02-T34
branch: s21-t02-t34
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-11-01
updated: 2026-11-01
---

## Objective
"Both founders approve both flip plans and each runbook is rehearsed once on staging."

## Plan
Docs only: `docs/runbooks/RB-44-t02-shadow-and-rollout.md` (pilot onboarding through import
endpoints, the shadow reconciliation checklist against CCH for Jul 27 – Aug 13, the Aug 17 and
Aug 31 flips with written rollback, the Aug 24 renewal bundle to Nov 22) and
`docs/runbooks/RB-45-k1-bounce-resend-and-mis-release.md`; both indexed. Rollback: revert.

## Open
- A route to revoke one package's `k1_recipient` grant is not built; RB-45 contains through the
  flag and the client-level revoke until it is (T-02 open item).
**Human**: both founders approve the two flip plans; each runbook rehearsed once on staging on the
synthetic test firm.

## Progress log
- 2026-11-01: written.
