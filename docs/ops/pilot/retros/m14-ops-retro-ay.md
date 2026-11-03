# M14 ops retro, part AY (Q-04-T087), rehearsed on PF-X1

**Synthetic.** Run on the synthetic test firm PF-X1 (Brightwater Hale, DEC-1530) and reported as
synthetic (DEC-2081). M14 is Fri Oct 15, 2027 in the plan's calendar: the autumn window's close and
re-baseline #4. No pilot firm is live (DEC-1391).

Acceptance: "The retro numbers reproduce from snapshots and logs and are in the capacity ledger
before re-baseline #4."

## How to reproduce

    python -m abacus_tools.m12_pack --firm 293fc3e7-be13-4767-ae6a-ce245b2dbda9 --code PF-X1         --week 2027-08-30 --week 2027-09-06 --week 2027-09-13 --week 2027-09-20         --week 2027-09-27 --week 2027-10-04 --week 2027-10-11         --sprint 22 --sprint 23 --sprint 24 --sprint 25

The pack (Q-04-T054's tool) reads the snapshots and logs only and prints each input's SHA-256, so a
second read differs only where an input did. This task labels each firm by its pilot code: the pack
is committed, and firm names never enter git (`docs/ops/pilot/README.md`). The read below is from
the local database, where PF-X1 has no metric snapshots.

## The retro's figures

| Figure | Value | Source |
|---|---|---|
| Support hours per sprint against the reserve | S22 0 of 31.50, S23 0 of 43.50, S24 0 of 43.50, S25 0 of 36.00; RK-07 does not fire | `support-hours.csv` against the reserve rows in `backlog.csv` |
| W2 and W8 | none recorded (PF-X1 dossier at shadow) | `docs/ops/go-live/PF-X1.md` |
| W4 and W5 | no data in any week | `pilot_metric_snapshots` (Q-04-T050's read) |
| W6 and W7 | no data in any week (no enrolment with a baseline) | `pilot_metric_snapshots` |
| W1, W3, W9, W10 | not measured by the platform: F-09's partner and commercial signals | F-09-T186's evidence pack |
| Flips executed and rolled back | 0 and 0: none planned in the window (`make flag-calendar`) and no production | Q-04-T084, T085 |
| Escaped defects in the weeks read | none dated in Aug 30-Oct 17, 2027. The build's own period logged ED-300 to ED-321 on 2026-11-02 (Q-03-T164, T165) | `docs/quality/escaped-defects.md` |

### The pack (read 2026-11-03)

Read from code by `make m12-pack`; reproduce with the same inputs. Inputs:

- weeks read: 2027-08-30, 2027-09-06, 2027-09-13, 2027-09-20, 2027-09-27, 2027-10-04, 2027-10-11; sprints: 22, 23, 24, 25; hours per task-equivalent: 6
- support log `docs/ops/pilot/support-hours.csv` sha256 283223a6f3f2d7d0bc372fee78c5a32afdddcd6be48333045bd7120bad168889
- escaped-defect log `docs/quality/escaped-defects.md` sha256 35f4f522adca0f9bbc082a25ad4142264c5f6f97a53eceea0a811d139437625f
- backlog `docs/plan/backlog.csv` sha256 5eed89b6e907bbf88b6632c7755bb34656c1f38b914e0b9021c2d5985cb6d3db

## W4 and W5 (chapter 11 §11.6.2, Q-04-T050's read)

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-08-30 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-08-30 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-09-06 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-09-06 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-09-13 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-09-13 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-09-20 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-09-20 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-09-27 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-09-27 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-10-04 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-10-04 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

| Firm | Week | Weeks live | Signal | Value | Enrolments (values) | Colour | Owner | Action |
|---|---|---|---|---|---|---|---|---|
| PF-X1 | 2027-10-11 | 0 | W4 Portal activation: invited client contacts who sign in | — | 0 (none) | no data |  |  |
| PF-X1 | 2027-10-11 | 0 | W5 PBC items delivered through the portal | — | 0 (none) | no data |  |  |

## W6 and W7

| Firm | Week | Signal | Value | Counts | Colour | Note |
|---|---|---|---|---|---|---|
| PF-X1 | 2027-08-30 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-09-06 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-09-13 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-09-20 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-09-27 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-10-04 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |
| PF-X1 | 2027-10-11 | W6 request → received vs baseline | — | 0 enrolment(s) with a baseline | no data | slower is red only at week 8 |

## W2 and W8 (as recorded in each go-live dossier)

| Pilot code | Dossier level | W2 / W8 lines recorded |
|---|---|---|
| PF-X1 | shadow | none recorded |

## Support hours against the reserve, and SEVs

| Sprint | Hours logged | Reserve hours | Over | SEV1 | SEV2 | SEV3 |
|---|---|---|---|---|---|---|
| S22 | 0 | 31.50 | no | 0 | 0 | 0 |
| S23 | 0 | 43.50 | no | 0 | 0 | 0 |
| S24 | 0 | 43.50 | no | 0 | 0 | 0 |
| S25 | 0 | 36.00 | no | 0 | 0 | 0 |

RK-07 (two sprints running over the reserve): does not fire.

## Escaped defects found 2027-08-30 to 2027-10-17

| ID | Severity | State |
|---|---|---|
| none | | |

## Into the capacity ledger
`docs/product/capacity-ledger.md` gains "M14 ops retro (Q-04-T087, Q-04-T088)" with these figures,
for re-baseline #4.

## What only a live firm can show
W2 to W8 with values, a champion's reading of them, support hours that were spent, and a flip
executed or rolled back.
