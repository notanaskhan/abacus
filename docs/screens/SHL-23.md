# SHL-23 · Today brief panel

| Field | Value |
|---|---|
| Route and params | Docked in Home as HOME-05 (`/home?today=open`, I-02-T17); a left drawer over any firm route, `?ov=today` (from the bell and "Open Today ›"); `?ov=today:history:<briefId>` (a read-only past brief) |
| Template and host frame | Pane 470 (docked) or a left drawer x10–480, y10–850, radius 14, `--e-modal`, **no scrim** · `Wave 0 - Shell.dc.html#shl23` |
| Surface | firm, every role, role-shaped (never a client surface, INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-23 Today brief panel/` (README.md, spec.md; no revision.md; DF-25 binds) |
| Epic and tasks | I-02 · SPEC-654 · contract `docs/contracts/today.md` (T03) · read model T10 · dispatch T13 · questions T14 · panel T15 · drill-in, assign, history and ask UI T16 · HOME-05 docking T17 · journeys and parity T21 |
| Manifest status | planned (I-02-T15 builds it behind `today_brief.enabled`) |

## States
"Prod" is the live API on staging; "fixture" waits for a later epic or decision. Panels are cropped
`SHL-23b-1` … `SHL-23b-7` from the state board for parity.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| full | daniel-reyes | Mon Sep 14, 2026, 9:24 AM CT | E0 | HOME-01 for Daniel with Today as the left drawer (`?ov=today`) | prod (T15) |
| 1 | daniel-reyes | 9:24 AM | E0 | Default: cells 3 Decisions · 6 Sign-offs · 2 Approvals & sends · 0 Overdue (= HOME-01's 11); the code fact paragraph "9 of your 11 items are due tomorrow, Sep 15; 8 of them are Ridgeline. …"; Needs you first §754, Capital Accounts, Final approval; groups High risk 1, Late 0, Due tomorrow 9, Ready for sign-off 4 | prod (counts, paragraph and rows code; why lines model) |
| 2 | daniel-reyes | 9:24 AM | E0 | Drill-in "Ridgeline K-1 release": Capital Accounts Blocked (M-2 off 6,200), Basis Blocked on decision (Pell Street II off 28,595), Waiting downstream Feld and Shah 1040s; Assign open items (Samuel Ito, due today; Basis "Reserved to you — not assignable"); title and to-do wording per HOME-05 b (DF-25) | prod (T16) |
| 3 | daniel-reyes | 9:26 AM | E0 | Ask follow-up "What happens if Samuel doesn't approve the M-2 fix today?" with three citation chips | prod from S43 via `workbench.assistant` (T14); "Save to saved prompts" hidden until W-03 |
| 4 | margaret-okonkwo | Mon Sep 14, 9:24 AM | E0 | Following HOME-05 d (DF-25): 2 Decisions · 0 Sign-offs · 2 Signatures · 0 Overdue; Needs you first Northwind and Granite Peak materiality, E14 and E11 countersignatures; Needs attention 2 (3 in the fixture until A-08's flux item) | prod |
| 5 | margaret-okonkwo | Tue Dec 1, 2026, 8:30 AM | Dec 1 | "Late · 1": Pruett & Lang interim memo, 1 day late; Draft follow-up opens AUD-35 d | fixture until A-09 registers `component_deliverable.late` (J20 step 8 `test.fixme`) |
| 6 | daniel-reyes | 9:24 AM | quiet | Quiet day: all cells 0 in ink-4; "Nothing needs you first." / "I'll add items here as decisions, sign-offs and deadlines reach you." | prod |
| 7 | daniel-reyes | 9:24 AM | E0 | Building: "Building your brief from 11 items, 4 deadlines and 3 runs…" with skeleton rows | prod (T13, T15) |
| composed | as 1 | — | — | DF-04 "AI isn't available for real client data yet" and "Agents are off for this taxpayer — §7216 consent isn't on file" (per-card fallback; counts and rows stay, they are code); metadata-only viewer; walls (absent, never counted); flag off (no panel, no link, `/v1/me/today*` 404); History list and a read-only past brief (C-20 grammar, RK-62); per-card "summary unavailable"; a four-plus-cell row that wraps | composed (recorded here) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/me/today?date=` | `TodayVM` | `briefing.read` | every firm role, own brief only; 404 flag off |
| write | `POST /v1/me/today/builds` | `TodayBuildAcceptedOut` (202) | `briefing.rebuild` | three forced rebuilds per viewer per day (429 `rebuild_limit`) |
| read | `GET /v1/me/today/work-items/{work_item_id}` | `DrillVM` | `briefing.read` + `visible(work_item)` | 404 walled or not the viewer's |
| read | `GET /v1/me/today/history` · `/history/{brief_id}` | `ListPage[HistoryRow]` · `TodayVM` | `briefing.read` | own rows, 90 days |
| write | `POST /v1/me/today/questions` | `TodayQuestionAcceptedOut` (202) | `briefing.ask` | 409 `capability_unavailable {reason}`; hidden while `workbench.enabled` is off |

## Status
`daily_briefing` (Building · Ready · Unverified · Failed · Unavailable), `attention_item` pills (Letter unsigned · Missing support · {n} requests open), and the C13 gate words (`human_gate`). I-02-T03.

## Copy
Verbatim from spec.md, with keys in `screens/SHL-23/copy.ts` (T15): "Today", "Good morning, {first name}", the cell labels (C13 band words), "Needs you first", group labels "High risk", "Late", "Due tomorrow", "Ready for sign-off", "Needs attention", "Nothing is late.", "Nothing needs you first.", "I'll add items here as decisions, sign-offs and deadlines reach you.", "Ask about your day…", "Assign open items", "Open", "Reserved to you — not assignable", "Waiting downstream", "Building your brief from {n} items, {d} deadlines and {r} runs…", "Brief built {time} from your queue, deadlines and runs · every line links to its source", "Rebuild brief", "History".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Count cells | HOME-02 `?band=<kind>` (`?due=overdue`) | live (I-01) |
| Needs you first: decision | HOME-02 with SHL-11 inline | live |
| Needs you first: sign-off row | HOME-02 item | live |
| Final approval | SHL-12 | live (P-04) |
| Ready for sign-off | HOME-02 bulk selection | live |
| Assign open items | SHL-17 (`?ov=todos:new:<nonce>`) | live (P-05) |
| Late: Draft follow-up | AUD-35 d | planned (A-09) |
| Card links | AUD-06, TAX-05, POR-23 | per the manifest |
| Load saved prompt | WB-12 | planned (W-03), hidden |
| Inbound | HOME-01 "Open Today ›", HOME-05, SHL-01 bell | per the manifest |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| — | C | 0.20 / 3 % | full and panels 1–7 (`SHL-23b-1` … `SHL-23b-7`) report-only from I-02-T21; live dot and spinners masked; listed when the screen is built |
| — | D | exact | Pane 470, header 46, composer 38, drawer x10–480 radius 14 |

## Deviations
1. **The fact paragraph is code** (Q1, DEC-4608): HOME-05 a/d's model-voiced lead is replaced by code sentences over registered facts; per-engagement why lines and the drill-in summary stay model prose.
2. **Late (5) is a fixture** until A-09's Late provider (S45–S50).
3. **Saved prompts** ("Load saved prompt", "Save to saved prompts") are hidden until W-03 (DF-32).
4. **HOME-05 b's composer path** ("Show me the detail on the high-risk item" → "Gathering details…") is not built: the card click opens the drill-in.
5. **"Brief settings…"** is not built (I-02 §2.3).
6. Margaret's "Needs attention" reads 2 until A-08 registers the flux item (3 in the fixture).

## Acceptance
- SPEC-654 §3.1 to §3.10 and the invariants (§3.11), I-COUNT first: every count equals HOME-01 and HOME-02 and never comes from model output.
