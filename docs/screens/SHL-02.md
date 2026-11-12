# SHL-02 · Command palette "Go…"

| Field | Value |
|---|---|
| Route and params | No route: local state in the firm shell (chapter 04 §2.4, never `?ov=`). Opened by the SHL-01 "Go…" pill (`on-go`) and ⌘K / Ctrl+K on every firm screen. Gallery: `/components/screens/SHL-02?st=a…g&as=hannah-leclerc&clock=…&frame=1&static=1&contrast=reference` |
| Template and host frame | O5 Command palette (F-05-T20 `CommandPalette`) over TPL-11 Home under the .22 scrim · `Wave 0 - Shell.dc.html#shl02` |
| Surface | firm (never the portal: the portal bundle carries no palette code, INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-02 Command palette - Go/` (README.md, spec.md, revision.md R2; revision wins over spec) |
| Epic and tasks | P-02 · ADR-241 (P-33) T15 · glossary T04 · contract T03 · C15 stub T01 · migration T05 · consumer suite T02 · indexer T06 · builders T07 · query T08 · AC suite T09 · palette T10 · fixtures T11 · journeys T12 · load T13 · docs T14 |
| Manifest status | planned (`routes/manifest/shl.ts`; `entry: true`, no designed link targets it). Fixture at P-02-T10/T11, live behind `search.palette` after P-02-T08 |
| Flags | `search.palette` (routes, ⌘K and the mount) · `search.agent_mode` (the `>` prefix; flips only after W-02's WB-01 new-session target) |

## States
Clock is the demo clock (DEC-27), CT. Persona slugs follow F-04. The spec renders a–e on "Mon 14
Sep 2026 9:24 AM" and the README's capture table says "Mon Sep 28, 9:24 AM"; the R2 revision
("Rendered Mon 14 Sep 2026, 9:24 AM CT (frames A–E); new frames F and G Mon 28 Sep 2026, 9:10 AM
CT") wins (P-02 OQ-6): **a–e run on E0, Mon Sep 14, 2026 9:24 AM CT; f–g on Mon Sep 28, 2026
9:10 AM CT.** The Home background behind the scrim is masked in parity.

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026 9:24 AM (E0) | `q = "feld"`: Clients Jonah & Claire Feld · Household · Brooklyn, NY · TY2025 Form 1040; Returns 2025 Form 1040 "In review · Manager" (selected), 2025 Form 1065 Ridgeline Property Partners, LP · "Jonah Feld, limited partner 25%" · "In review · Partner"; Binders 2025 Binder · 2 open requests · "Published"; Files Claire_Feld_2025_W2_MercerHill.pdf · "Approved"; Inbox Re: 2025 tax documents · Claire Feld · 9:12 AM · "Waiting"; Actions "Run an agent on Jonah & Claire Feld…", "New engagement for Jonah & Claire Feld…", "Message Claire Feld…", "New to-do on Jonah & Claire Feld…" (R2 item 3) | fixture-only (P-02-T11; live after P-02-T08) |
| b | hannah-leclerc | Mon Sep 14, 2026 9:24 AM (E0) | `q = ""`: Recent (5) Northwind Robotics 401(k) Plan · PY2025 EBP Audit "Processing"; 2025 Form 1065 · Ridgeline "In review · Partner"; Copperleaf Coffee Roasters, Inc. · Close · 2026-08 "In progress" + "4 days past due"; Session · TY2025 season progress by office "Needs your answer"; Agent · Season Progress Reporter "Next run Mon, Sep 21 · 9:00 AM CT". Create (7, R2 order): New client…, New engagement…, New Workbench session…, Upload to Inbox…, New to-do…, Load saved prompt…, Open board | fixture-only (P-02-T11; live recents after P-02-T08; planned targets hidden in production) |
| c | hannah-leclerc | Mon Sep 14, 2026 9:24 AM (E0) | `q = ">"` with `search.agent_mode` on: "Run an agent": Return Review Packet, K-1 Reconciliation Workpaper, Missing Document Chaser, Season Progress Reporter, EBP Audit Workpapers, Bank Reconciliation, each with its category tag and "Installed" | fixture-only (live after W-02 registers `agent_definition`; `>` is literal text while the flag is off) |
| d | hannah-leclerc | Mon Sep 14, 2026 9:24 AM (E0) | `q = "pellstret"`: EmptyState "No matches for 'pellstret'." / "Try a client, form, period or file name." and the suggestion "Did you mean Pell Street II LLC · partner in Ridgeline Property Partners, LP?", computed only from documents Hannah may open | fixture-only (P-02-T11; live after P-02-T08) |
| e | hannah-leclerc | Mon Sep 14, 2026 9:24 AM (E0) | `q = "feld"` with a scenario-local wall on two Feld documents: renders exactly a without the walled rows. **No footer note, lock glyph or count** (DEC-43, DF-14; see Deviations) | fixture-only (P-02-T11 proves no wall count renders) |
| f | hannah-leclerc | Mon Sep 28, 2026 9:10 AM | `q = "granite"`: Clients Granite Peak Outdoor Supply, Inc. · C corp · Denver; Audits FY2026 Financial Statement Audit "Fieldwork"; To-dos "Re-request 2 SURL files" · Cole Hart · BH-FS-430 · due "Sep 28" (selected); Actions "Open board · Granite Peak FY2026 audit", "New to-do on Granite Peak Outdoor Supply…" | fixture-only (P-02-T11; the to-do row live after P-05's builder, P-02-T07) |
| g | hannah-leclerc | Mon Sep 28, 2026 9:10 AM | `q = "explain"`: Saved prompts "Explain a year-over-year change with evidence" · Audit · Tag Firm · used 41 times; "Draft a client question for an unexplained variance" · Audit · used 33 times; Actions "Load saved prompt…" | deferred (W-03 registers `saved_prompt`, S63–S69; fixture-only in the gallery) |
| loading, error, off, client | hannah-leclerc; meera-shah | as above | never-resolving handler (skeleton rows); 503 `search_unavailable` ("Search isn't available right now. Try again."); `search.palette` off: no ⌘K listener, no mount, routes answer 403 `flag_off`; a client principal: 403 `forbidden`, no palette in the portal | fixture-only (P-02-T11) |

Parity tier: Tier C (threshold 0.20, at most 3%) on a–g with the scrim background, caret and
type-tile glyphs masked; Tier D blocking on the 640 card at top 88, the 46 search row, the 40 rows,
the 28 group labels and the 36 footer.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–g | C | measured by the parity run (gallery `SHL-02`, P-02-T11) | threshold 0.20, at most 3%; background masked |
| card | D | — | width 640, top 88, radius 14, search row 46, rows 40, group labels 28, footer 36 (blocking) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `POST /v1/search` | `SearchQueryIn` `{q, types?, limit_per_group, context?}` → `SearchResultsOut` `{groups, suggestion, total_visible}`; no `hidden_by_wall` field | `search.read` | firm roles; client, agent, system and `platform_support_content` refused (403 `forbidden`); 403 `flag_off`, 422 `q_invalid`, 429 `rate_limited`, 503 `search_unavailable` |
| read | `GET /v1/search/recents?limit=5` | `SearchRecentsOut` `{items}` | `search.read` | own recents only, re-filtered by `visible()` |
| write | `POST /v1/search/recents` | `SearchRecentIn` `{object_type, object_id}` → 204 | `search.recent.record` | 404 `not_found` when the viewer may not read the object |

Every endpoint is in `docs/contracts/c15-search.md` (P-02-T01); 501 until P-02-T08. Search text
travels only in the POST body (ADR-241 decision 7).

## Status
Result pills read the owning object's C2 status words through `status.ts` (`{code, context}`):
`tax_return` ("In review · Manager", "In review · Partner"), `request_list` ("Published"),
`evidence_item` ("Approved"), `inbox_thread` ("Waiting"), `assurance` ("Fieldwork",
"Processing"), `close` ("In progress"), `workbench_session` ("Needs your answer"); to-do due chips
use C-30 (Overdue derived at read time, never stored).

## Groups
Canonical order (P-02 OQ-3; S01 §i #13): **Clients · Returns · Audits · Closes · Binders · Files ·
Inbox · Sessions · To-dos · Saved prompts · Actions**; with nothing typed, **Recent** and
**Create**; in `>` mode, **Run an agent**. Group labels are Title Case, never uppercase. A group
with no rows does not render.

## Copy
Keys live in `apps/web/src/screens/SHL-02/copy.ts` with P-02-T10. Placeholder "Go…"; footer
"↑↓ Navigate · ↵ Open · ⌘↵ Open in new tab · esc Close" (macOS) and "↑↓ Navigate · ↵ Open ·
Ctrl+↵ Open in new tab · esc Close" (other platforms; P-02 OQ-4, parity uses the macOS variant);
"accrued·" wordmark; empty state "No matches for '‹q›'." / "Try a client, form, period or file
name."; suggestion "Did you mean ‹title› · ‹context›?"; live region "‹n› results"; error "Search
isn't available right now. Try again.". "To-do" hyphenated, never "task"; "saved prompt", never a
bare "prompt"; "Session" means a Workbench session. The palette is "Go…" in copy, never "Search…"
or "Command palette" (DEC-4502).

## Deviations
- **e (DEC-43, DF-14).** The handoff draws SHL-02e as "Frame A plus a footer note … Lock 12 + '2
  results hidden by an ethical wall'", and the R2 checklist says "the ethical-wall count in Frame E
  still shows". DEC-43 chose 404 semantics everywhere and DF-14 removed that copy: the product
  renders e exactly as a without the walled rows, with no note, glyph or count, for every role
  admins included. The parity run masks the footer-left region of e only.
- **Clock (OQ-6).** The README's capture table lists every frame on Mon Sep 28; the revision wins:
  a–e on E0 Mon Sep 14 9:24 AM, f–g on Mon Sep 28 9:10 AM.
- SHL-02a to SHL-02e have no matching letter in the spec's STATES list (added during the build);
  the spec's FRAME A–E are those letters.
- The canvas mounts the Shell Kit toolbar with `on-go` reopening the board; the product mounts
  `CommandPaletteData` once in `shell/firm/`.
- Frame A's Actions gain "New to-do on Jonah & Claire Feld…" (R2 item 3); f and g add To-dos and
  Saved prompts between Inbox and Actions (R2 item 1).

## Links
The handoff link graph holds no SHL-02 links ("Links: None found"); the spec's INTERACTIONS name
these targets, wired with `to.<ID>()` / `ov.<ID>()` by P-02-T10 as each becomes fixture or live.

| From | To (manifest builder) | Planned or live |
|---|---|---|
| Clients row | CLI-02 | planned (P-07) |
| Returns row (1040, 1041) | TAX-02 | fixture (T-04) |
| Returns row (1065) | TXP-00 | planned (T-05-T28 dispatches a 1065 to the Agent tab; until then the row opens CLI-02) |
| Audits row | AUD-02 | planned (A-01) |
| Closes row | CLS-02 | planned (C-01) |
| Binders row | BND-02 | planned (P-06) |
| Files row | FIL-01 | live (document drawer `?ov=viewer:…`) |
| Inbox row | INB-01 | live (`/inbox/$threadId`) |
| Sessions row, Saved prompt row, "New Workbench session…", agent row in `>` mode | WB-01 | planned (W-02; nothing is sent, INV-1) |
| Agent row in Recent | WB-06 | planned (W-03) |
| To-dos row, "New to-do…" | SHL-17 | planned (P-05: `?ov=todos:<id>`, `?ov=todos:new`) |
| "New engagement…" | ENG-03 | planned (P-07) |
| "New client…" | CLI-06 | planned (later wave) |
| "Open board" | ENG-10 | planned (K-04; or the TAX-01 / CLS-01 board view) |

## AVOID
Gradients in product UI, emoji, saturated blue highlights, heavy shadows, invented colours, lorem
ipsum, uppercase group labels, results the viewer has no right to see, any count or note of hidden
results (DEC-43), "task" for a to-do, a bare "prompt", the agent approving or running anything from
the palette (INV-1), Approve, Sign off, Release, Send, Post or Decide on any palette row.

## Acceptance
- Seven artboard states (a–g) are listed, each marked live, fixture-only or deferred with its
  owning task or epic.
- The e deviation (DEC-43, DF-14) and the clock decision (OQ-6) are recorded.
- The Links table names every outbound target, so the link-contract test knows each one.
