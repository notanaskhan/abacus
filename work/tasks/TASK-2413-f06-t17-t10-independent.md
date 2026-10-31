---
id: TASK-2413
title: F-06-T17 Independent AC tests for T10 (ADR-078)
spec: SPEC-400  # AC-19, AC-21; F-06.md §5.2
acceptance_criteria: [AC-19, AC-21]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T17
branch: s19-f06-t17
worktree: /Users/ayushkbhatia/Accrued/abacus-s19
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Independent AC tests for T10 (ADR-078): no markup path, locator-only citations, HumanAction
approve opening SHL-12, Locked read-only, regenerate keeps human-edit flags, attribution words,
and no model text in client- or agency-facing variants while ADR P-25 is off.

Acceptance: "Tests prove no dangerouslySetInnerHTML or model markup, Approve never renders for an
agent actor, Approved by Accrued Agent never appears, Locked blocks every edit, and agent prose or
the Drafting state never renders in variant letter or email unless modelTextToClients is passed
(INV test for ADR-111 and DEC-79)."

## Plan (amber)
`packages/ui/src/templates/document-on-well/f06t17-independent.test.tsx`, written from the row
and F-06 §5.2, not from the code. Writing it found that `DocumentOnWell` printed a non-person
approver; fixed in the kit (DEC-1461). Rollback: revert.

## Progress log
- `2026-10-30` — Built on `s19-f06-t17` off main; the suite runs at the end review.
