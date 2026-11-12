# HOME-05 · Home with Today brief

| Field | Value |
|---|---|
| Route and params | `/home?brief=1` with the brief docked (collapsed is HOME-01 exactly; I-02 §3.9) |
| Template and host frame | T11 (HOME-01) + SHL-23 docked: pane 470 at x12–482, y98–848; right region 896 (tiles 88×99 ×4 at gap 6, Audits 330, Closes 90, Notices 84; queue 506; right column 380) · `Wave 5` canvas `#home05` |
| Surface | firm (INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/HOME-05 Home with Today brief/` (README.md, spec.md; no revision.md; DF-25 binds: HOME-05 d is canonical for Margaret; HOME-05 b's to-do reads "Approve the M-2 fix — Ridgeline Capital Accounts", due Sep 15) |
| Epic and tasks | I-02 · SPEC-654 · contract T03 · read model T10 · docking and linked highlight T17 · journeys and parity T21 |
| Manifest status | planned (I-02-T17 builds it behind `today_brief.enabled`) |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | daniel-reyes | Mon Sep 14, 2026, 9:24 AM CT | E0 | Brief open: "11 items across 4 engagements"; 3 · 6 · 2 · 0; Needs you first 3; the right region HOME-01 string for string (tiles 17 / 15 / 11 / 7, Audits 27, Closes 11 of 22, Notices 9 · 2 New, Waiting on you 11) | prod (one deviation: the code fact paragraph replaces the model lead, Q1) |
| b | daniel-reyes | 9:24 AM | E0 | Drill-in Ridgeline, HOME-01 Sign-off rows 7 and 8 lit; to-do "Approve the M-2 fix — Ridgeline Capital Accounts", due Sep 15 (DF-25) | prod (the composer path is not built; the card click opens the drill-in) |
| c | daniel-reyes | 9:24 AM | E0 | Collapsed: HOME-01 exactly plus "Open Today ›" after the date | prod |
| d | margaret-okonkwo | 9:24 AM | E0 | "4 items across 3 engagements"; 2 Decisions · 0 Sign-offs · 2 Signatures · 0 Overdue; Needs attention 2 (3 in the fixture until A-08) | prod |
| e | daniel-reyes | 9:24 AM | E0 | Building on the first open of the day: "Building your brief… reading your queue, deadlines and runs" with skeletons; the right region renders normally | prod (T13) |
| f | daniel-reyes | 9:24 AM | E0 | Flag off: Home is HOME-01, no toggle, no link (prod); one card per engagement briefing (Ridgeline 2025 Form 1065 · Harborview Form 8879-PE · Whitley CP2000 · Thornbury acceptance) as the `by_engagement` layout | prod (flag off); fixture (`by_engagement`, the Q1 fallback) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/me/today?date=` | `TodayVM` | `briefing.read` | own brief only |
| read | `GET /v1/home` | `HomeOut` (I-01) | `home.read` | the right region, unchanged |
| read | `GET /v1/human-gates/counts` | C13 | `human_gate.read` | the one count source (I-COUNT) |
| write | `POST /v1/me/today/builds` | 202 | `briefing.rebuild` | first open and Rebuild brief |

## Status
`daily_briefing`, `attention_item`, the C13 gate words; the right region's words are HOME-01's.

## Copy
SHL-23's keys plus HOME-05's: "{n} items across {m} engagements", "Open Today ›", "Building your brief… reading your queue, deadlines and runs".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Brief rows and cards | HOME-02, SHL-17, TXP-01, TAX-02, AUD-02, AUD-13, ENG-02 | per the manifest |
| Linked highlight | the matching HOME-01 rows (Needs-you-first 1 ↔ Decision 1; 2 ↔ Sign-off row 7; 3 ↔ Approval row 10) | T17 |
| Inbound | HOME-01 "Open Today ›" | live (I-01), behind the flag |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| — | C | 0.20 / 3 % | a–f report-only from I-02-T21; listed when the screen is built |
| — | D | exact | Pane 470 docked at x12–482; the right region's HOME-01 geometry at 896 wide |

## Deviations
1. The code fact paragraph replaces HOME-05 a/d's model-voiced lead (Q1).
2. HOME-05 b's composer path is not built; the card click opens the drill-in.
3. HOME-05 f's per-engagement layout is the `by_engagement` fallback (fixture).
4. Margaret's Needs attention reads 2 until A-08.
5. "Signatures" (d) follows DF-25's taxonomy; if the band is "Approvals & sends", the label is this deviation (Q5).

## Acceptance
- The right region matches HOME-01 string for string and count for count; the brief agrees with the lists (Decisions 3 · Sign-offs 6 · Approvals & sends 2 · Overdue 0; Due tomorrow 9; Ready for sign-off 4); Margaret's 2 + 0 + 2 = 4 on both sides; materiality figures foot (1.0% × 16,812,400 = 168,100; 1.5% = 252,200; 5% × 3,100,000 = 155,000, PM 116,250, CT 7,750; 11,420,000 ÷ 9,180,000 − 1 = 24.4 %).
