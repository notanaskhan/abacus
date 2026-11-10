# NOT-01 · Notices index · intake sheet

| Field | Value |
|---|---|
| Route and params | `/notices` · `?agency=` `?type=` `?assignee=` `?respond_by=7\|30` `?tile=` `?q=` · `?ov=intake:<intakeId>` (O3 sheet) |
| Template and host frame | T1 IndexList (F-05-T28) + O3 intake SheetModal 500 (F-05-T20) · `Wave 1 - Workbench & Ops.dc.html#not01` |
| Surface | firm (never a client surface, INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/NOT-01 Notices index - intake sheet/` (README.md, spec.md; no revision.md) |
| Epic and tasks | N-04 · stubs T02 (`docs/contracts/notices.md`) · a, e, f, g T05 · b, c, d intake sheet T09 · core T06 · intake T07 · live swap T22 · E2E and parity T26 |
| Manifest status | live (N-04-T22); contract final at N-04-T27 (2026-11-07): changes go through a new contract version |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | kevin-osei | Mon Sep 14, 2026, 9:24 AM CT | E0 | Nine open notices by deadline risk; N4 Sep 21 red "7 days"; N1 amber 9 days with row hover; tiles 2 New · 3 Analyzing · 2 Response drafted · 2 Awaiting IRS; type tile 3 CP2000 · 2 CP14 · 1 CP501 · 3 State; "9 open · 1 due within 7 days · 1 blocked (no authorization)" | fixture (T05) |
| b | grace-holloway | Thu Sep 10, 2026, 2:16 PM | Sep 10 | Santos CP14 photo, eight fields at 96–99% with confidence pills, matched by name and SSN to TY2024 1040 · Accepted; red-tint "No Form 8821 or 2848 on file" and "Draft Form 2848…"; Assign with Notify Daniel Reyes on | fixture (T09) |
| c | kevin-osei | 9:24 AM | E0 | Intake `extracting`: "Reading 2 pages…" skeleton; Create notice disabled | fixture (T09) |
| d | kevin-osei | 9:24 AM | E0 | Respond by `low_confidence`: amber "71% · date partly obscured", editable, helper "Check page 1, top right" | fixture (T09) |
| e | kevin-osei | 9:24 AM | E0 | `?tile=new`: N5 and N9; Clear | fixture (T05) |
| f | kevin-osei | 9:24 AM | empty | No visible notices: "No open notices." | fixture (T05) |
| g | kevin-osei | 9:24 AM | — | Loading: skeleton rows | fixture (T05) |
| composed | as a | — | — | Possible duplicate ("Looks like N2 · same notice": Attach / Create anyway); Manual entry (no confidence pills, page thumbnails); No client matched (picker); not allowed (C-20; the flag-off state retired with `notices.workspace`, DEC-2602); error | composed (DEC-32) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/notices` | `ListPage[NoticeRowOut]` | `notice.read` | Row click opens NOT-02 |
| read | `GET /v1/notices/summary` | `NoticesSummaryOut` | `notice.read` | Tallies are visible rows only (DEC-43) |
| write | `POST /v1/notice-intakes` | `IntakeOut` (202) | `notice_intake.create` | preparer and above, client service |
| read | `GET /v1/notice-intakes/{id}` | `IntakeOut` | `notice_intake.read` | — |
| write | `PUT /v1/notice-intakes/{id}` | `IntakeOut` | `notice_intake.update` | — |
| write | `POST /v1/notice-intakes/{id}/create` · `/attach` · `/discard` | `CreatedNoticeOut` · `IntakeOut` | `notice_intake.confirm` | 409 `low_confidence_unconfirmed`, `duplicate_unresolved`, `no_client` |

## Status
`notice` (tiles by QN-6: New = received; Analyzing = classified + analyzing; Response drafted = response_drafted + approved; Awaiting IRS = sent + awaiting_irs; escalated rows count as open and have no tile), `notice_intake`.

## Copy
Verbatim from spec.md: the filter chips "Agency", "Notice", "Assignee", "Respond by"; "Search notices"; "+ Add notice"; the table headers; "Add notice", "Create notice", "Extracted by Accrued Agent", "Match", "Authorization", "Assign", "Draft Form 2848…", "No open notices.", "Notices uploaded by clients, forwarded to the Inbox or scanned in the mailroom appear here."

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Row | NOT-02 | live with T14 |
| Draft Form 2848… | SIG-02 (and the SIG-01 To send row) | live (N-02) |
| Agent chip | WB-06 | planned (W-03), hidden in production |
| Inbound | SHL-01 nav "Notices", HOME-01 tile, INB-02, POR-03 "Upload something else", BND-03 Q8, CLI-05 | per the manifest |

## Deviations
1. The agent chip reads "Notice Intake & Response Drafter · on arrival": the "daily 7:00 AM CT" sweep needs agent schedules (ADR P-50, W-03); its WB-06 target is a planned link.
2. The chip shows the firm's agent stage (Off · Shadow · Live) instead of a fixed label.
3. Extraction is by code (P-11 box maps) for mapped IRS notices; the agent extracts only notice types without a map.
4. The nine states map onto the four designed tiles as above (QN-6, inferred).
5. b renders Thu Sep 10, 2:16 PM (the state description and P-11), not the README's Mon Sep 14 (DF-34).

## Acceptance
- NOT-01 acceptance: the nine rows equal blueprint §9.7; tiles 2 + 3 + 2 + 2 = 9 and types 3 + 2 + 1 + 3 = 9, agreeing with HOME-01's "9 Notices open · 2 New".
- NOT-01 acceptance: only N4 (7 days) is red; N1 (9 days) is amber.
- NOT-01 acceptance: every extracted field shows its confidence; Santos is visibly blocked by a missing authorization and the fix routes to SIG-02.
- NOT-01 acceptance: "Awaiting IRS" never appears on a state-agency row (N8 reads "Awaiting agency").

## Figures
N1 $686.40 + $66.61 interest; N2 $4,210.00; N3 $1,980.00 · disagreed; N4 $3,412.18; N5 $1,106.00; N6 $2,240.00; N7 $640.00; N8 $5,880.00; N9 $918.00. Respond-by days from the demo clock (Mon Sep 14, 2026).
