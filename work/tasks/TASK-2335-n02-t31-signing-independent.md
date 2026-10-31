---
id: TASK-2335
title: N-02-T31 independent AC tests for N-02-T23 to T25
spec: SPEC-381
acceptance_criteria: [AC-10, AC-11, AC-12]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T31
branch: s18-n02-t31
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ADR-078 independent AC tests for N-02-T23, T24 and T25: only the named signer reaches a session
(INV-4), spouses never act for each other, MFA required for signing scopes, one-time expiring
sessions, return parameters never trusted, date_as_of enforced server-side in the firm's time zone,
ERSD recorded before any session, decline and withdraw rules, download audited, superseded marker
system-only, retention extension only. Acceptance: "The suite passes and fails if Jonah's principal
can fetch Claire's signing session."

## Plan
Red zone, tests only (no production code; rollback = revert).
`backend/tests/integration/backfill/test_n02t31_signing_independent.py`, reusing T23's world helpers
(its assertions are not reused): Jonah's principal gets 404 on Claire's envelope, session, return and
download; one spouse's ERSD and session never count for the other; sessions are one-time (replay
same while open, a new one abandons the old, expired or abandoned never reopen); forged return
parameters complete nothing; date_as_of follows the firm's zone (America/Chicago) not UTC; only the
system marks superseded (human, agent and support refused); retention only extends. MFA, ERSD,
decline/withdraw and audited downloads stay covered by T23's suite. DEC-1381.

## Progress log
- `2026-10-31` — written; ruff and pyright clean; runs at the end review. `[skip ci]`.

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** N-01-T24 readiness.
