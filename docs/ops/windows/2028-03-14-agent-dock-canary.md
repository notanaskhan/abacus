# Agent dock and trace canary flip request, Tue Mar 14, 2028 7:00 PM CT (P-09-T20)

**Request, not a flip.** No firm is live (DEC-1391) and there is no production stack yet; this is
the request P-09 §8 files for the canary, in the plan's calendar. The firm part runs on the
synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and is reported as synthetic.

| Field | Value |
|---|---|
| Flags | `agent_dock.enabled`, `run_trace.enabled` (per firm) |
| Firm | the canary firm (PF-X1, synthetic, until a pilot firm is live) |
| Slot | Tue Mar 14, 2028, 19:00 CT (a Tuesday slot; `release.window_gate` decides) |
| Approvers | ayushkbhatia, notanaskhan (both founders) |
| Runbook | RB-69 |
| Status | filed, awaiting both approvals and a staging rehearsal |

## Before the flip
1. RB-69 rehearsed on staging: both flags off and on for the firm, a run watched in the dock and
   its trace opened, the two signals read on the dashboard.
2. A shadow run on the canary firm: `agent_runtime.v2` on, the engagement run in `shadow` stage
   (RB-39), the dock showing it with no write reaching a record.
3. P-09-T19's journeys green in the fixture and compose projects; parity locks green (P-09-T18).

## The flip
Turn `agent_dock.enabled` on for the canary firm, then `run_trace.enabled`. Open a running run's
dock and its trace as a manager and as a staff member; confirm Lena-style refusals (403) for a
person `agent_run.read` refuses.

## Rollback (written)
Turn `run_trace.enabled` off, then `agent_dock.enabled` off, for the firm (RB-69 §3). Nothing is
written by either flag; decisions stay on their own pages. Record the rollback here with the time.
