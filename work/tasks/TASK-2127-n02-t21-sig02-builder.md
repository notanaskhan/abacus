---
id: TASK-2127
title: N-02-T21 SIG-02 envelope builder part 1 (a, e, f) in fixture mode
spec: SPEC-381
acceptance_criteria: [AC-7, AC-8]
risk_zone: green
status: in-review
epic: N-02
plan_key: N-02-T21
branch: s16-n02-t21
created: 2026-10-29
updated: 2026-10-29
---

## Objective
SIG-02 on the O4 full sheet: Documents (drag and Alt+↑/↓ reorder) with the Checks band, the
preview on the E5 page pipeline (zoom, page bar) with placed fields listed, Signers (order,
identity with policy-disabled options and reasons, role, sequential or parallel), Delivery,
Dating, Retention, the footer gate sentence, Save draft and Send; Escape asks to keep the draft.
States a, e and f.

Acceptance (backlog row): "Scenario tests for a, e and f pass and SMS code is never selectable on
an e-file authorization."

## Progress log
- 2026-10-29: built. Small additive C7 contract change (DEC-1174) and `make generate`. Tests:
  `apps/web/src/screens/SIG-02/SIG-02.test.tsx` (6), `backend/tests/contracts/c7_n02/
  test_n02t21_builder_fields.py` (3). ValueRow select now passes option hints (policy reasons).
  Open: field placement and trace outline (T30), document sub-lines, header Draft pill.
