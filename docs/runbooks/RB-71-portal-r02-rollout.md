---
id: RB-71
title: R-02 portal rollout (portal.approvals, portal.deliverables, portal.governance_room)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2028-02-25
---
# RB-71 · R-02 portal rollout

| Field | Value |
|---|---|
| Owner | the founder on call flips; the other founder approves every flip (Q-04-T004, P-29) |
| Task | R-02-T25 (the plan), Q-04 (the flips) |
| Flags | `portal.approvals` (POR-08, C18), `portal.deliverables` (POR-09, C10), `portal.governance_room` (POR-15); per firm, default off |
| Contracts | `docs/contracts/portal-approvals.md` (C18 v1, frozen), `docs/contracts/deliverables.md` (C10 v1, frozen) |
| Rollback | the flag off (below); nothing a client decided is undone |

## 1. Before any flip (each firm, each environment)
1. **Email templates are database content** (DF-40, AGENTS rule 16). Import them through `POST /v1/platform/email-templates/import` (staff, per environment), then publish, before the flag goes on; until then their emails settle `suppressed`:
   - `notification.approval_requested` (POR-08: an item waits on the client);
   - `notification.governance_letter_sent` (POR-15: a letter in the room);
   - "Deliverable ready" (reused from T-01/T-02; check it is published for the firm's sender domain).
2. The firm's sender domain is verified (R-01-T27) and its branding is set: the portal never shows "Accrued" (DEC-01).
3. The staging journeys are green within 24 hours: `j12 8`, `j12 10`, `j12 scoped`, `j03 9b`, `j03 18` (`apps/web/e2e/journeys/`), plus the three screen specs (`e2e/screens/POR-08`, `POR-09`, `POR-15`).
4. C18's registered kinds are the ones the firm uses: `proposed_entry` and `fs_draft` live; `uncorrected_misstatements` (R-02-T15); `fs_package` waits for C-02 and A-08, so a firm on packages keeps POR-08 a to d as fixtures.

## 2. The flips
| When | Where | What |
|---|---|---|
| Tue Feb 29, 2028, the canary slot | production canary (PF-X1, synthetic) | all three flags on, both founders approving |
| Tue Mar 7, 2028 | the first real firms (design partners) | `portal.approvals`, then `portal.deliverables` |
| Tue Mar 21, 2028 | the remaining real firms | all three, `portal.governance_room` last |

```bash
make flag FIRM=<firm-id> FLAG=portal.approvals VALUE=true OPERATOR=<you> APPROVED_BY=<the other founder> REASON="RB-71 <ticket>" ROLLBACK="make flag ... VALUE=false"
```

Check after each flip: the firm's portal nav shows Approvals, Deliverables and (for TCWG members) the governance room; one client principal opens POR-08, POR-09 and POR-15 on the firm's own host.

## 3. Roll back
Turn the flag off for the firm (`make flag FIRM=<firm-id> FLAG=<flag> VALUE=false OPERATOR=<you> REASON="RB-71 rollback <ticket>"`; every flag at once: `ALL_OFF=1`):
- **`portal.approvals` off:** POR-08 answers 404 and its nav item and home source go away. Items already decided stay decided (C18 rows are insert-only); open items wait.
- **`portal.deliverables` off:** POR-09 answers 404. Published deliverables stay published, and the download audit keeps its rows.
- **`portal.governance_room` off:** POR-15 answers 404, and A-07 sends governance letters through the acknowledgement envelope (DEC-83).

## 4. The flag renewal
The three flags expire 2027-05-07 under DEC-137 (registry dates). File the renewal ticket for the **Thu Apr 13, 2028** train: renew registry-only to a date outside every release window (`make flag-calendar`), or retire the flags once every firm is on.

## Rehearsal log
| Date | Who | Environment | Result |
|---|---|---|---|
