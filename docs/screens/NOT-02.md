# NOT-02 · Notice workspace · CP2000 · TY2024 · Marcus & Dana Whitley

| Field | Value |
|---|---|
| Route and params | `/notices/$noticeId` · `?tab=analysis\|response\|activity` · `?segment=notice_vs_return\|information_returns\|transcript` · `?ov=decision:<cardId>` (SHL-11 inline) |
| Template and host frame | T3 EvidenceTriad, Review preset 452 · 452 · 452 (F-05-T53) with tabs Analysis · Response · Activity |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/NOT-02 Notice workspace - CP2000 - TY2024 - Marcus and Dana Whitley/` |
| Epic and tasks | N-04 · stubs T02 · screen T14 · analysis T11 · agent T19 · live swap T22 (e, f) · E2E T26 |
| Manifest status | live (N-04-T22); contract final at N-04-T27 (2026-11-07): changes go through a new contract version |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | kevin-osei | Mon Sep 14, 2026, 9:24 AM | E0 | Analysis ready: +3,120.00 from two 1099-INTs issued after filing; 22% × 3,120 = 686.40; total 753.01; `notice_position` card reserved to Daniel Reyes | fixture (T14) |
| b | kevin-osei | 8:58 AM | 8:58 | Analysis `running`: spinners in the IRS column; "Comparing 6 information returns with the 2024 return…"; skeleton Proposed action | fixture (T14) |
| c | daniel-reyes | 9:51 AM | 9:51 | Decided: read-only "Agree · decided by Daniel Reyes"; Draft response | fixture (T14) |
| d | kevin-osei | 9:24 AM | E0 | Both 1099-INTs stacked in SHL-08 "1 / 2"; payers lit in all three panes | fixture (T14) |
| a2 | kevin-osei | 9:24 AM | E0 | Activity: Received Aug 24 · Uploaded by Dana via portal · Classified · Analyzed · Decision requested | fixture (T14) |
| e | kevin-osei | 9:24 AM | E0 | Collins CP2000 (N3): broker reported no basis; 13,200.00 basis on Form 8949, gain zero; Disagree; Awaiting IRS | live swap (T22) |
| f | kevin-osei | 9:24 AM | E0 | Santos CP14 (N5): authorization "None on file"; banner "Form 2848 to send (SIG-01)" | live swap (T22) |
| composed | as a | — | — | New with Start; Return as filed missing (cited entry); AgentBlock Off / Shadow ("Agent analysis is off for this firm") and Refused ("Agents can't read this taxpayer's return information — §7216 consents missing"); Position changed after drafting; error | composed (DEC-32) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/notices/{id}` | `NoticeOut` | `notice.read` | — |
| read | `GET /v1/notices/{id}/analysis` | `AnalysisOut` | `notice.read` | the browser does no arithmetic |
| write | `POST /v1/notices/{id}:start` | `NoticeOut` | `notice.start` | preparer function and above |
| write | `PUT /v1/notices/{id}/return-as-filed` · `/proposed-items` | `AnalysisRunOut` | `notice.record_as_filed` | every line cited |
| write | `POST /v1/notices/{id}/analysis/run` | `AnalysisRunOut` | `notice.analyze` | — |
| write | `POST /v1/notices/{id}/decision-requests` | `DecisionRequestOut` | `notice.request_decision` | — |
| write | `POST /v1/decision-cards/{id}/decide` (C3) | decision | `decision.decide` | the notice's signer only; the agent never |
| write | `POST /v1/notices/{id}/notes` | `NoticeNoteOut` | `notice.note` | insert-only |
| read | `GET /v1/notices/{id}/activity` | `ListPage[ActivityItemOut]` | `notice.read` | — |
| write | `POST /v1/notices/{id}/response` | `ResponseOut` | `notice_response.draft` | opens NOT-03 |

## Status
`notice`, `notice_analysis`; the decision card's words are SHL-11's.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Draft response | NOT-03 | live with T20 |
| Citation chips, stacked sources | SHL-07, SHL-08 | live |
| Authorization card · Form 2848 to send | SIG-01 / SIG-02 | live (N-02) |
| Transcript segment | CLI-05 data (T-01) | live (deviation 1) |
| Assistant chip | TAX-08-style assistant (W-02) | planned, hidden in production |

## Deviations
1. The "Transcript" segment, designed as "CLI-05 later", is live: T-01 shipped transcripts and comparisons in S21.
2. The subbar "Assistant" chip is a planned link (W-02), hidden in production.
3. Arithmetic is code; the bracket check verifies the IRS figure and never replaces it (QN-3); interest and penalty come from the notice, never recomputed.
4. "Contact-IRS actions" have no artboard; v1 builds none, and the computed `can_represent` fact drives only the banner.
5. Position is reserved to the signer; the screen serves the preparer, manager and partner.

## Acceptance
- NOT-02 acceptance: 3,120.00 difference from two 1099-INTs; 22% × 3,120 = 686.40; total 753.01 with 66.61 interest from the notice.
- NOT-02 acceptance: no agent citation renders unverified; agent text renders through `AgentText` only.
- NOT-02 acceptance: only Daniel Reyes can decide; the decision card reads SHL-11's grammar.

## Figures
Whitley (N1): 3,120.00 · 686.40 · 66.61 · 753.01 (goldens in N-04-T04). Collins (N3): 13,200.00 basis, gain zero. Santos (N5): 1,106.00.
