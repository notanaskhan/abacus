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

## S29 leftovers round (2026-11-07, TASK-6000 to TASK-6013, DEC-2600 to DEC-2610)

Built as a held stack off main 05881ec69 (#1382 to #1395), one PR per row, tests targeted to what
each PR touched (Ayush: no comprehensive runs this round).

| Row | Now | Still open, and why |
|---|---|---|
| N-04-T25 | Real-run harness, per-mode clearance, HMAC report, cost rows, live rule (#1382) | The real direct and Bedrock runs; the CPA label review; extract cases' word layers; every real firm's opt-in |
| N-04-T27 | Contract frozen (v1 snapshot), RB-61, RB-16 R4-15, load profile, hand-offs (#1383); both flags retired (#1384, held for Dec 16) | Live firms' notices and the Dec 7 approvals (DEC-1391); pen test #2 (DEC-1389); RB-61's rehearsal |
| A-05-T49 | `ebp_audits` entitlement with the signed-memo check, ebp@1 memo drafted, flip plan (#1385) | The CPA's signature; staging soak; canary walk; flag renewals on Tue Dec 7, 2027 |
| T-03-T18 | Rollover drafts tool, 2028 holidays, RB-62, TY2027 memo, load profile (#1386); flags retired into `tax_returns` (#1387) | Drafting from published TY2026 versions; CPA and counsel review; two-person publishes; pilot-state due dates (no kind); organizers per firm |
| A-06-T32 | Golden figures from one book, scenario and fixtures (#1388) | The 26-row matrix (strict xfail, DEC-2391); AUD-15's tab badge has no fixture field |
| A-06-T39 | Lineage through C4 and suggestions tests (#1389) | none |
| Q-03-T195 | Every workflow has a replay history; gap list empty (#1390) | none |
| N-04-T23 | Time-skipping alert and follow-up tests (#1391) | none |
| P-11-T30 | Masks burned on OCR pages, offshore and walled readers refused (#1392) | none |
| I-01-T23 | Tax export gate on Home (#1393) | Methodology and wall approval sources (no engagement; the projection reads by engagement); inbound-mail rows (no event names an engagement) |
| P-11-T29 | Nightly real-Textract run, report-only (#1394) | The staging role variable; two passing nights, then blocking |
| A-06-T29 | unchanged | Send-draft needs R-02's services (S31); the FS render needs an `fs_package` firm template |
| N-04-T22 | unchanged in code | The staging run of j09 (the `staging` Playwright project already reads it) |
| N-04-T26, T-03-T17, A-05-T50, A-05-T51 | unchanged | Staging and Tier C parity locks |
| EBP-01 to EBP-04 | by design | AUD-02 cockpit canvases with no path of their own (the links rule), not a gap |
