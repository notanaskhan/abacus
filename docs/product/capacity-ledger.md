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


## F-06 actuals (F-06-T23, 2026-11-01)

F-06 (T6, T10, T16 and the TPL-01, 06, 10, 16, 19 specimens) is built on main through the T22 lock (planned 22.75 task-equivalents in 24 rows); this row adds the kits' written hand-offs (`docs/design/kits/{signing,workbook,document-on-well,portal-mobile}.md`) and the build-screen skill's pointer to them. The epic shipped inside S14 to S22 in the solo build's calendar weeks, ahead of chapter 01's dates; no F-06 cut was invoked. TPL-19 frames 3, 4, 8 and the permission-off variant are deferred to R-03 (DEC-97; `docs/plan/deferrals/R-03-tpl19.md`).


## T-02 actuals (T-02-T35, 2026-11-01)

T-02 (returns workflow, organizers and K-1s) planned 32.25 task-equivalents in 35 rows (S15–S21);
delivered 35 task files for 35 rows (T-02-T15 folded into T-01-T18, its acceptance there), the
last five (T31–T35) in the S21 batch with T-01 and N-02's closing rows. No row was dropped; the
open items are written in `docs/handoffs/T-02/README.md`.


## M14 ops retro (Q-04-T087, Q-04-T088; 2026-11-03, synthetic)

Rehearsed on PF-X1 and reported as synthetic (DEC-1530, DEC-2081); no pilot firm is live, so every
firm figure is zero or no data. For re-baseline #4.

| Figure | Value |
|---|---|
| Support hours, S22 to S25 | 0, 0, 0, 0 against reserves of 31.50, 43.50, 43.50 and 36.00 hours; RK-07 does not fire |
| W2 to W8 for PF-X1 | no data (no snapshots; dossier at shadow) |
| Flips executed and rolled back in the window | 0 and 0 |
| Pages per week, hotfixes, change failure rate | see Q-04-T088 (`docs/ops/pilot/retros/m14-ops-retro-n.md`) |

The retros are `docs/ops/pilot/retros/m14-ops-retro-ay.md` and `m14-ops-retro-n.md`.
- Q-04-T088 (N): change failure rate has no denominator (0 production releases); `main`'s `ci` had
  0 green of 48 runs since 2026-10-30; 0 hotfixes; 0 pages per week. Fractional SRE: kept per ADR-100,
  contracted at the first real go-live (DEC-2082).

## Q-03 reserve review 2027 Q3 (Q-03-T162; 2026-11-03)

S19-S25: 51 rows, 65.75 te planned; 2.75 te merged, 7.00 te in review (the S25 batch's lane rows),
56.00 te not traced (an upper bound on what is undone). Escaped defects: 22 in S25, mostly
integration and review gaps found at the batch. 2027 Q4 lanes: integration, escaped-defect and
ADR-078 catch-up kept; window hardening held until the first live firm; pen tests deferred
(DEC-1389); load, drills and SOC 2 waiting on environments. The review is
`docs/quality/reserve-review-2027-q3.md`.
- Q-03-T159 (M14 calibration inputs): one builder column; 2027 Q3 actuals are 2.75 te merged and
  7.00 te in review of 65.75 te; escaped defects by sprint found 22 in S25 after 0 in S15-S24
  (batches tested late); back-fill 55 of 55 accounted for; no pen-test remediation (DEC-1389).
  `docs/quality/m14-calibration-inputs.md`.
## P-04 Review grammar & sign-off engine (updated 2026-11-03, P-04-T62)

Plan: 62 rows, 59.25 task-equivalents, S8 to S26. Counted from the task files (TASK-3223).

| State | Rows | Task-equivalents | Rows |
|---|---|---|---|
| done | 28 | 26.25 | T01 to T18 and T21 (the contract, schema, slots, projector and sign-off services), T36, T37, T42 to T44, T49 to T51, T58 |
| in review (merged, review items left) | 32 | 32.0 | T19, T20, T22 to T35, T38 to T41, T45 to T48, T52 to T57, T59, T60 |
| built on the S26 stack (PR open) | 2 | 1.0 | T61 (runbook, skill, consumer notes; staging rehearsal pending), T62 (this row) |
| not started | 0 | 0 | — |

P-04 actuals: every row has a task file and built code or docs; no row is deferred. Open clauses
carried by the in-review rows are listed in their task files (staging flips on PF-X1, the RB rehearsal
for the review grammar). `review.grammar_api` is retired; `review.approve_agent_output` and
`review.checkpoints` are renewed to May 1, 2027.

## P-10 Agent runtime v2 and real time (close-out, 2026-11-12, P-10-T56)

Plan: 58 rows, 55.75 task-equivalents, S29 to S38 (chapter 01 dates Dec 2027 – Apr 2028); built
in the solo calendar from 2026-11-06 to 2026-11-12. Counted from the task files and the S29–S38
status files; DEC-4414.

| State | Rows | Task-equivalents | Rows |
|---|---|---|---|
| done | 50 | 50.75 | T01 to T12, T16 to T45, T47 to T49, T52, T55 to T58 |
| partial (built; a staging, evaluation-account or founder step left) | 7 | 4.5 | T13 (committed parity reports), T14 (production-sized run), T15 (edge apply), T46 (real evaluation runs), T50 (staging runs), T51 (staging load run and RB-28 rehearsal), T54 (rehearsal, shadow, canary) |
| deferred | 1 | 0.5 | T53 delta pen test (DEC-1389) |
| not started | 0 | 0 | — |

P-10 actuals: every row has a task file. No row of the pre-agreed internal cut list was invoked
except cut 3 (the PDF trace export's v2 fields, A-07 or G-02 depth). The partial rows' remaining
steps are listed in `docs/plan/status/P-10-closeout.md`; none blocks a consumer epic's build.


## R-01 actuals (R-01-T36, 2026-11-12)

R-01 (portal documents, drops, the third-party room, email templates, portal settings and sender
domains) planned 26.75 task-equivalents in 36 rows (S9–S18); every row is built on main (31 with
task files; T26 to T28 and T34 cited in their commits), and this row closes the docs. No cut was
invoked. Two rows stay partial outside the repo: R-01-T32 (the journeys on staging) and R-01-T34
(PF-X1 synthetic; real DKIM and MAIL FROM need SES and a live firm). Contracts frozen: C5 section
`portal-pbc` v1 and C16 v1.1. The Jul 13 per-firm flips and their rollbacks:
`docs/runbooks/r01-portal-flip.md`.
