# S52 support reserve, AY lane (Q-04-T234), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). The sprint is S52 of the plan (Oct 16–27, 2028); no pilot firm is live
(DEC-1391).

Acceptance: "Hours are logged against this row at the sprint review and first responses met the
SLA, or the RK-07 trigger is raised."

## Hours
`docs/ops/pilot/support-hours.csv` gains S52's AY rows: **0 hours** in each week (Oct 16 and Oct
23), no SEV1, SEV2 or SEV3. No firm reached the desk, so there was no first response to time. RK-07
(two sprints over the reserve) is not raised (`docs/ops/pilot/retros/ext-season-2028-retro.md`).

## The lane's duties

| Duty | This sprint | Source |
|---|---|---|
| Shared inbox | no messages: no firm has the address | `docs/ops/pilot/README.md` |
| Tue/Thu office hours | none held: no firm to invite | the same |
| Weekly pilot-metrics read | no data for PF-X1 (no enrolment snapshots; `abacus_tools.m12_pack`, Q-04-T231) | Q-04-T050 |
| SEV3 triage to the owning epics | no firm-reported SEV3 | |
| Firm-admin questions | none | |
| Monthly flag-hygiene report | below | `make flag-calendar` |

## Flag hygiene (`make flag-calendar`, 2026-11-20)
No flag expires before Thu Feb 11, 2027 in today's calendar: the earliest are the three
`prompt.tax.*` flags (Feb 11), the consolidation and tb-mapper flags (Feb 12) and the three K-03
flags `templates_v2.enabled`, `sheets.enabled`, `agent_columns.enabled` (Feb 18, created dark by
K-03-T06). No renewal is due this month; none is on at a live firm.
