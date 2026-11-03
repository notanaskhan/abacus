# M14 calibration inputs (Q-03-T159)

What the M14 re-plan (re-baseline #4, Fri Oct 15, 2027 in the plan's calendar) reads from the
reserve. Solo edition: one builder column, so "per founder" is one column (`AMENDMENT-solo.md`
item 1). Read 2026-11-03.

Acceptance: "The M14 re-plan reads reserve actuals per founder per workstream."

## Reserve actuals by workstream, 2027 Q3 (S19-S25)
From the 2027 Q3 review (`docs/quality/reserve-review-2027-q3.md`, Q-03-T162):

| Workstream | Planned te | Merged te | In review te |
|---|---|---|---|
| A · Programme, skills and gates | 0.50 | 0 | 0 |
| B · Back-fill and coverage | 1.50 | 0 | 0 |
| D · Security assurance | 8.50 | 0.50 | 0 |
| E · Performance and load | 4.50 | 0.50 | 0 |
| F · Resilience and data safety | 3.00 | 0 | 0 |
| G · SOC 2 and Safeguards | 3.00 | 0 | 0 |
| H · Accessibility | 1.50 | 0 | 0 |
| I · Continuous upkeep | 2.00 | 0 | 0 |
| J · Window hardening | 2.50 | 0 | 0 |
| L · Standing lanes | 38.75 | 1.75 | 7.00 |
| **Total** | **65.75** | **2.75** | **7.00** |

One column: the builder's. Effort in hours is not recorded (`capacity-ledger.md`), so actuals are rows
delivered, in task-equivalents.

## Escaped-defect trend

Rows in `docs/quality/escaped-defects.md` by the sprint that found them:

| S1 | S6 | S7 | S8 | S9 | S10 | S11 | S12 | S13 | S14 | S15-S24 | S25 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 16 | 12 | 14 | 8 | 13 | 15 | 10 | 2 | 2 | 0 | 22 |

The quiet S15-S24 stretch is not a clean one: those sprints merged in batches with their suites run
late or not at all, and S25's end pass found 22 at once, most of them integration and review gaps
(ED-300 to ED-321). The M14 re-plan should read the trend as "defects surface at the batch", not as
"defects stopped".

## Back-fill and remediation actuals
- **Back-fill** (`docs/quality/backfill.md`): of the 55 owed suites, 35 back-filled, 11 superseded,
  9 done in tranche 0. None is owed.
- **Remediation** (pen-test findings): none, because no pen test has run (DEC-1389). The pen-test
  gates stay open; nothing here closes them.

## For the re-plan
- The reserve's committed workstreams (D, E, F, G, J) are blocked by environments, vendors or a live
  firm, not by capacity; their te should move with the dates that unblock them, not into features.
- The lanes are where the reserve's te went (integration, escaped defects, the end passes); size the
  next quarter's lanes from that (Q-03-T162).
