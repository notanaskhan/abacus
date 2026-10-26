---
id: TASK-1341
title: Retire the legacy evidence screens (A-01-T21)
spec: SPEC-330
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-01
plan_key: A-01-T21
branch: s10c-fe
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Every spec021, spec022 and spec023 assertion maps to a passing AUD-03 test and no legacy evidence
route remains." Retire Board, ItemDetail, AIReviewPanel (and whatever else nothing live imports),
keep tests honest, and leave the legacy paths as redirects to AUD-03.

## Plan
- `routes/firm/engagements.tsx`: drop the Board, ItemDetail and ImportRequestList screens; the
  `/requests` and `/items/$itemId` children become one `LegacyEvidenceRedirect` (AUD-03 on the
  assurance work item, `?item=`; flag off → FlagOffState; no assurance item → the record).
- Delete `legacy/{Board,ItemDetail,AIReviewPanel}.tsx`, `Board.test.tsx`, `spec021`, `spec022`,
  `spec030review`; the eslint clock exception for Board goes.
- SPEC-330 §8: the one-for-one mapping table; AUD-03 gains the item-redirect, search and
  flag-off tests.
- Kept (live importers or a planned reuse): EvidencePreview, DecisionActions, CheckResults,
  InboxPanel, ImportRequestList (until K-01).
- DEC-442. Rollback: revert the commit (no backend, migration or flag change).

## Progress log
- 2026-10-27: Built as planned. vitest over AUD-03 and the touched legacy tests; tsc, eslint,
  prettier on touched files. Firm guidance editing (ClientGuidance on ItemDetail) has no designed
  home in the new screens: recorded in DEC-442 as retired behaviour.
