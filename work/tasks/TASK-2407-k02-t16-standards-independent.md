---
id: TASK-2407
title: K-02-T16 independent AC tests for the firm-standards service, standards API and import/export
spec: SPEC-500
acceptance_criteria: [AC-30, AC-31, AC-32, AC-33, AC-39, AC-40, AC-42, AC-44, AC-47]
risk_zone: amber
status: in-review
epic: K-02
plan_key: K-02-T16
branch: s19-k02-t16
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
test_author: ayushkbhatia
test_session: 2026-10-30 s19-k02-t16
---

## Objective
ADR-078 independent AC tests for K-02-T08, T10 and T11, written from K-02 §3 to §4, SPEC-500 and the
C21 part B contract only.

Acceptance: "The suite fails if the agent can draft or publish, a staff member can see a draft, or
any golden figure drifts."

## Plan (amber)
File: `backend/tests/integration/test_k02t16_firm_standards_independent.py` (HTTP on the migrated
Postgres for the lifecycle; `methodology.api` plus the contract's payload models for the standards
API). No production code. Fan-out (K-02-T12) is covered by K-02-T15's suite already on main.
Golden figures: the spec's numeric boundaries (limit 15,000, 10 % and 2,500 strictly over, the
Dec 15, 2026 SSARS 27 boundary, the 90/98 confidence floor) are asserted as literals.

Per AC: test_ac30 (agent), test_ac31 (owner), test_ac32 (fresh MFA), test_ac33 (staff drafts),
test_ac39 ×2 (attest held, limit), test_ac40 (strictly over both), test_ac42 (no auto-accept),
test_ac44 (SSARS boundary), test_ac47 (import never publishes, draft_exists). Results: run at the
S19 end review.

## Progress log
- `2026-10-30` — Written on `s19-k02-t16` (build-only; run at the end review).
