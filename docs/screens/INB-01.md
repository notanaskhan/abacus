# INB-01 · Inbox

| Field | Value |
|---|---|
| Route and params | `/inbox` (firm app nav item "Inbox"); `?thread=<uuid>` selects a thread, `?ov=file&message=<uuid>` opens INB-02 over it, `?ov=log-intake` opens the Log received documents sheet (DV-1). Filters in the query: `client`, `status`, `received`, `channel`, `q`, `show_ignored`, `show_filed`. Artboards: `/components/screens/INB-01?st=a…g` |
| Template and host frame | T8 Inbox master-detail (filter bar 50 · rail 392 · reading flex); the TPL-08 specimen made live · `Wave 1 - Workbench & Ops.dc.html#inb01` |
| Surface | firm (never in the portal bundle) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/INB-01 Inbox/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | N-01 · contract N-01-T05 (this file); stub T02; consumer tests T03; tables T07; intake scope T08; intake writes T09; list and fixtures T10, T11; read APIs T13; triage T18; journeys and parity T23–T28 |
| Spec and ADRs | SPEC-380 (Stories 1–3, 6); ADR-210; DEC-20, DEC-23, DEC-43, DEC-75 |
| Flags | `inbox.firm_intake` (all inbox routes); `matching.firm_intake` (agent proposals in the note) |
| Manifest status | `live` (N-01-T23): `/inbox` behind `inbox.firm_intake`, inside the firm shell (InboxLayout without its own toolbar); `/components/screens/INB-01?st=a…g` for the artboards |

Code to come (N-01 §5.1): `apps/web/src/routes/firm/inbox.tsx`, `src/screens/INB-01/{index.tsx, scenarios.ts, copy.ts, INB-01.test.tsx}`, `src/domain/inbox/{queries.ts, InboxRail.tsx, MessageView.tsx, AgentNote.tsx, BulkBar.tsx, LogIntakeSheet.tsx}`, `src/fixtures/handlers/inbox.ts`, `src/fixtures/seed/inbox.ts`. The Atelier `InboxPanel.tsx` and `InboxAIMatch.tsx` are retired in N-01-T30, not extended.

## States

INB-01 has 7 artboards. Clock E0, Mon Sep 14, 2026, 9:24 AM CT (DEC-27); viewer Grace Holloway (Firm Admin, Intake team, DEC-701) throughout.

| Artboard | Viewer | Clock | Snapshot | Data condition that produces it | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | grace-holloway | 9:24 AM | E0 | 17 threads, Feld thread selected; Feld 1a holds Feld_1095C_2025.pdf and Feld_1095C_2024.pdf (`waiting`), the 2024 one flagged `wrong_year`; summary "23 waiting · 4 unmatched" counted from rows (2+1+3+3+2+2+2+2+1+1+4; rows 9, 13, 16, 17 unmatched) | C report; C lock before M10 | live (T10, T13) |
| b | grace-holloway | 9:24 AM | E0 | Row 9 selected: billing@soundelectricco.com matches no contact and no sender rule; one attachment `new` | C report | live; the ledger hint is fixture-only and permanent (DV-6) |
| c | grace-holloway | 9:24 AM | E0 | Row 3 (Harold Stein) selected; the suggested destination is a `notice` kind | C report | **fixture-only** until N-04 registers the `notice` destination (DV-7) |
| d | grace-holloway | 9:24 AM | E0 + INB-02 a applied | Feld_1095C_2025.pdf `filed`, Feld_1095C_2024.pdf `ignored` (reason `wrong_year`); summary "21 waiting · 4 unmatched" | C report | live (T18) |
| e | grace-holloway | 9:24 AM | E0 | Rows 2, 10, 11 checked; rows 1a, 3, 12 carry flags (`block_bulk`), row 4 is `low_confidence`; their checkboxes are disabled | C report | live (T18) |
| f | grace-holloway | 9:24 AM | E0 | Client filter Ridgeline, Received Past 30 Days → no thread | C report | live (T10) |
| g | grace-holloway | 9:24 AM | — | `GET /v1/inbox/threads` pending → 8 skeleton rows, `aria-busy` | C report | live (T10) |

Non-artboard states:

| State | Persona | Data condition | Rendering |
|---|---|---|---|
| Walled | lena-park | Walled from Ashford | No Ashford thread, attachment, count or destination; an Ashford thread id answers 404 (INV-3, DEC-43) |
| Engagement member | kevin-osei | Not on the Intake team | Only threads matched to clients he can read through scope kind `client`; no unmatched rows; summary counts his visible rows |
| Summary only | firm admin not on the Intake team | ADR-024 | Summary counts only; the rail reads "You can see counts, not messages." |
| Flag off | any | `inbox.firm_intake` off | Nav item stays; C-20's "This isn't on for ‹firm› yet." state (AC-24) |
| AI unavailable | any | matcher not cleared or the tenant's agents off | Agent note reads "Suggested from the file's name and contents" without the monogram (DV-9); DF-04 states |
| Error | any | a read fails | F-05 error ViewState in the failed pane with Retry |
| Not allowed | client, agent, system or support principal | — | 403 on `/v1/inbox/*` |

## API
| Read or write | Endpoint | Shape | Matrix action | Notes |
|---|---|---|---|---|
| read | `GET /v1/inbox/summary` | `{waiting, unmatched, by_source[]}` | `inbox.read` | Counts over visible rows only |
| read | `GET /v1/inbox/threads` | list envelope of `InboxThreadRow` | `inbox.read` | Polled every 10 s while visible (DEC-23) |
| read | `GET /v1/inbox/threads/{id}` | `InboxThreadDetail` (messages newest first; bodies only with `inbox.read_content`) | `inbox.read` | `allowed_actions` per attachment |
| write | `POST /v1/inbox/threads/{id}/match-client` | `{client_id, client_entity_id?, remember_sender, seen_version}` | `inbox.match_sender` | b: "Match client…" |
| write | `POST /v1/inbox/threads/{id}/ignore` | `{reason_code, note?}` | `inbox.triage` | b: "Ignore" |
| write | `POST /v1/inbox/intake` | multipart + `{received_via, received_at, subject, ...}` | `inbox.log_intake` | Log received documents (DV-1) |
| write | `POST /v1/inbox/attachments/bulk-file` | `{attachment_ids[], seen_proposals}` | `inbox.file` | e: "File 3 as suggested" |
| read | `GET /v1/inbox/attachments/{id}/content`, `GET /v1/inbox/messages/{id}/attachments.zip` | bytes, `no-store` | `inbox.download` | Audited; "Download All" |

Contract: `docs/contracts/firm-intake.md` (N-01-T02).

## Status
`inbox_item` codes (`docs/product/status-vocabulary.yaml`): `new` ring 16, `waiting` gold dot 16, `filed` olive check 15, `ignored` ink-4 ✕ 15 with the row muted, `held` shown as the waiting dot with sub-line "Asked the client · {date}" (DV-15), `withdrawn` muted. Thread roll-up: a ring while any attachment is `new`. `inbox_thread` `unmatched` shows the "Match client…" amber chip.

## Copy
Copy keys live in `screens/INB-01/copy.ts` and `domain/inbox/messages.ts`. Verbatim from spec.md.

| Key | String |
|---|---|
| `filters.all` | "← All Messages" |
| `filters.client` | "Client │ Select ⇕" |
| `filters.status` | "Status │ Select ⇕" |
| `filters.received` | "Received │ Past 30 Days ⇕" (amber when active) |
| `filters.channel` | "Channel │ Email ⇕"; values "Email" · "Portal upload" · "Logged by staff" (DV-2) |
| `summary` | "23 waiting · 4 unmatched" (template `{waiting} waiting · {unmatched} unmatched`) |
| `rail.source` | "@ docs@… ⌄" on the synthetic tenant's seeded source; "Firm intake ⌄" elsewhere (DV-1) |
| `rail.title` | "Inbox" |
| `rail.search` | "Search" |
| `rail.logIntake` | "Log received documents…" (menu item, DV-1) |
| `reading.file` | "File…" |
| `reading.reply` | "Reply" (hidden until N-03, DV-3) |
| `note.review` | "Review →" |
| `note.unmatched` | "No contact uses {address}." (DV-6) |
| `unmatched.match` | "Match client…" |
| `unmatched.ignore` | "Ignore" |
| `attachments.header` | "Attachments" |
| `attachments.downloadAll` | "Download All" |
| `attachment.filedTo` | "Filed to {path}" |
| `attachment.ignored` | "Ignored · {reason}" (e.g. "Ignored · wrong year") |
| `tag.wrongYear` | "{form_year} ≠ {return_year}" (e.g. "2024 ≠ 2025") |
| `bulk.selected` | "3 selected · File 3 as suggested" (template `{n} selected · File {n} as suggested`) |
| `bulk.ignore` | "Ignore…" |
| `bulk.hasFlags` | "Has flags — review in File…" |
| `bulk.lowConfidence` | "Low confidence — choose in File…" |
| `empty.title` | "No messages match these filters." |
| `empty.clear` | "Clear filters" |

## Deviations (N-01 §2.4)
DV-1 (source pill and Log received documents), DV-2 (channel values), DV-3 (Reply hidden), DV-4 ("Uploaded – needs review" unless the filer holds `evidence.accept`; d's "request now Received ✓" holds only then), DV-5 (filed thumbnails for intake-scope-only viewers render as a FileChip), DV-6 (no ledger hint), DV-7 (notice destination fixture-only), DV-9 (code-composed note), DV-15 (held display).

## Links
Inbound: SHL-01 nav "Inbox", HOME-01 `inbox_waiting` tile, SHL-04 client-upload notifications, POR-03 "Upload something else" (via intake). Outbound: INB-02 (live), SHL-08 (live), BND-02, AUD-03, TAX-03 (filed destinations, live as their screens are), NOT-02 and CLS-03 (planned), INB-03 and INB-04 (N-03, planned).

## Open gaps
- Row 4's Copperleaf receipts need C-01-T58's close-receipt destination; until S48 the row renders from fixtures and cannot be filed live (DV-7).
- The design of the Log received documents O3 sheet is in `docs/screens/INB-02.md` § Log received documents.
