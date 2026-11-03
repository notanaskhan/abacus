# S26 support reserve, AY lane (Q-04-T095), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The sprint is S26 of the plan (Oct 18-29, 2027); no pilot firm is live
(DEC-1391).

Acceptance: "Hours are logged against this row at the sprint review and first responses met the
SLA, or the RK-07 trigger is raised."

## Hours
`docs/ops/pilot/support-hours.csv` gains S26's AY rows: **0 hours** in each week (Oct 18 and Oct
25), no SEV1, SEV2 or SEV3. No firm reached the desk, so there was no first response to time. RK-07
(two sprints over the reserve) is not raised.

## The lane's duties

| Duty | This sprint | Source |
|---|---|---|
| Shared inbox | no messages: no firm has the address | `docs/ops/pilot/README.md` |
| Tue/Thu office hours | none held: no firm to invite | the same |
| Weekly pilot-metrics read | no data for PF-X1 (no enrolment snapshots on the local database) | Q-04-T050 |
| SEV3 triage to the owning epics | no firm-reported SEV3; the batch's own defects went to their rows (Q-04-T094's record) | |
| Firm-admin questions | none | |
| Monthly flag-hygiene report | below | `make flag-calendar` |

### Flag hygiene (`make flag-calendar`, 2026-11-03)
89 flags, each with its owner; none expires within 21 days of today. S26 retired
`review.grammar_api` (P-04-T62) and renewed `review.approve_agent_output` and `review.checkpoints`
to 2027-05-01 with the S26 flags it created; no flag's expiry falls inside the Jan 1 - Apr 20 freeze
of either year. On the plan's calendar every flag would still need renewing past its last train
before the first real go-live (RB-16 §2).

## What only a live firm can show
Real support hours and their SEV counts; first-response times against the 2-business-hour SLA; an
office-hours session; a firm admin's question answered.
