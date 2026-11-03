# Quarterly reserve review, 2027 Q3 (Q-03-T162)

The reserve's burn by workstream against the plan, the period's escaped-defect retro, the lanes
re-sized for 2027 Q4, and the calibration inputs (read by Q-03-T159 for M14). Solo edition: one
builder, so one column of capacity, not one per founder (`docs/plan/AMENDMENT-solo.md` item 1).
Reviewed 2026-11-03; the plan's 2027 Q3 is S19 to S25 (Jul 12-Oct 15, 2027), which the build reached
early.

Acceptance: "The review is recorded in the capacity ledger and the next quarter's lanes are
re-sized."

## Burn by workstream (S19-S25)

Planned: the 51 Q-03 rows in S19-S25 (`docs/plan/epics/Q-03.tasks.csv`), 65.75 te. **Merged**: a
`main` commit cites the row. **In review**: this batch's open PRs cite it. **Not traced**: no commit
cites it; some may be built under another row (the S0-S25 audit found such rows), so this is an upper
bound on what is undone. The CSV does not tag rows with a workstream: each is placed by its title
(lane, fix-forward, reserve review and calibration rows under L; pen test, delta, DAST and fuzz under
D; and so on), so a row near a boundary may sit in the neighbouring workstream.

| Workstream | Rows | Planned te | Merged (rows, te) | In review (rows, te) | Not traced (rows, te) |
|---|---|---|---|---|---|
| A · Programme, skills and gates | 1 | 0.50 | 0, 0.00 | 0, 0.00 | 1, 0.50 |
| B · Back-fill and coverage | 2 | 1.50 | 0, 0.00 | 0, 0.00 | 2, 1.50 |
| D · Security assurance | 8 | 8.50 | 1, 0.50 | 0, 0.00 | 7, 8.00 |
| E · Performance and load | 5 | 4.50 | 1, 0.50 | 0, 0.00 | 4, 4.00 |
| F · Resilience and data safety | 4 | 3.00 | 0, 0.00 | 0, 0.00 | 4, 3.00 |
| G · SOC 2 and Safeguards | 3 | 3.00 | 0, 0.00 | 0, 0.00 | 3, 3.00 |
| H · Accessibility | 2 | 1.50 | 0, 0.00 | 0, 0.00 | 2, 1.50 |
| I · Continuous upkeep | 2 | 2.00 | 0, 0.00 | 0, 0.00 | 2, 2.00 |
| J · Window hardening | 2 | 2.50 | 0, 0.00 | 0, 0.00 | 2, 2.50 |
| L · Standing lanes | 22 | 38.75 | 1, 1.75 | 5, 7.00 | 16, 30.00 |
| **Total** | 51 | 65.75 | 3, 2.75 | 5, 7.00 | 43, 56.00 |

Burn: **2.75 te merged and 7.00 te in review, 9.75 of 65.75 te (15%)**. What the reserve paid for
this quarter was the standing lanes' fix-forward work on the batches (integration lane, escaped
defects, the end passes); the committed workstreams of the quarter are mostly waiting on things the
build cannot do alone: pen tests (deferred, DEC-1389), load tests on the perf stack (Q-03-T036's
`infra/envs/perf` is not built), SOC 2 and drills on an environment that does not exist yet, and
window hardening for a firm that is not live.

## Escaped-defect retro

`docs/quality/escaped-defects.md`: 115 rows, 22 of them found in S25 (ED-300 to ED-321). By the
layer that should have caught each:

| Layer | All rows | S25 |
|---|---|---|
| integration | 45 | 6 |
| review | 14 | 5 |
| contract | 11 | 3 |
| spec | 11 | 1 |
| component | 8 | 2 |
| unit | 8 | 3 |
| security | 8 | 0 |
| journey | 3 | 2 |
| other (golden, e2e, infra, as written) | 7 | 0 |

Severity: 93 SEV4, 21 SEV3, 1 written "low"; 109 fixed, the rest closed, mitigated or held by a
strict xfail. The S25 pattern is that rows were built with their tests written but not run until the
batch (the "build first, test last" working agreement): integration and review gaps then surface all
at once in the end pass. Recurrence controls added this quarter: CAST-001 (ED-302), the trace-id and
sign-in-code fixes (ED-300, ED-301), journeys sharded and gallery changes acceptable by label
(Q-03-T163).

## Lanes re-sized for 2027 Q4 (S26-S31)

| Lane | Q4 plan | Re-sized | Why |
|---|---|---|---|
| Integration and conflict (Q-03-T163 parts 2-3) | as planned | **kept, first in the order of spend** | every batch this quarter needed it; `main` still needs one green run |
| Escaped-defect fix-forward (back end and front end) | as planned | **kept** | 22 defects in one batch |
| ADR-078 catch-up (independent suites) | as planned | **kept** | the only workstream with merged te this quarter |
| Window hardening, deadline-week watches, support pools | as planned | **held until the first live firm**; rehearse on PF-X1 (DEC-2081) | no firm is live, so the guards are inert |
| Pen tests and deltas | as planned | **deferred** (DEC-1389) | unchanged decision |
| Load, drills, SOC 2 | as planned | **waiting on environments** (perf stack, staging) | not lane work |

Unspent lane te moves to the next lane or sprint, never to a feature (Q-03 §9.1).

## Calibration inputs
Carried to M14 in `docs/quality/m14-calibration-inputs.md` (Q-03-T159).
