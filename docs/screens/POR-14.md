# POR-14 · Third-party request room

| Field | Value |
|---|---|
| Route and params | `/requests` in the portal entry, the reduced shell chosen by the server (`GET /v1/me` → `portal.shell = "third_party"`, P-08); `/requests/$requestId` opens one row full screen at 390. The invitation `/accept` route is P-08's; an expired, used or unknown token renders f inside the reduced shell. Artboards: `/components/screens/POR-14?st=a…f` |
| Template and host frame | T7 reduced (F-05 `PortalLayout variant="reduced"`: one centred pane 720) with `PortalToolbar` reduced to the single item "Requests"; T7-M at 390 (specified, not built; no tab bar) · `Wave 2 - Client Portal.dc.html#por14` |
| Surface | portal (white-labelled; the third party sees the firm's name, never "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-14 Third-party request room - Keystone Retirement Services/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | R-01 · contract R-01-T03; contract stub R-01-T01; consumer tests R-01-T02; fixtures R-01-T05; room read model and invitations on delegation R-01-T13; frontend (the `ScopedRequestRoom` composition) R-01-T14; parity and accessibility R-01-T31. A-09 reuses `ScopedRequestRoom` for POR-23 |
| Manifest status | built on fixtures and live (R-01-T14 over R-01-T13's read model, 2026-10-26): every artboard in the gallery, and the portal entry's `/requests` (a row at `/requests/$requestId`); the manifest entry stays `planned` with a null path, as POR-03's (DEC-347) |

Code to come (R-01 §5.2): `src/screens/POR-14/{index.tsx, scenarios.ts, copy.ts, POR-14.test.tsx}`, `src/domain/portal/{room.ts, ScopedRequestRoom.tsx}`, `src/routes/portal/requests.tsx`, `src/fixtures/handlers/portal-room.ts`.

**White label and isolation (AGENTS frontend rule 7, DEC-59, INV-4).** Portal code never renders "Accrued". A third party sees only the requests delegated to them: no other request, binder, client page, materiality, sample parameter, participant SSN, other third party or client contact detail beyond the plan name. Every other route answers `404`.

## States

Fixture scenarios (R-01-T05, `fixtures/scenarios/POR-14.ts`), footed by the room footing test (Keystone 4 of 9 at a, 5 of 9 at b).

6 artboards in the handoff (a–f), 6 built here; the 390 layout is specified, not drawn (Tier D only).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | sam-ortiz (Sam Ortiz, Keystone Retirement Services, `third_party` grant on 9 Northwind request items) | Mon Sep 14, 2026, 9:24 AM CT | E0 | 9 delegated items in two bands, 4 uploaded; the bridge-letter row expanded with the firm's guidance and the comment thread | fixture (T14) |
| b | sam-ortiz | **Tue Sep 22, 2026** | E0 at Sep 22 | Sam uploaded the bridge letter; nobody has accepted it: "You uploaded Sep 22 · Brightwater Hale is reviewing it", 5 of 9 | fixture (T14) |
| c | sam-ortiz | **Wed Sep 23, 2026** | E0 at Sep 23 | Marcus Delaney returned the bridge letter with reason `wrong_period` and a note | fixture (T14) |
| d | harborline-certifications (Harborline Trust Company's certifications contact) | **Fri Sep 11, 2026** | E0 at Sep 11 | Harborline's two delegated items (certification uploaded Sep 11 and in review; trust statement due Sep 18) with the firm-written ERISA §103(a)(3)(C) introduction from the request guidance | fixture (T14) |
| e | sam-ortiz | **Mon Sep 28, 2026** | E0 at Sep 28 | All 9 delegated items received: the green-tint banner | fixture (T14) |
| f | (no principal: an invitation token that is expired, used or unknown) | Mon Sep 14, 2026, 9:24 AM CT | E0 | P-08's invitation accept answers its one `404` for every failure | fixture (T14) |

Personas: `sam-ortiz` exists (P-08-T08, P-08-T14); `harborline-certifications` is added by R-01-T05.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Loading | `GET /v1/portal/room` pending | token skeleton in the 720 pane, status label "Loading" |
| Error | the read fails | C-20 `ErrorRow` |
| Outside the room | Sam opens `/`, `/documents`, `/approvals`, `/deliverables` or a request id not delegated to him | `404` (the reduced toolbar offers no route to POR-02, POR-08 or POR-09) |
| Which request? | a file dropped on the "Drop files here" pill with more than one open request | the request picker "Which request is this for?" with a pre-selection from `POST /v1/portal/room/suggest` (code-only file-name scoring among the delegated items) |
| Flag off | `portal.third_party_room` false | F-05's flag-off ViewState for a third-party principal; delegations are recorded only |
| 390 | viewport under 768 px | single scrolling page, header 56 with brand and avatar, bands and rows full width, a tapped row opens full screen (`/requests/$requestId`) with upload and comments; no tab bar |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/portal/room` | `PortalRoomOut`: `engagement_label` ("Northwind Robotics 401(k) Plan · 2025 audit"), `firm_name`, `organisation_name`, `intro` (firm-written; d's certification introduction), `uploaded_count`, `total`, `complete`, `bands[{code, label, uploaded, total, rows[]}]`, rows `{id, title, sub {kind ∈ uploaded\|due\|in_review\|returned, date}, disc ∈ done\|ring, guidance, files[{id, name, receipt, withdrawable}], returned {reason_code, note, by, at}?, comment_count, allowed_actions[]}` | `portal.documents.read` · `third_party` with `delegated_only` | `upload`, `withdraw` (own unaccepted upload), `comment`; nothing else |
| write | `POST /v1/portal/room/suggest {file_names[]}` | `{suggestions[{file_name, request_item_id?}]}`; code-only file-name scoring among the caller's delegated items; no content, no model | `portal.documents.read` | the third party |
| write | `POST /v1/engagements/{eid}/request-items/{id}/uploads` (existing) | upload to the chosen item | `evidence.upload` (`delegated_only`) | `upload` |
| write | `POST /v1/engagements/{eid}/evidence-versions/{vid}/withdraw` (P-06; P-31) | withdraw while in review | `evidence.withdraw` | `withdraw` |
| read / write | `GET`/`POST /v1/engagements/{eid}/request-items/{id}/comments` (existing) | the thread under the expanded row | `comment.read` / `comment.create` (`delegated_only`) | `comment` |

Accept and return happen only firm-side (AUD-03) and reflect here as b and c. Every upload and comment is audited with Sam as actor and the organisation as an attribute; the request owner gets the in-app `third_party.uploaded` kind (INV-5).

## Status
- Rows use the `request` object's client words through discs: 18 px olive ✓ for uploaded or received, empty ring for to do; "Due Sep 18" is the request's due date, never "Overdue" before it passes.
- `request` `uploaded` before acceptance → sub-line "You uploaded Sep 22 · Brightwater Hale is reviewing it" (the firm words "Uploaded – needs review" never appear).
- `request` `returned` → red-tint pill "Returned · wrong period".
- Room complete → green-tint banner.

## Copy
Copy keys live in `screens/POR-14/copy.ts`; strings verbatim from spec.md and the built artboards.

| Key | String |
|---|---|
| `nav.requests` | "Requests" |
| `user.menu` | "Security" · "Sign out" |
| `pane.title` | "Requests" |
| `intro.title` | "Northwind Robotics 401(k) Plan · 2025 audit" (template `{engagement_label}`) |
| `intro.body` | "Brightwater Hale LLP asked Keystone Retirement Services for these items. You can only see and upload to these requests." (template `{firm_legal_name} asked {organisation_name} for these items. You can only see and upload to these requests.`) |
| `progress` | "4 of 9 uploaded" (template `{n} of {total} uploaded`) |
| `drop.pill` | "Drop files here" |
| `band.count` | "3 of 5" (template `{n} of {total}`) |
| `row.uploaded` | "Uploaded Sep 2" (template `Uploaded {date}`) |
| `row.due` | "Due Sep 18" (template `Due {date}`) |
| `row.inReview` | "You uploaded Sep 22 · Brightwater Hale is reviewing it" |
| `row.uploadSlot` | "Drop the letter here or Upload…" |
| `comment.placeholder` | "Comment…" |
| `returned.pill` | "Returned · wrong period" |
| `returned.note` | "This letter covers Jan–Jun 2025. We need Oct 1 to Dec 31, 2025. — Marcus Delaney" |
| `custodian.intro` | "Under ERISA section 103(a)(3)(C), Brightwater Hale relies on your certification of the plan's investment information." (firm-written request guidance; database content, not a constant) |
| `complete.banner` | "Everything Brightwater Hale asked Keystone for is in. Thank you." |
| `expired.title` | "This link has expired or was already used" (POR-14f no-oracle copy; Deviations) |
| `expired.action` | "Ask Brightwater Hale for a new link" |
| `picker.title` | "Which request is this for?" |
| `withdraw.action` | "Withdraw" |
| `withdraw.confirm` | "Withdraw this file? Brightwater Hale's team won't use it. It's kept securely for 30 days, then erased." (DF-15) |

Per-artboard data (seed rows, R-01-T05; verbatim):
- **a** band "Recordkeeper reports" (3 of 5): "Schedule of account balances — every participant, 12/31/2025" / "Uploaded Sep 2" ✓ · "Annual participant loan roll-forward — 2025" / "Uploaded Sep 2" ✓ · "BrokerWindow self-directed brokerage asset detail — 12/31/2025" / "Uploaded Sep 2" ✓ · "Withdrawals and distributions report — 2025" / "Due Sep 18" ○ · "Contribution remittance report — deposit date for each 2025 payroll" / "Due Sep 18" ○. Band "SOC 1 & fees" (1 of 4): "SOC 1 Type 2 report — Oct 1, 2024 to Sep 30, 2025" / "Uploaded Sep 2" ✓ · "Bridge letter — Oct 1 to Dec 31, 2025" / "Due Sep 25" ○ (expanded) · "ERISA 408(b)(2) fee disclosure" / "Due Sep 25" ○ · "Plan expense invoices paid from plan assets — 2025" / "Due Sep 25" ○. Expanded guidance "Your SOC 1 Type 2 report covers October 1, 2024 to September 30, 2025. Please upload a letter from Keystone management saying whether there were any material changes to the controls in that report, or any known control failures, from October 1 through December 31, 2025."; thread "Marcus Delaney · Brightwater Hale · Sep 1" "A signed PDF on Keystone letterhead is fine." · "Sam Ortiz · Sep 10" "Our compliance team issues bridge letters on the 20th — I'll upload it by Sep 22."; user chip "Sam Ortiz · Keystone".
- **d** items "Certification of investment information — 12/31/2025, signed" (uploaded Sep 11 · "Brightwater Hale is reviewing it") and "Trust statement — 12/31/2025" (Due Sep 18).

Accessibility (R-01 §5.6): the "Drop files here" pill has a focusable "Choose files…" path and each row an "Upload…"; discs carry accessible names; the progress bar is `role="progressbar"`; "Returned · wrong period" carries text with the red tint.

Copy bans on this screen: never "Accrued", the rest of the PBC list, other third parties, plan materiality, sample parameters, participant SSNs, client contacts' details beyond the plan name, the full portal nav, an agent name or a firm status word.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| f "Ask Brightwater Hale for a new link" (the branding support contact; the designed target is POR-01's expired frame) | POR-01 `to.POR01()` | per manifest (P-08) |
| User menu "Security" · "Sign out" | POR-12 (security) · POR-01 after sign-out | planned (N-03) · per manifest |
| Row click, "Drop files here", comment send | in-screen (row expands; `/requests/$requestId` at 390) | in-screen |

Inbound: POR-01 invite acceptance, POR-20 Invitation and Reminder, CLI-04 invite, and the designed links AUD-03 "Request from third party…", EBP-01 and EBP-07 (each opens POR-14 scoped to the delegated requests), PRJ-01 (engineer room, T-09). Firm side (not links): AUD-03, AUD-10, INB-04. POR-14 has no outbound designed link in `handoff-links.json`; every ID above is a manifest screen.

## Acceptance
- POR-14 acceptance: band and row grammar matches `bento-audit-client.png` (folder band on `#EFEEEB`, title and sub-line, 18 px olive disc vs empty ring).
- POR-14 acceptance: Sam sees exactly 9 delegated requests (CLI-04 "9 delegated requests only"), 4 uploaded, and nothing else of the 24-item PBC.
- POR-14 acceptance: the bridge-letter wording is technically right (SOC 1 period Oct 1, 2024 – Sep 30, 2025; gap Oct – Dec 2025).
- POR-14 acceptance: the Harborline variant cites the §103(a)(3)(C) certification role.
- POR-14 acceptance: acceptance and return are firm-side only; the third party sees the result.
- POR-14 acceptance: the 390 frame is a single scrolling page with no tab bar.
- R-01-T14 acceptance: six scenarios pass and the reduced toolbar offers only "Requests".
- R-01 Story 6.2: an expired, used or unknown link shows the one state f with identical timing and response for every failure (P-08's no-oracle rule).

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Room (a) | 9 delegated = 5 Recordkeeper reports + 4 SOC 1 & fees; 4 uploaded = 3 + 1 | R-01-T05 footing test |
| Room (b) | 5 of 9 (the bridge letter uploaded) | same |
| Room (e) | 9 of 9; complete | scenario test e |
| PBC | 9 of Northwind's 24 items are Keystone's; the other 15 never reach the room | R-01-T05 seed test; R-01-T20 security case |
| Periods | SOC 1 Type 2 Oct 1, 2024 – Sep 30, 2025; bridge letter Oct 1 – Dec 31, 2025 | seed |

## AVOID
Each becomes a test in `POR-14.test.tsx` ("POR-14 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, the rest of the PBC list, other third parties, plan materiality, sample parameters, participant SSNs, client contacts' details beyond the plan name, the full portal nav.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| POR-14d viewer | d's viewer is Harborline Trust Company's certifications contact (`harborline-certifications`), not Sam Ortiz as the README's viewer column repeats | The custodian variant belongs to Harborline's grant | R-01 §2.1 |
| POR-14f no-oracle | f reads "This link has expired or was already used" with "Ask Brightwater Hale for a new link", instead of "This invitation has expired" | Invitations v2 answer one `404` for every failure; the copy may not reveal which (P-08-T18) | R-01 §2.1; DEC-212 |
| DEC-35 | Invitation links are 14-day and single-use; a used link lands on f | Invitations and lockout | decision-log DEC-35 |
| DF-15 | The design's "Remove" while in review is **Withdraw** with the DF-15 confirm | Client withdrawal (ADR P-31) | 09 DF-15 |
| DEC-63 | The third party is a named person with the organisation as an attribute ("Sam Ortiz · Keystone") | Third parties and the approver of record | decision-log DEC-63 |
| DF-03 | The 390 layout is specified, not drawn: Tier D only | Portal responsive scope | 09 DF-03 |
| — | The "Which request is this for?" picker pre-selects by code-only file-name scoring among the delegated items (`room/suggest`); the person chooses | No content and no model reach the choice (ADR-050) | R-01 Story 6.2 |
| — | `intro` is null from the live read model: the intro reads the template with the firm's name ("Brightwater Hale asked …"); the fixtures carry the legal name and, at d, the custodian's line | No firm-written room introduction exists yet (DEC-387); the custodian's line is request guidance | DEC-387 |
| — | The banner and the chip shorten the organisation to its first word ("Keystone", "Harborline"), as the handoff writes them | The read model carries the organisation's full name | R-01-T14 |
| — | The open row's slot reads "Drop the letter here or Upload…" for a letter and "Drop the file here or Upload…" for anything else | The handoff draws only the bridge letter | R-01-T14 |
| — | Any 404 from the room (no delegation, the flag off, an expired or used link) reads as f | One answer for every case (no oracle) | R-01 Story 6.2 |
| — | At 390 an open row is shown alone (`/requests/$requestId`); the page has no tab bar (`PortalLayout` draws none for an empty nav) | T7-M for a room of one area | R-01-T14 |
| DEC-471 (seed) | Keystone's 9 and Harborline's 2 are delegated on the live seed without a grant (nobody signed in); a's "4 of 9" stays a fixture figure, because AUD-03's statuses make 6 of Keystone's 9 done | Two goldens disagree; the delegations are synthetic | decision-log DEC-471; TASK-1221 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, e | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked before M8 (R-01-T31) |
| f | C | not run | reported with the copy deviation masked |
| 390 | D | — | single page, header 56, targets ≥ 44 × 44, no tab bar |
| host | D | — | pane 720 centred, header 46, intro padding 16 18, band 32, row 52, disc 18, progress 3 px × 200, pill 30 |

## Open gaps
- R-01-T14 wrote the words the handoff has no frame for in `domain/portal/messages.ts` (`ROOM_WORDS`): "Couldn’t load your requests. Nothing was lost; try again in a moment." with Retry, a failed write's toast "That didn't go through. Nothing changed; try again in a moment.", the picker's "Upload" and "Cancel", the composer's "Send comment".
- No handoff string for the room's load error or flag-off state: the keys are reserved; R-01-T14 uses F-05's portal flag-off ViewState and records any new string here.
- The user menu's "Security" target is POR-12's security section (N-03); until it exists the item is hidden in production.
