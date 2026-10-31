---
id: TASK-2428
title: T-02-T21 K-1 release gate and K1ReleaseWorkflow
spec: SPEC-502  # the backlog row; T-02 §3.6, §4.9, §4.11
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: T-02
plan_key: T-02-T21
branch: t02-t21-k1-release
worktree: /Users/ayushkbhatia/Accrued/abacus-s19b5
created: 2026-10-31
updated: 2026-10-31
---

## Objective
The red release gate: eligibility incl. BH-TAX-02's condition, a single-use approval grant with
`not_before` + 10 s and Undo, per-recipient idempotent activities (contact, `k1_recipient` grant,
invitation, released, "Deliverable ready" email from the database template, hand-off finals with
values copied), the human-only CHECK and replay histories.

Acceptance: "Undo within ten seconds leaves no grant, email or portal change and a replayed
half-finished release sends no second email."

## Plan (red)
- Migration 0566 (on 0522): `k1_releases` (human-only insert trigger, status machine),
  `k1_release_deliveries` (step ledger), `k1_packages` release guard, `released_at` and
  `k1_recipients.contact_id` writable, `approval_grants.action` pattern with digits, two
  human-only actions.
- `tax/k1_release.py` (service, activities, subscriptions), `tax/k1_release_workflow.py`.
- identity: `grant_k1_recipient`, `create_release_invitation`; communications:
  `template_version_in_use`; tax: `k1_package` scope resolver.
- Tests: `test_t02t21_k1_release.py` (4), `tests/workflows/test_k1_release_replay.py` (8).
- Rollback: downgrade 0566 (restores 0563's register and the grant action pattern); routes go
  back to 501.

## Progress log
- `2026-10-31` — Built on `t02-t21-k1-release` off main 20f5d5508. DEC-1476 (OQ-1 decided:
  after final approval). The integration test stands in for `send_templated` and BH-TAX-02's
  signer (the harness publishes neither); the email's sent-once guarantee is the ledger plus the
  template send's idempotency key. `tests/unit/worker` keeps two failures from main's #907
  (reporting's module and `generated_document.render_requested`), not this change.
