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
