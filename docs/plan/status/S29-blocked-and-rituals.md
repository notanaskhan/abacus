# S29: rows not built, and why (DEC-2401)

Recorded at the S29 build (2026-11-06). None is marked done, and no gate they guard is treated as met (DEC-1389, DEC-1391).

## Code rows held back
| Row | What holds it |
|---|---|
| A-06-T32 | Sprint 28 session owns it; Northwind's completion slice landed on main for it. |
| N-04-T25, N-04-T27 | Real evals and the CPA label review (DEC-2312). |
| A-05-T49, T-03-T18 | Staging, CPA and counsel. |

## Partials from this sprint
| Row | What's open |
|---|---|
| A-06-T29 | Emits `fs.approved_by_management` at rebase; note_ref stays open. |
| A-06-T39 | Lineage through C4 and agent answers staying suggestions need the completion slice. |
| N-04-T22 | The staging Whitley journey. |
| N-04-T23 | No time-skipping harness; pure functions and replay stand in. |
| N-04-T26, T-03-T17, A-05-T50, A-05-T51 | Fixture project only. Staging and Tier C locks not measured, so nothing is locked. |
| P-11-T29 | Nightly real-Textract half. |
| P-11-T30 | Masks on OCR pages, offshore refusal and walls need the integration set. |
| I-01-T23 | Methodology and wall sources, tax export gates, inbound-mail rows. |
| Q-03-T195 | 13 workflows without a recorder, named in `test_q03t195_history_preflight.py`. |
| ADR-232 to 235, P-14, P-29, P-43 | Proposed, not accepted: Ayush accepts. P-16, P-25, P-42 undrafted. |

## Quality lanes
| Row | How it stands |
|---|---|
| Q-03-T192, Q-03-T198, Q-03-T199 | Results land in the S29 end pass or wait on staging. |
| Q-03-T193, Q-03-T194 | Deferred (DEC-1389). |
| Q-03-T196, Q-03-T197 | Staging drills. |
| Q-03-T200 | Part 1 recorded in `S29-adr078-lane.md`; open rows named there. |

## Not code
| Row | What holds it |
|---|---|
| Q-04-T104 to Q-04-T109 | Pilot and rollout work: no live firm (DEC-1391). |
| F-09-T209 to F-09-T215 | Programme, partners and spend: human work. |
