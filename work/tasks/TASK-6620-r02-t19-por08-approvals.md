---
id: TASK-6620
title: "R-02-T19: POR-08 Approvals frontend"
spec: SPEC-646
acceptance_criteria: [AC-4, AC-5, AC-7, AC-12]
risk_zone: green
status: in-review
branch: s34-r02-t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T19
---

## Objective
POR-08 e, e2 and f run on live data and a to d in fixture mode with every amount from the API,
and no threshold, materiality or agent word appears.

## Built
- `apps/web/src/screens/POR-08/` (index, copy, scenarios, test): T7 split and T7-M.
  - Rail: period card (context label, client = the person's scope label, state pill), filters
    with the server's counts (Waiting for you, Entries posted for <month> only when posted > 0,
    Approved, Declined), Coming next (contexts with no state).
  - Main: header (period Picker, Download entries through the journal render), Card A package
    (parts, highlights and legend verbatim, Approve statements with the O1 confirm, Decline… O3
    sheet with the three reason codes and a note, Ask a question), attest entry cards (lines on
    expand, Accept, Decline… with the free-text reason, Ask), the acknowledgement card (22,250 and
    its two figures from the item's detail; only `seen_hash` is sent), Card B posted entries
    (read-only, whole dollars, lines and support chips on expand, Ask about this entry).
  - Every decision sends the detail's `seen_hash` and an `Idempotency-Key`; 409 toasts and refetches.
  - Flag off (404 on the list): the designed state. Empty: "Nothing to approve." with the firm's name.
  - 390: the package reads "Review required" with a full-width Review opening a FullSheet.
- `fixtures/seed/portal-por08.ts` + foot test (35,300; 14,900; 48,600; 22,250);
  `fixtures/scenarios/POR-08.ts` (a, a2, b, c, d, e, e2, f, flag off) replaces R-02-T13's unused
  two-state placeholder.
- Portal route `/approvals` reads `?context=`, `?filter=`, `?ov=`; Approvals moved from the planned
  nav map to production's (the shell still shows it only on an entity scope).

## Progress log
- 2026-11-10: built; tests run at the S34 end pass.
- Partial (API carries no field for it; nothing invented, no client arithmetic):
  - Card A's "Released by Priya Raman, Brightwater Hale · Sep 14, 4:25 PM": the item has no
    released-by or released-at; the sub-line reads the firm's name and "waiting for your approval".
  - Card B's footer ("Approved by Raj Malhotra and Priya Raman … posted to QuickBooks Online …"),
    its "Posted · QBO 48213–48218" pill and the "August entries · 6 / $35,300.00" total strip: no
    total, decider or QBO range on the list. Omitted until the API carries them (R-02-T24 parity).
  - Coming next's "Requests open Oct 1" sub-line: not on `ApprovalContextOut`.
  - The acknowledgement sentence's two figures come from the item's detail lines (debit = would
    increase, credit = would decrease). The live `uncorrected_misstatements` provider answers no
    lines yet, so live e2 shows the short sentence with the net effect only. Follow-up: the
    provider lists the two declined entries as lines (backend, R-02-T15's file).
  - Download entries requests the render then the file once; a render still running answers an
    error and the toast. No polling.
- Data note: `fixtures/seed/portal-r02.ts` (R-02-T13) titles RJE-1 "Accrued expenses" 13,050 and the
  PAJEs as receivables, unlike the handoff's e frame (RJE-1 14,850 loan offsets, PAJE-1 35,300,
  PAJE-2 13,050). POR-08 reads its own seed transcribed from the handoff; the R-02-T13 seed is left
  for its foot test.
