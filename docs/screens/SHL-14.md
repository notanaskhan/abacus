# SHL-14 · Request composer drawer

| Field | Value |
|---|---|
| Route and params | Overlay `?ov=request:new\|<requestItemId>[:<nonce>]` over its host (BND-02 here; AUD-03 from A-01, CLS-03 from C-01), registered in chapter 04's overlay table; prefill payloads go through `overlayPayloadStore` (P-06 §5.1). No route of its own. Artboards: `/components/screens/SHL-14?st=a,b,d,e,f` |
| Template and host frame | O2 right drawer 480 + R2 tabs row 40 · `Wave 0 - Shell.dc.html#shl14` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-14 Request composer drawer/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-06 · contract P-06-T03 (TASK-404); a, b, e, f and R2 items 1–5 P-06-T13; d P-06-T24; request lifecycle P-06-T10; data P-06-T08; parity P-06-T26 |
| Manifest status | planned (`routes/manifest/shl.ts`) |

Code to come (P-06 §5.2): `src/domain/requests/{queries.ts, mutations.ts, messages.ts, ClientPreviewSheet.tsx}`, `src/screens/SHL-14/{index.tsx, scenarios.ts, copy.ts, SHL-14.test.tsx}`.

## States

6 artboards in the handoff (5 + R2 f), 5 built here. The spec and revision number the states 1–6; the README and the screenshots letter them a–f (1 = a … 6 = f).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | marcus-delaney (Marcus Delaney, Audit Senior) | Mon Sep 14, 2026, 9:41 AM CT (revision) | E0 | `?ov=request:new` on the Northwind PY2025 PBC binder: ERISA fidelity bond for Dana Kowalski; preview of what Dana sees | built · fixture (T13) |
| b | marcus-delaney | same | E0 | Existing request "Bridge letter — Keystone, Oct–Dec 2025", `requested` Sep 1, due Sep 25, delegated to Sam Ortiz (Keystone) | built · fixture (T13) |
| c | marcus-delaney | same | E0 | Sample-driven bulk: 25 requests from the EBP-04 sample (seed `0x5E2A91`) | **deferred → A-03** (S20–S23): needs the sampling engine. Recorded, not built, not missing |
| d | raj-malhotra (Raj Malhotra) | same | E0 | Copperleaf August `close_intake` binder: "Square payouts — August", `incorporation_state = pending_incorporation`, uploaded by Ben Ashby Sep 3 | built · fixture (T24; hosted from BND-02 until C-01 builds CLS-03) |
| e | marcus-delaney | same | E0 | State a with no due date | built · fixture (T13) |
| f (R2) | cole-hart (Cole Hart, Audit Staff) | Thu Sep 24, 2026, 10:58 AM CT | E0 | Granite Peak FY2026 SURL request in `draft` with `drafted_by_run_id` set and `drafted_wording_source = 'template'` | built · fixture (T13) |

R2 on every built state: tabs Details · Comments · Activity; the Draft pill on drafts; Visibility segmented Owners only · Client; Links rows Related rows and Controls; "Link from another engagement…" (hidden, DV-6). Loading: the drawer opens with F-05 skeleton rows. Error: the save error words come from `domain/requests/messages.ts`. Not-allowed: the agent principal is denied `request_item.send`; a role without `request_item.create` never sees "+ Request". Dirty guard: Escape or ✕ with changes asks "Discard changes?".

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| write | `POST /v1/engagements/{eid}/request-items` (extended) | Extended body (title, client wording, category, period, due, wave, assignee, firm owner, linked workpaper, supports); status `draft`; `binder_id` required | `request_item.create` | partner, manager, senior, staff, `client_service` (DEC-38); agent deny |
| write | `PATCH /v1/engagements/{eid}/request-items/{id}` | Edit any non-terminal request (b) | `request_item.update` | — |
| write | `POST …/request-items/{id}/send` (+ `/undo`; Idempotency-Key) | Draft → Requested; due required (422 `due_date_required`, e); scope check (409 `out_of_scope`); 409 `model_text_not_permitted` (DV-11); email after the 10 s Undo | `request_item.send` | partner, manager, senior, staff, `client_service`; agent deny; independence required |
| write | `PUT …/request-items/{id}/client-visibility` | Visibility Owners only · Client | `request_item.update` | — |
| write | `POST …/request-items/{id}/delegate {contact_id}` | Delegation row + `request_item` grant for the third party (b) | `request_item.delegate` | partner, manager, senior; agent deny |
| write | `POST …/request-items/{id}/incorporate` | Close variant "Mark incorporated" (d) | `request_item.update` | — |
| write | `POST …/evidence-versions/{vid}/decision/send-back` | "Return…" (d) | `evidence.reject` | agent deny |
| read | `GET …/request-items/{id}/client-view` (extended for drafts) | The live recipient preview, from the projection the portal uses | `request_item.read` (drafts) | never internal fields, sample parameters or materiality |
| read | `GET …/request-items/{id}/activity` | Activity tab | `activity.read` | — |
| read | `GET …/request-items/{id}/comments` (SPEC-032, existing) | Comments tab (C-29) | `comment.read` | — |

## Status
`request`: `draft` neutral-outline "Draft" pill (never client-visible) · `requested` ring "Requested {date}" · `received` "Received ✓". `request_close` (d): `pending_incorporation` amber "Pending incorporation" · `incorporated` green "Incorporated".

## Copy
Copy keys live in `screens/SHL-14/copy.ts`; strings verbatim from spec.md and revision.md.

| Key | String |
|---|---|
| `title.new` | "New request" |
| `title.close` | "Request" |
| `tabs` | "Details" · "Comments" · "Activity" |
| `pill.draft` | "Draft" |
| `card.documentRequest` | "Document request" (a, b, e, f) / "Document Request" (d) |
| `keys.request` | "Request" · "Category" · "Description" · "Period" · "Due" · "Wave" |
| `wave` | "Planning" · "Year-end" · "Sample" |
| `card.people` | "People" |
| `keys.people` | "Client assignee" · "Request from a third party" · "Firm owner" · "Visibility" · "Reminders" |
| `visibility` | "Owners only" · "Client" |
| `visibility.draftHelp` | "Becomes Client when sent" |
| `reminders.help` | "Sent from the pre-approved reminder template" |
| `thirdParty.help` | "Sam sees only this request (POR-14). Dana is copied." |
| `card.links` | "Links" |
| `keys.links` | "Linked workpaper" · "Supports" · "Related rows" · "Controls" · "Attachments" |
| `attachments.empty` | "No attachments" |
| `attachments.add` | "+ Attach" |
| `links.crossEngagement` | "Link from another engagement…" |
| `card.preview` | "Preview — what {name} sees" (a: "Preview — what Dana sees") |
| `preview.upload` | "Upload…" |
| `preview.ignore` | "Ignore" |
| `preview.due` | "Due {date}" |
| `preview.thirdPartyHeader` | "Requests from Brightwater Hale for Northwind Robotics 401(k) Plan" |
| `footer.adds` | "Adds 1 request · Source Documents will read 11 of 25 received" |
| `footer.saveDraft` | "Save draft" |
| `footer.saveSend` | "Save & send" |
| `footer.sendTo` | "Save & send to {name}" (b: "Save & send to Sam Ortiz") |
| `footer.approveSend` | "Approve & send" / "Approve & send to {name}" (f: "Approve & send to Luis Ferrante") |
| `footer.modelText` | "Edit the client wording before sending" (DV-11) |
| `validation.due` | "Add a due date to send" |
| `close.keys` | "Visible to client" · "Requested by" · "Document" · "Status" · "File" · "Type" · "Summary" · "Uploaded by" |
| `close.uploadCard` | "Uploaded Document" |
| `close.markIncorporated` | "Mark incorporated" |
| `close.return` | "Return…" |
| `toast.sent` | "Request sent to {name}" (a: "Request sent to Dana Kowalski") |
| `activity.drafted` | "Drafted by Accrued Agent in the BH-FS-430 procedure session" |
| `controls.none` | "—" |

Field values (request titles, descriptions, periods, due dates, assignees, workpapers, the client wording in each preview, the close-variant summary and file) are seed data (P-06-T08), copied from spec.md and revision.md, never from `copy.ts`. The preview's brand line is the firm's name ("Brightwater Hale") from the tenant, never "Accrued".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Link from another engagement…", a Linked row | SHL-21 ("Opens SHL-21 · link requests") | planned (K-04); hidden until K-04 grants `request_item.link_cross_engagement` (DV-6) |
| Related rows chip | SHT-01 ("Opens SHT-01 with these rows selected") | planned (F-08); renders "—" until sheets exist; f's "40 rows" is fixture-only |
| Save & send (a) | the host's new row (BND-02 here; AUD-03 "Requested Sep 14") | planned (spec-level) |
| Third-party preview (b) | POR-14 room | planned (R-01; spec-level) |
| Mark incorporated (d) | logs to CLS-03 | planned (C-01; spec-level) |
| Preview | POR-04 request detail | planned (R-01; spec-level) |

Inbound: BND-02 "+ Request" and "Edit", AUD-02, AUD-03, AUD-05, AUD-19, CLS-03, TAX-03, ENG-02, ENG-12, EBP-01, EBP-03, TXT-04, SHL-08, SHL-17, SHL-21, SHT-01, TPL-20, ATT-09, IAU-02. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- SHL-14 acceptance: fieldset rows match the `close-intake.png` detail card: key left in ink-2, value right, ⇕ pickers, olive "Visible to client" toggle, "Pending incorporation" amber pill.
- SHL-14 acceptance: the client preview is plain language, firm-branded, and free of firm internals.
- SHL-14 acceptance: counts update coherently: 11 of 24 → 11 of 25 (one new). (11 of 49 for 25 sample requests belongs to c, deferred to A-03.)
- SHL-14 acceptance: fidelity bond wording is domain-correct (10% of plan assets, $500,000 cap without employer securities; Schedule H line 4e).
- SHL-14 acceptance: the delegated request names Sam Ortiz and states that he sees only this request; its status reads "Requested Sep 1 · due Sep 25".
- SHL-14 acceptance: close variant figures tie: 73,166.90 − 1,684.54 = 71,482.36; request "Square payouts — August", file `square-2026-08-01_2026-08-31-payouts.xlsx`, uploaded by Ben Ashby Sep 3, 2026.
- SHL-14 acceptance (R2): tabs Details · Comments · Activity sit under the header; Details is the drawer as built.
- SHL-14 acceptance (R2): Draft is a neutral outline pill; Visibility reads Owners only until sent.
- SHL-14 acceptance (R2): Links shows Related rows, Controls and "Link from another engagement…".
- SHL-14 acceptance (R2): state f matches §9.3.3: SURL request to Luis Ferrante, approved and sent by Cole Hart (11:02 AM).
- P-06 §3.3: with no due date "Save & send" is disabled with "Add a due date to send" and the API answers 422 `due_date_required`; the agent principal is denied `request_item.send`.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Source Documents count (a) | 11 of 24 → 11 of 25 received after one new request | P-06-T08 footing test |
| Close variant (d) | 73,166.90 − 1,684.54 = 71,482.36 | P-06-T08; P-06-T29 |
| Close binder (d) | 8 recurring + 1 ad hoc = 9 requests (P-06 §5.4, J10 step 2) | P-06-T08 |
| Fidelity bond (a) | at least 10% of plan assets, capped at $500,000 | copy test against spec.md |
| Bridge letter (b) | Requested Sep 1 · due Sep 25 | scenario test |
| f | Related rows "40 rows" (fixture only) | scenario test |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, materiality, sample parameters or agent reasoning in the client preview, boxed form fields with borders (use row grammar), the words Accrual/ACME. R2: the agent sending a request; a Draft in the client portal; changing states 1–5 beyond items 1–5; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-6 | "Link from another engagement…" is hidden and Linked rows do not open SHL-21 until K-04 grants `request_item.link_cross_engagement` | SHL-21 is K-04's | P-06 §2.4 |
| DV-11 | f: while the firm's P-25 setting is off, "Approve & send" on an agent-drafted request whose client wording is model text and unchanged is disabled with "Edit the client wording before sending" and the server answers 409 `model_text_not_permitted`. The seeded SURL Draft has `drafted_wording_source = 'template'` and sends as designed | ADR-111; DEC-79 off | P-06 §2.4 (closes with N-03, P-25) |
| — | c (Sample-driven bulk) is not built here | needs the sampling engine and EBP-04 | P-06 §2.3 → A-03 |
| — | Related rows and Controls render "—" until sheets (F-08) and attest controls (X-01) exist | engines not built | P-06 §2.1 |
| — | "+ Attach" for reference files is R-01's | portal file intake | P-06 §2.1 |
| — | The spec's C-16 preview rows are drawn inline (README note) | README build detail | P-06 §5.3 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, d, e, f | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | report-only until A-01's AUD-03 host is stable |
| c | — | — | deferred to A-03; recorded in `routes/manifest/shl.ts`, not missing |
| host | D | — | drawer 480, pane header 46 with a 14.5/500 title, rows 34, pills 21, radius 14 |

## Open gaps
- Clocks: the README renders a–e at "Thu Sep 24, 9:41 AM"; revision.md renders states 1–5 at Mon Sep 14, 2026, 9:41 AM CT. Revision wins (DEC-15 precedence).
- The Underlay differs per state (a, b, e Northwind cockpit with Toolbar "Audits"; d CLS-03 Copperleaf Intake with Toolbar "Closes"; f Granite Peak audit). In P-06 the drawer is hosted from BND-02; the AUD-03 and CLS-03 hosts come with A-01 and C-01.
- P-06 §3.8 has Raj add "Sound Electric invoice — Aug 18 ($3,200)" to the Copperleaf binder (J10 step 2). That request is journey data for the d scenario's binder; artboard d itself shows the Square payouts request as the handoff draws it.
- Personas `marcus-delaney` and `cole-hart` are added to the scenario by P-06-T08 if F-04 has not.
