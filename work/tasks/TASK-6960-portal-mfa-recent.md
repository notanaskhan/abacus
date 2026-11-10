---
id: TASK-6960
title: "A portal session's second step counts for mfa_recent actions"
spec: SPEC-333  # POR-16 connections (AC-36: start needs a fresh second factor)
acceptance_criteria: [AC-36]
risk_zone: red  # identity
status: in-review
branch: a02-portal-mfa-recent
worktree: /Users/ayushkbhatia/Accrued/abacus-portal-mfa
created: 2026-11-10
updated: 2026-11-10
---

## Objective
A portal session that passed its own second step within `MFA_RECENT` can do `mfa_recent`
actions (POR-16 connect start and complete, disconnect, portal approvals), without weakening staff
MFA. Found by A-02-T33 (#1601, TASK-6902): `portal_member_context` built every portal context with
`mfa_at=None`, so the matrix refused all of them.

## Plan (red: identity)
- `identity/service.py`: `portal_member_context(..., mfa_at=)` keyword, default None.
- `identity/portal_session.py`: `portal_context` passes the session row's `mfa_at` (the TOTP's
  time; a trusted-device session has None).
- `identity/context.py`: comment on the field.
- No migration, no matrix or registry change, no flag. `authorise` unchanged.
- Tests first: `tests/integration/backfill/test_t6960_portal_mfa_recent.py` (start, complete,
  disconnect within the window; 14 minutes allowed; 16 minutes refused at each; trusted device
  reads and is refused), `tests/unit/identity/test_t6960_portal_mfa_at.py`.
- Rollback: revert the commit; portal sessions are refused `mfa_recent` actions again.
- Decision: DEC-3960.

## Progress log
- 2026-11-10: tests written and red (403 `authz.denied` layer attribute on `connection.create`);
  fix in; new tests and the related identity, connections, portal, filed-delivery, K-1 and
  approvals suites run. Self security review of the red diff: staff path (`choose_tenant`,
  `authorise`'s staff branch) untouched; a portal `mfa_at` only ever comes from the session row
  written by `portal_mfa` on a verified TOTP; trusted devices stay out of `mfa_recent`.
- Follow-ups: portal step-up; flip #1601's portal-path test (403 -> 201, start on the portal
  session) once #1601 is on main.
