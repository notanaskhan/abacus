# S25 support reserve, AY lane (Q-04-T091), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The sprint is S25 of the plan (Oct 4-15, 2027, inside the autumn window for
tax and EBP firms); no pilot firm is live (DEC-1391).

Acceptance: "Hours are logged against this row at the sprint review and first responses met the
SLA, or the RK-07 trigger is raised."

## Hours
`docs/ops/pilot/support-hours.csv` gains S25's AY rows: **0 hours** in each week (Oct 4 and Oct 11),
no SEV1, SEV2 or SEV3. No firm reached the desk, so there was no support time to log. RK-07 (two
sprints over the reserve) is not raised.

## The lane's duties

| Duty | This sprint | Source |
|---|---|---|
| Shared inbox | no messages: no firm has the address | `docs/ops/pilot/README.md` |
| Tue/Thu office hours | none held: no firm to invite | the same |
| Weekly pilot-metrics read | W4 and W5 read **no data** for PF-X1 in both weeks: it has no enrolment snapshots on the local database (`make pilot-read`) | Q-04-T050 |
| SEV3 triage to the owning epics | no firm-reported SEV3. The period's escaped defects were found by the batch's own checks and are logged with their owners (ED-300 to ED-321, Q-03-T164 and T165) | `docs/quality/escaped-defects.md` |
| Firm-admin questions | none | |
| Monthly flag-hygiene report | below | `make flag-calendar` |

### Flag hygiene (`make flag-calendar`, 2026-11-03)
85 flags, owners named on each; none expires within 21 days of today. **Every one expires between
Apr 21 and Apr 30, 2027** (54 on Apr 21, the rest Apr 26-30), so on the plan's S25 dates all 85 would
already have lapsed. Before the first real go-live, each flag is renewed past its last train
(`docs/ops/release-windows.md` §2) or removed if its rollout is done: a registry-only change, never
an extension into a window (RB-16 §2).

## What only a live firm can show
Real support hours and their SEV counts; first-response times against the 2-business-hour SLA; an
office-hours session; a firm admin's question answered.
