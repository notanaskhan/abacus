---
id: RB-93
title: "September close shadow and close support (C-01)"
owner: builder
alarms: [close-sync-freshness, close-sync-failure-rate, intuit-meter-budget]
last_rehearsed: never
rehearse_by: 2028-10-03
---
# RB-93 · September close shadow and close support

| Field | Value |
|---|---|
| Owner | builder |
| Severity range | SEV3 (a shadow figure differs and is explained) to SEV1 (a close figure or a client question reached a client wrong, or anything was written to QuickBooks) |
| Source | C-01-T55 (TASK-8757); C-01 §10 items 1 and 6; SPEC-655; DEC-17, DEC-70; RB-04 (connector outage) and its hourly-sync addendum (C-01-T56) |

## What turns on
Three C-01 flags per firm, in order (`docs/architecture/feature-flags/closes.yaml`):
1. `closes.engine`: the close screens (CLS-01 to CLS-06, CLS-09, CLS-10) and the hourly QuickBooks Online read;
2. `closes.portal_requests`: POR-11 requests and transaction questions for the firm's clients;
3. `closes.agent`: the `close.agent` modes, each only once cleared (`evals/close_agent`); off, the run completes on code alone and texts fall back to templates (DV-3).

The connector only reads (ADR-040). No C-01 path writes to a client's books: AJEs are recorded in QuickBooks by a person (DV-1, DV-2).

## Gate (all must hold; record each in the flip log)
- [ ] **Shadow on the September close** with no open SEV1 or SEV2. Until a real pilot firm exists the shadow runs on PF-X1 (Brightwater Hale, Copperleaf) and is reported as synthetic (DEC-1530, DEC-1391).
- [ ] **Reconciliation goldens** green in `make check` (`backend/tests/golden/closes/`), exact `Decimal` equality.
- [ ] **Sync freshness** within the 60 ± 15 min SLO for 5 business days; the meter budget not exhausted.
- [ ] **Pen-test delta**: deferred (DEC-1389). Recorded as deferred, never as met.
- [ ] **Written rollback** below, rehearsed once on staging.
- [ ] **Both founders' approvals** for the window (Tue 19:00 CT), recorded by name. Never assumed.

## Shadow (each business day of the September close)
1. Open CLS-01 for the firm: the tiles and the past-due count match the firm's own tracker.
2. For each shadow close, compare against the firm's spreadsheet:
   - every bank reconciliation's difference (CLS-05) equals the firm's;
   - every schedule's tie (CLS-04) agrees, and a "Does not tie" row has a review issue;
   - flux lines (CLS-10) over threshold match the firm's list.
3. Any difference: open an issue on the close (CLS-06), explain it in a resolution note, and log it here with the close and account. Unexplained differences block the flip.
4. Client side (POR-11): questions read in client wording only; no firm-only field or workflow word reaches the portal (INV-4; `e2e/screens/POR-11.spec.ts`).

## Close support (during the shadow and after the flip)
- **"The schedule doesn't tie after I recorded the entry."** The next hourly sync ties it. Check sync freshness on the close's record bar; if it is past 75 minutes, follow RB-04's hourly-sync addendum. Sync now is a person's action and counts against the meter budget.
- **"The run stopped at Shopify" (CLS-02 e).** Retry once; if it fails again, open the run's trace (View run) and raise an issue on the close with the trace link. Never edit run output by hand.
- **"The agent summary says Totals from the file."** Expected while `closes.agent` is off or the `intake` mode is not cleared (DV-3).
- **"The client can't see a request."** Requests publish on BD1 from the close plan (CLS-03 f). Check the plan version and the publish schedule before republishing.
- **Meter budget exhausted.** Follow "Intuit meter budget exhausted" (C-01-T56): business-hours sync pauses, Sync now stays available per close.

## Rollback (flags only; no data is deleted)
1. Turn `closes.agent` off for the firm: runs continue on code alone.
2. If the close screens must go dark: turn `closes.portal_requests` off (POR-11 hides; published requests stay in the client's binder), then `closes.engine` off (the screens show the designed flag-off state; the hourly sync stops).
3. Record the audit row ids, notify the firm's partner in writing, and open a SEV ticket.
4. Turning the flags back on resumes from the stored closes; nothing is recomputed on its own.

## Rehearsal log
| Date | Where | Who | Result |
|---|---|---|---|
| — | staging | — | not yet rehearsed (needs a staging tenant with the fake QBO; rehearse before Tue Oct 3, 2028) |
