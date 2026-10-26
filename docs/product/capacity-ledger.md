# Capacity ledger

Planned work against delivered work, per epic, in task-equivalents (the `size_tasks` column of `docs/plan/backlog.csv`; chapter 01 §1.8.3). Updated at each sprint close from the task files in `work/tasks/` (chapter 07, "Exit check, velocity log, capacity ledger"). Solo edition: one builder, so there is one column of capacity, not one per founder (`docs/plan/AMENDMENT-solo.md`).

States come from each task file's `status`: **done**; **in review** (built, PR open or merged with review items left); **in progress**; **not started** (no task file, or a `todo` one). Effort in hours is not recorded in the task files, so "actual" here means rows delivered, not time spent.

## Q-01 Platform operations (updated 2026-10-23, Q-01-T57)

Plan: 59 rows, 53.5 task-equivalents, S0 to S5.

| State | Rows | Task-equivalents | Rows |
|---|---|---|---|
| done | 10 | 7.75 | T05 (TASK-146), T19 (TASK-377), T23 and T50 (TASK-930, TASK-922), T27 (TASK-939), T46 (TASK-912), T48 (TASK-922), T49 (TASK-915), T51 (TASK-916), T59 (TASK-932) |
| in review | 8 | 7.5 | T08 and T09 (TASK-343), T12 and T24 (TASK-352), T13 and T22 (TASK-355), T45 (TASK-934, with TASK-938 done), T47 (TASK-937, with the F-04 sink in TASK-954) |
| in progress | 6 | 5.0 | T01 (TASK-142, console steps), T02 (plan written in TASK-014, TASK-143 not closed), T03 (TASK-144, bootstrap written), T06 and T16 (TASK-342), T10 (ADR-152 and ADR-153 drafted as proposed, TASK-151 not closed) |
| written, apply pending | 1 | 1 | T56 (TASK-971): portal edge Terraform, plans to nothing until its settings exist |
| partly done | 1 | 0.5 | T57 (TASK-972): docs, skills, contract freeze and this ledger done. TASK-014 is **not** done (below) |
| not started | 33 | 31.75 | T04, T07, T11, T14, T15, T17, T18, T20, T21, T25, T26, T28 to T44, T52 to T55, T58 |

Delivered (done plus in review): 18 rows, 15.25 of 53.5 task-equivalents (29%).

**What this means for dates.** Every row that needs an AWS account is still open: the landing zone (T01) is mid-way, so nothing is applied on staging or production, and R0 (M2, Fri Nov 13) and R1 (M4, Fri Dec 11) depend on T01, T03, T07, T14, T15, T17, T18 and T20. The rows that are done or in review are the code that needs no account: adapters, migrations, workflows, routes and the register. They were pulled forward from S1 to S4. TASK-014, and so SPEC-000 AC-21, stays open until a staging deploy runs the Stories 1 to 6 flow.

**Pulled forward, not re-dated.** Chapter 01 dates are unchanged. T56 and T57 (S5) were started on 2026-10-23 because they need no account. T56 lands as Terraform that plans to nothing until the portal domain (F-09-T09) and T15's VPC origin exist.

## Q-03 Hardening and test back-fill: the reserve (set up 2026-10-23, Q-03-T001)

Q-03 is the plan's reserve, not a feature epic: 22.5% of every sprint from S6 to S73 (chapter 01 §1.8.1; Q-03 §9.1). Solo edition: the plan's two founder columns are added into one builder column (`AMENDMENT-solo.md` item 1). Rows are activities sized in task-equivalents (te), typed TEST, OPS or VENDOR. **No reserve row is a feature**, and none may become one.

### Reserve per sprint

| Sprint kind | Sprints | Reserve (te) | Plan's split, kept for reading the epic |
|---|---|---|---|
| S6, the first reserve sprint | S6 | **8.57** | 5.36 + 3.21 |
| Normal sprint | S7–S73, except below | **9.38** | 5.36 + 4.02 |
| Thanksgiving (×0.9) | S28, S54 | **8.44** | 4.82 + 3.62 |
| Holiday (×0.6) | S30, S31, S56, S57 | **5.63** | 3.22 + 2.41 |

S6 plans 9.5 te against 8.57 (111%): the identity and client-access back-fill must be green on the pen-test build pinned Fri Feb 12, 2027 (Q-03 §9.1, "AY's S6–S7 crunch is deliberate"). 2027 Q1 as a whole plans 65 te against 64.8.

### Reserve per workstream (whole epic, S6–S73)

| Workstream | Rows | te | Kind |
|---|---|---|---|
| A · Programme, skills and gates | 37 | 19 | committed |
| B · Back-fill and coverage | 28 | 27.5 | committed |
| C · Mutation | 23 | 18.5 | committed |
| D · Security assurance | 71 | 82 | committed |
| E · Performance and load | 31 | 37.5 | committed |
| F · Resilience and data safety | 34 | 26.25 | committed |
| G · SOC 2 and Safeguards | 20 | 17 | committed |
| H · Accessibility | 7 | 7 | committed |
| I · Continuous upkeep | 72 | 51.5 | committed |
| J · Window hardening | 29 | 46 | committed |
| K · Named call-offs | 11 | 6.75 | conditional (4.25 te return to the lanes if not invoked) |
| L · Standing lanes | 153 | 281.75 | lanes, re-sized at each quarterly review |
| V · Assurance vendors (non-code) | 9 | 5 | outside the reserve |
| **Total** | **525** | **625.75** | |

### Order of spend (chapter 01 §1.8.6 rule 1)

1. **The sprint's back-fill commitment first.** Until the sprint's back-fill rows (workstream B) are met, the reserve funds nothing else: not an integration overrun, and never a feature.
2. **Then integration and conflict overruns** (the L lanes), inside the sprint.
3. **Never a feature.** A feature overrun that asks for reserve time is refused and the refusal is written in the table below; the weekly quality report (`abacus_tools.quality.report`, Q-03-T003) prints this table.
4. **Unspent lane te** moves to the next lane or the next sprint, never to a feature row of another epic, and the move is written below at the quarterly review.

### Refused requests and moved te

| Date | Sprint | Request or move | From → to | te | Why |
|---|---|---|---|---|---|

### S6 (Mon Jan 11 – Fri Jan 22, 2027), pulled forward to 2026-10-23

| Row | Workstream | te | State | Task file |
|---|---|---|---|---|
| T001 programme set-up | A | 0.5 | done | TASK-991 |
| T002 back-fill tracker (`docs/quality/backfill.md`) | B | 0.5 | done | TASK-991 |
| T003 weekly quality report | A | 1 | done | TASK-991 |
| T004 DAST | D | 1 | not started: the ZAP container needs a dependency-allowlist decision first | — |
| T005 call-off (F-01 cut list) | K | 1 | not invoked this sprint; if it stays uninvoked its te return to the lanes | — |
| T006 back-fill TASK-041, TASK-045 | B | 1 | see TASK-992 | TASK-992 |
| T007 back-fill TASK-030, TASK-032 | B | 1 | see TASK-992 | TASK-992 |
| T008 back-fill TASK-040, TASK-044 | B | 1 | see TASK-992 | TASK-992 |
| T009 S6 defect triage | B | 1 | see TASK-992 | TASK-992 |
| T010 `ac-test-author` skill | A | 0.5 | done | TASK-991 |
| T011 ADR-078 catch-up lane 2027 Q1 | L | 1 | see TASK-992 | TASK-992 |

**Labels and burn-down issues.** T001 names GitHub labels (`reserve:q03`, `backfill`, `pen-finding`, `drill`) and a burn-down issue per workstream. Under the solo edition there are no issue queues to route (`AMENDMENT-solo.md` item 4), and the builder works without GitHub issues, so the burn-down lives in files instead: this section for the reserve, `docs/quality/backfill.md` for the 55 owed suites and `docs/quality/escaped-defects.md` for the defects they find (DEC-200).

## P-06 Requests and binders engine (close-out, updated 2026-10-26, P-06-T27)

Plan: 29 rows, 26.0 task-equivalents, S3 to S10 (`docs/plan/epics/P-06.tasks.csv`). States from the task files on `main` plus this close-out's two (TASK-1310, TASK-1311).

| State | Rows | Task-equivalents | Rows |
|---|---|---|---|
| done | 23 | 21.0 | T01 (TASK-415), T02 (TASK-420), T03 (TASK-404), T04 (TASK-405), T05 (TASK-419), T06 (TASK-418), T07 (TASK-914), T08 (TASK-921), T09 (TASK-931), T10 (TASK-967), T11 (TASK-952), T12 (TASK-949), T13 (TASK-989), T14 (TASK-1006), T15 (TASK-1007), T17 (TASK-1140), T18 (TASK-1171), T19 (TASK-1172), T20 (TASK-1194), T23 (TASK-1280), T24 (TASK-1273), T28 (TASK-403), T29 (TASK-993) |
| in review | 3 | 2.75 | T22 (TASK-1223, TASK-1252), T26 (TASK-1310: keyboard suites pass; parity and axe not measured), T27 (TASK-1311: docs written, merge with the batch) |
| in progress | 2 | 1.25 | T16 (TASK-1008: Grace's send not yet walked on staging), T21 (TASK-1195: the reviewer fake and the direct-route run) |
| not started | 1 | 1.0 | T25 (journey E2E j06, j16, j03, j10, j22; no spec file yet) |

Delivered (done plus in review): 26 rows, 23.75 of 26.0 task-equivalents (91%).

**What is still owed.** The epic's DoD is not met: the journeys (T25), the staging walk (T16), the eval run (T21), the Tier C parity locks and the axe run (T26, `docs/quality/parity-P-06.md`) and the C5 v1 freeze (`docs/contracts/README.md`, ready at the batch merge). Open seams, none folded into a done row: the live poll's provider (DEC-158), the OQ-1 preparer path (DEC-136), the follow-up override write (501), `awaiting_review_count`. Chapter 01 dates are unchanged.

## F-05 Design system: M3 calibration (F-05-T26, measured 2026-10-26)

The M3 measure (chapter 01 §1.8.7; F-05 §2 and §9): kit-task throughput for S1 and S2 against the rebalanced plan, and the hold or cut decision. Planned Fri Nov 20, 2026; measured early because S1 and S2 are already behind us. "Done" is the read-only reconcile of main `a0d16491` (every code clause built), not a task file's own status.

**Kit tasks, S1 and S2** (F-05 rows, `size_tasks`; this calibration row itself left out):

| Sprint | Rows | Planned | Done | Partial | Done share |
|---|---|---|---|---|---|
| S1 | 8 | 9.5 | 8.0 | T16 (1.5): the baseline fetch from the design-baselines bucket is not wired (needs AWS) | 84% |
| S2 | 8 | 9.0 | 8.0 | T25 (1.0): the text-only handoff mirror, held while the repo is public | 89% |
| **S1 + S2** | **16** | **18.5** | **16.0** | 2.5 | **86%** |

Counting the two partial rows at half, throughput is 93%. Beyond S2, F-05's S0 to S6 rows deliver 46.5 of 50.5 planned (92%).

**Decision: hold, no cut** (DEC-410). Throughput is above the 85% threshold, so the §2 deferral list (T5 + TPL-05 to K-01, T8 + TPL-08 to N-01, T9 + TPL-09 to T-02, T3 + TPL-03 to F-06) is not invoked. Neither open partial blocks a tier-0 or tier-1 consumer: T16's harness runs on a local baseline directory, and T25's mirror is a publication choice.

**Post-rebalance S1–S6 AY plan for F-02…F-05** (F-05 §9, planned tasks per sprint) beside what was delivered (rows done on main, all four epics, AY and N together since the solo edition has one builder):

| Sprint | S1 | S2 | S3 | S4 | S5 | S6 |
|---|---|---|---|---|---|---|
| AY capacity (ch. 01 §1.8.3) | 11.1 | 10.0 | 11.1 | 6.6 | 6.6 | 11.1 |
| F-02…F-05 AY, rebalanced plan | 11.75 | 11.0 | 12.5 | 8.0 | 6.5 | 10.5 |
| F-02…F-05 planned (all rows) | 26.75 | 24.25 | 20.5 | 11.5 | 7.5 | 11.5 |
| F-02…F-05 delivered (done rows) | 24.25 | 22.75 | 20.5 | 10.0 | 6.5 | 9.5 |

The residual overcommit the plan names (106–121% of AY capacity in S1 to S4) did not bind: the solo build delivered S1 to S6 of these four epics in calendar weeks, ahead of chapter 01's dates, which are unchanged.
