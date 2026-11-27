---
id: TASK-9027
title: "C-02-T56: Posting restored on CLS-04 and CLS-05 for non-attest W1 clients"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-c02-t56-posting-restored
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: C-02-T56
---

## Objective
Backlog row acceptance: "For Copperleaf Post AJE in CLS-04 b posts AJE-02 as a batch of one and lands on c 'Posted · QBO 48214', CLS-05 d reads 'AJE-06 posted (QBO 48218)', an attest client still sees the read-only variants with no Post control, and AJE-06 resolves to /closes/$closeId/adjustments/AJE-06."

## Done
- Backend (additive): CLS-04's workpaper read carries pending_entry_id / status / version, posting_open (approved, not attest) and the posted entry's number, QuickBooks id and time; adjustments' Entry carries external_txn_ref and the batch's posted_at; integration test extended
- CLS-04: with adjustments.posting and a non-attest client, Post AJE (secondary to CLS-07 before approval; primary Post AJE… after) opens the confirm Post AJE-02 to QuickBooks Online?, whose HumanAction Post posts a batch of one (entry and seen version) through CLS-07's posting path; c reads Posted · QBO 48214 · 10:20 AM with Post AJE disabled as Posted; read-only note otherwise (DV-1); fixtures bpost, b2, c
- CLS-05: d reads AJE-06 posted (QBO 48218) for a non-attest W1 client, linking to /closes/$closeId/adjustments/AJE-06; attest keeps the recorded wording; Review required opens CLS-07; CLS-06's Issues picker Adjustments entry opens CLS-07; new route /closes/$closeId/adjustments/$entryRef selects the entry in CLS-07
- Tests: CLS-04 (19, incl. b W1, b2 posts a batch of one, c), CLS-05 (17, incl. d posted and attest), C-01-T21 and CV-2 integration (20)

## Progress log
- `2026-11-27` — Built; tests pass.
