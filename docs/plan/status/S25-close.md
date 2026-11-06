# S25 close (2026-11-06)

**S25 is not closed by the prompt book's definition.** Steps 2 and 3 of the close have not run: `deploy-staging` has no recorded runs, so no journey, axe or parity check has run against staging, and `main` is not green. What follows is step 4, written from what is on `main` and in the stack held for merge. What stays open row by row is in [S25.md](S25.md).

Plan dates: Oct 4 to Oct 15, 2027. Built: 2026-11-02 to 2026-11-06. Counts assume the held PRs merge.

## Close steps
| Step | State |
|---|---|
| 1. Merge finished work | S25's code and records merged 2026-11-03 and 2026-11-06, mostly with `[skip ci]`. The rows below are held for one batch |
| 2. With main green, deploy staging once | **Not run.** `main`'s last green `ci` is `faf6d1524` (2026-10-29). The run on `37856f6c7` was in progress when this was written, and the two finished runs before it failed |
| 3. Journeys, axe and parity on staging | **Not run.** Journeys pass in the fixture project only (K-01-T25, P-04-T57) |
| 4. This file and the status column | Done |

## Tasks done versus planned
Planned 50 rows, 49.5 task-equivalents.

| Result | Rows |
|---|---|
| Done | 23 |
| Partial | 20: 10 product, 2 quality lanes, 8 run on the synthetic firm |
| Todo | 7 |

This corrects an earlier count. S25.md recorded 22 done, and a later check against `main` found five of those rows short of their full text: A-04-T18, A-04-T20, A-06-T10, N-04-T05 and P-04-T60. The held batch closes those five and A-06-T11, which is why the count reads 23 rather than 17.

## Carry-overs
| Rows | Reason |
|---|---|
| A-04-T19, A-04-T24, A-05-T16 | In progress in a separate session; A-04-T19 is #1306, not yet merged |
| A-04-T21 | Inquiries list and Remind follow A-04-T19; the decision strip and amber notes need a data marker |
| A-05-T17 | The viewer's matching line needs SHL-08's anchors, which the row's acceptance names (DV-EBP-02-3). SHL-07 on the reference is also open |
| A-05-T19 | Waits on P-03's census scan |
| A-06-T08 | Needs the audit CPA's signature on the golden review |
| K-01-T25, P-04-T57 | Need staging and demo-firm data |
| P-04-T59 | Mutation baseline, fleet ids and the observability module |
| Q-03-T161, Q-03-T163 | No perf stack; `main` not green |
| Q-04-T084 to T091 | No live firm (DEC-1391). They ran on PF-X1 and are reported as synthetic (DEC-1530) |
| F-09-T185 to T189 | Founders' notes, live partners, a hire and committed firms |
| P-11-T18 | Counsel's written position on Textract under Sec. 7216 |
| Q-03-T160 | Quota requests through the provider consoles |

## Demo script
Fixture mode only (`make dev-fixtures`). None of this has been walked on staging.

1. **AUD-08, risk approval.** Open R3's drawer. Who the card waits for and when it was routed come from the server. As Margaret, Approve opens the decision. As anyone else with the action, Remind notifies the person named, and only that person is told.
2. **EBP-02, plan review.** At 20 of 20 verified, open Version 1 from the Version 2 pill. It is read-only, with 18 rows and a "+2 rows" ribbon naming Long-term part-time and Catch-up. Open Version 2 returns.
3. **EBP-02 c, SPD conflict.** Entry dates carries "SPD: quarterly" and the SPD's sentence. Clicking the row opens the SPD in the dock; it opens on the first page with no line lit. Raise exception… opens SHL-15.
4. **AUD-15, findings.** The list shows the severity bands and the badge of findings awaiting the partner.
5. **NOT-01, notices.** The status tiles foot to 9 and the By type tile reads 3 CP2000, 2 CP14, 1 CP501, 3 State.

Consultations and the projected conversion have routes and tests but no screen (AUD-28 is Q-05), so they can only be shown through the API.

## Incidents
No production exists, so there are no production incidents. Delivery problems:
- **`main` has not been green since 2026-10-29.** S24 to S28 merged with `[skip ci]` or on an unread run, by decision. CI found 96 failures on S25's end pass (DEC-2078); #1302 (DEC-2363) repairs the latest set, and its verdict is the run in progress.
- **A stuck CI queue** on the S25 end pass; stray runs were cancelled and rerun.
- **An overstated status.** "42 on `main`" and then "22 done" were both too high. The count above comes from reading each row's full text against the code.

## Calibration trigger (§1.8.7, M14)
M14 measures throughput S16 to S25 including support, and the conversion result, then re-plans PH4 and PH5.
- **Throughput cannot be measured as the gate means it.** S25 was built in days by one builder against a two-week plan, and most rows stop at their code clause, so rows per week says little about readiness.
- **There is no conversion result.** No pilot firm is live (DEC-1391), and pen tests and accessibility audits are deferred (DEC-1389).
- **The gate's action has not been taken.** PH4 and PH5 have not been re-planned, and `docs/plan/status/PH3.md` does not exist. That call is Ayush's.
