---
id: RB-48
title: home.approvals flip (HOME-02 live per firm, Tue Nov 2 and Nov 9, 2027)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2027-10-29
---
# RB-48 · home.approvals flip

| Field | Value |
|---|---|
| Owner | the founder on call flips; the other founder approves (Q-04-T004, P-29) |
| Task | I-01-T22 (the runbook), Q-04-T097 (the flips) |
| When | Tue Nov 2 and Tue Nov 9, 2027, in the 19:00 CT window, one firm at a time |
| Rehearse | on staging, walking the audit half of HOME-02, before Fri Oct 29, 2027; `last_rehearsed` above is set then |
| Rollback | the flag off for the firm. Nothing is lost: the queue only reads the owners' gates, and every decision, sign-off, snooze and reassignment already written stays with its owner and its audit event |
| Related | `firm-rollback.md` (all of a firm's flags), `review-approvals-flip.md` (SHL-10's own flag), `docs/screens/HOME-02.md` |

The flip gives a firm's people `/home/approvals`: everything waiting on them, in one queue, opened at
the owner's own decision or sign-off. The flag grants no authority. A row is a link to where a gate
is decided, HOME-02 records no sign-off, approval or send itself, and the agent never decides
(INV-1).

## 0. The flag

`home.approvals` (kernel registry, boolean, default off; created by I-01-T16). With it off, HOME-01's
rows open their host gates and `/home/approvals` shows the flag-off view state. It retires in the Dec
14–17, 2027 protected bundle (Q-04-T097).

## 1. Preconditions (each recorded in the ops request)

1. **The firm's window is open** (`make windows`): the Tuesday 19:00 CT slot, not a freeze.
2. **The owners are on.** The rows the firm will see have live hosts: `review.grammar_api` for the
   firm, and for the audit half its materiality cards, planning sign-offs and screening proposals.
3. **Counts agree.** On staging, for the firm's own people, HOME-01's Approvals badge equals the queue's
   bands (AC1.2), and a walled client appears in neither (INV-3).
4. **Both founders approve this runbook** and the request names the rollback.

## 2. Flip

```bash
make flag FIRM=<firm-id> FLAG=home.approvals VALUE=true OPERATOR=<you> \
  REASON="HOME-02 flip" APPROVED_BY=<other founder> \
  ROLLBACK="flag off; gates stay with their owners" REQUEST=<ops-request file>
```

## 3. Verify (within the window)

1. As a partner at the firm: `/home/approvals` lists the queue in band order, and the badge equals
   `GET /v1/human-gates/counts`.
2. Open a row: its detail shows the owner's facts. Decide stays disabled until there is a rationale
   (DV-1), and only the reserved person sees it enabled.
3. As a staff member with nothing reserved: no row offers a verb they do not hold.
4. The firm's 5xx rate and the human-gates latency are unchanged after 15 minutes.

## 4. Rollback

```bash
make flag FIRM=<firm-id> FLAG=home.approvals VALUE=false OPERATOR=<you> \
  REASON="<why>" APPROVED_BY=<other founder> ROLLBACK="n/a" HOTFIX="<reason>"
```

Roll back on a count disagreement, a walled row, or any verb offered to someone who does not hold it.
HOME-01's rows go back to opening their host gates on the next read. Record the rollback in the
flip record under `docs/ops/windows/`.
