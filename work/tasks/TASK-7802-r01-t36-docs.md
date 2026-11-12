---
id: TASK-7802
title: "R-01-T36: R-01 docs and rollout: READMEs, frozen contracts, runbook additions, skill notes, flag renewals, the Jul 13 flip plan, ledger"
spec: SPEC-000  # row (R-01-T36; SPEC-345)
acceptance_criteria: [AC-20]  # the row's acceptance, below
risk_zone: red
status: in-review
branch: lo38-r01-t36-docs
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38
created: 2026-11-12
updated: 2026-11-12
plan_key: R-01-T36
---

## Objective
Close R-01's docs and write the per-firm flip plan with a rollback for every flag.

## Delivered
- READMEs: `portal` (documents, drops, the room, settings and preview), `communications` (templates,
  render, lint, `send_templated`, follow-up policy, sender domains, the client-mail gate, deliveries).
- Frozen: `portal-pbc.md` (section v1) and `email-templates.md` (C16 v1.1).
- Runbooks: RB-20 (the client-mail gate and sender domains), RB-43 §15 (drops that do not sort);
  new `docs/runbooks/r01-portal-flip.md` (Q-04's Tue Jul 13, 2027 flip: order, checks, a rollback
  for every flag, the gate first).
- Flag renewals: the five R-01 flags in `flag-renewals-2027.md`.
- Skill notes: `build-screen-from-handoff` (the room and the sheet).
- Capacity ledger: R-01 actuals.
Acceptance: "Docs merge … and Q-04 holds a written rollback for every flag to be flipped on Jul 13":
the flip plan. The approval named in the row is the solo builder's (AMENDMENT-solo).
No code, migration, flag or route. Rollback: revert the commit.

## Progress log
- 2026-11-12: written.
