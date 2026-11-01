---
id: TASK-2539
title: "T-01-T37 open pieces: the filed return's Deliverable ready email and Create issue for client service"
spec: SPEC-000  # T-01 §3.13, §3.14; TAX-12; DEC-1570, DEC-1571
acceptance_criteria: [AC-1, AC-2]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T37
branch: s20e-t01t37-pieces
worktree: /Users/ayushkbhatia/Accrued/abacus-s20b
created: 2026-11-01
updated: 2026-11-01
---

## Objective
AC-1 (T-01 §3.14): "when Grace publishes, then the client copy is released to the household's
scope, a `deliverable_ready` secure-link email goes out from a firm template". AC-2 (TAX-12e):
Create issue on a rejected ack works for whoever is offered it; client service is not offered it.

## Plan (red: authorisation)
- `communications.template_registry.SEND_AUTHORITIES` and `send_templated(..., authority=)`;
  `template_send._authorise_send` checks the pair (DEC-1580). No matrix change.
- `tax.filed_delivery.on_delivered` on `return.delivered` (tax `SUBSCRIPTIONS`): the owners, as
  the publisher, `authority="deliverable.publish"`, idempotent per release.
- `tax.filing.rejection_issue` authorises `issue.create` first; `tax.delivery` adds
  `issue.create` to `allowed_actions` on a Rejected return; TAX-12 calls the route.
- Tests: `backend/tests/integration/test_t01t37_open_pieces.py` (3), TAX-12 e test.
- Rollback: revert the PR; no migration.

## Progress log
- 2026-11-01: built; new tests and the T-01-T37/T-01-T41 suites pass (12), TAX-12 10 pass.
  K-1 resend under client service has the same seam (DEC-1580 open item).
