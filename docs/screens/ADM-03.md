# ADM-03 · Offices, teams, walls & offshore

| Field | Value |
|---|---|
| Route and params | `/settings/offices` (G-01 §5.1) behind `firm_settings.v2`. `?expand=<office code>` (CHI · DEN · NYC; a stable firm-scoped key), `?ov=wall:new`, `?ov=wall:<wallId>` (the wall log drawer), `#walls`, `#offshore`. Names, emails and TINs never travel in a URL. Artboards: `/components/screens/ADM-03?st=a…h` |
| Template and host frame | T12 `SettingsLayout` (F-05-T45; `bare`; fieldsets 860) with Fieldset, ValueRow, sub-header rows (`--nested`), initials chips, Count pills, a table inside a fieldset, locked Toggles, O3 500 `Sheet` (new wall), O2 480 `Drawer` with `Timeline` (wall log), Toast · `Wave 3 - Admin & Governance.dc.html#adm03` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-03 Offices- teams- walls and offshore/` (README.md, spec.md, revision.md: R2 service lines; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | G-01 · contracts G-01-T01 (TASK-1225) · stub T02 · seed and fixtures T06 · offices, teams and groups T08 · walls v2 and offshore T09 (TASK-1207 narrowed offshore) · service-line need-to-know T12 · screen T14 · independent AC tests T15 · Playwright T16 · parity lock T17 |
| Manifest status | planned (`routes/manifest/adm.ts`); fixture once G-01-T14 builds it |

Code to come (G-01-T14): `src/screens/ADM-03/{index.tsx, copy.ts, scenarios.ts, ADM-03.test.tsx}`, `src/fixtures/scenarios/ADM-03.ts`, wall and offshore handlers in `src/fixtures/handlers/firm-settings.ts`, `e2e/screens/adm-03.spec.ts`.

## States

8 artboards in the handoff (README letters a–h; g and h have no spec letter: g was added in the build, h is revision R2's state f), 8 to build.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway (Grace Holloway, Firm Admin) | Mon Sep 14, 2026, 9:24 AM CT | E0 | `?expand=CHI`: offices (Chicago HQ 22, Denver 14, New York 10), teams 16 · 21 · 7 · 2, groups EQR pool 2 · Monitoring reviewers 5 · Seasonal 5, service lines (R2), three walls, offshore 0 members; nothing edited: Save disabled | to build (T14) · Prod |
| b | grace-holloway | Mon Sep 14, 2026, 9:20 AM CT | E0 | `?ov=wall:new` with Lena Park ✕ Ashford Manufacturing Co., reason Personal relationship "Family member employed at Ashford", approver Margaret Okonkwo; effects from `GET /v1/walls/preview` ("Remove from 0 current assignments") | to build (T14) · Prod |
| c | grace-holloway | 9:24 AM | E0 | the sheet with Neil Ashcroft ✕ Ashford: the preview returns `relationship_partner`; red-ink row; Save disabled | to build (T14) · Prod |
| d | grace-holloway (Remy Vidal's membership offshore) | 9:24 AM | E0 + Remy offshore | `GET /v1/firm/offshore`: 1 member, 0 consented clients; the amber banner (copy per DEC-352) | to build (T14) · Prod |
| e | daniel-reyes (Daniel Reyes, Partner) | 9:24 AM | E0 | read-only fieldsets A, B, service lines and D under the banner and locks; fieldset C shows "+ Wall" and per-row Approve and Lift where he is the named approver or a partner (AC11.2); every wall row opens its log | to build (T14) · Prod |
| f | grace-holloway | 9:20 AM | E0 | `#walls` scrolled; the Lena Park wall created at 9:20 AM is tinted amber-tint for 2 s (none under reduced motion) and reads "Awaiting Margaret Okonkwo" until she approves | to build (T14) · Prod |
| g | grace-holloway | 9:24 AM | E0 | `?ov=wall:<Lena wall>`: `GET /v1/walls/{id}/events` in the ADM-07 grammar ("Ethical wall added by Grace Holloway", "Approved by Margaret Okonkwo") | to build (T14) · Prod |
| h | grace-holloway | 9:24 AM | E0 | Service lines: Tax narrowed to "Engagement team only" (dirty): the amber confirm row, Save enabled | to build (T14) · Prod only if the service-line decision is accepted by Fri Jan 29, 2027; otherwise fixture-only with the fieldset read-only at "Engagement team only" (AC10.4) |

Non-artboard states:

| State | Data condition | Rendering |
|---|---|---|
| Step-up for walls | `GET /v1/walls` answers 403 (`wall.list` keeps `mfa_recent`, SPEC-002 Q2) | a step-up row in fieldset C: "Confirm it's you to view walls" (R-5); no wall count anywhere |
| Loading | offices, teams or walls pending | skeleton value rows per fieldset |
| Not allowed | no settings role (overview 404) | "You don't have access to firm settings." |
| Remy Vidal's own view (d's check) | `remy-vidal` signed in, offshore, no consent provider | CLI-01 lists the clients his roles reach; TINs masked; no reveal offered (AC9.1 as amended by TASK-1207) |
| Flag off | `firm_settings.v2` off | "This settings section isn't built yet." |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/firm/offices` | address, lead, code, HQ, reviewer pool, derived seats, registered facts | `org_structure.read` | firm staff |
| write | `POST /v1/firm/offices` · `PATCH /v1/firm/offices/{id}` | `409 office_code_taken · one_hq` | `org_structure.manage` (fresh MFA) | firm admin, security admin |
| read/write | `GET /v1/firm/teams` · `POST` · `PATCH /{id}` · `PUT /{id}/members` | teams and groups with members | `org_structure.read` / `org_structure.manage` | as above |
| write | `PUT /v1/firm/groups/seasonal/access-ends` | one date for every seasonal member | `firm.manage_users` (fresh MFA) | firm admin |
| read/write | `GET /v1/firm/service-lines` · `PUT /v1/firm/service-lines/{line}` | policies; `422 audit_locked`; `409 stale_version` | `firm.read_settings` / `service_line_policy.manage` | 501 until G-01-T12 |
| read | `GET /v1/firm/offshore` | member ids, consented-client count (0 until T-01 registers the consent provider) | `firm.read_settings` | the two policy toggles are always on |
| read | `GET /v1/walls` | wall register with reason, creator, approver, approval status | `wall.list` (fresh MFA) | firm admin, security admin, partners |
| read | `GET /v1/walls/preview?user_id&client_id` | blockers (`relationship_partner`, `wall_exists`, `own_wall`), `assignments_ended` | `wall.create` | firm admin, partners |
| write | `POST /v1/walls` | reason, text, named partner approver; active at once (DEC-73); `409 relationship_partner · wall_exists`; `422 approver_not_partner` | `wall.create` (fresh MFA) | firm admin, partners |
| write | `POST /v1/walls/{id}/approve` | named approver only; `409 already_approved`; `403 not_named_approver` | `wall.approve` (fresh MFA) | the named partner |
| write | `POST /v1/walls/{id}/remove` | lift with a reason; `409 own_wall` | `wall.remove` (fresh MFA) | partners (DEC-73) |
| read | `GET /v1/walls/{id}/events` | the wall's log, newest first | `wall.list` | as above |
| read | `GET /v1/firm/members` | person and approver pickers | `wall.create` | firm admin, partners |

## Status
- `wall_approval` (`status-vocabulary.yaml`, G-01 §3.8): `awaiting` "Awaiting approval" (amber; the row reads "Awaiting {partner}") · `approved` "Approved".
- Offshore toggles: on, locked (Lock 12, `aria-disabled` with the reason).

## Copy
Copy keys will live in `screens/ADM-03/copy.ts`; strings verbatim from spec.md and revision.md, except the deviations below.

| Key | String |
|---|---|
| `fieldsets` | "Offices" · "Teams & groups" · "Service lines" · "Ethical walls" · "Offshore & restricted access (§7216)" |
| `adds` | "+ Office" · "+ Group" · "+ Service line" · "+ Wall" |
| `office.summary` | "{seats} seats · {returns} TY2025 returns" (HQ) · "{seats} seats · {returns} returns" |
| `office.rows` | "Address" · "Time zone" · "Office lead" · "Office code" (helper "Used in CCH Axcess office mapping (ADM-08).") · "Default reviewer pool" |
| `offices.total` | "All offices — {seats} seats · {returns} returns" |
| `teams.sum` | "16 + 21 + 7 + 2 = 46 seats" (computed) |
| `groups` | "Groups" · EQR pool helper "Eligible EQR reviewers; cannot be EQR on their own engagements (SQMS No. 2)." · Monitoring helper "Objective inspectors for ADM-12." · "Access ends" |
| `serviceLines` | columns "Service line" · "Lead" · "Content visible to" · "Cross-line access"; values "Engagement team only" · "Service line" · "Hand-offs only (AUD-38)" · "Hand-offs only" · "By request (partner approves)"; example row (Granite Peak, revision item 2); helper (revision item 3); confirm row h "Tax staff lose access to tax engagements they are not staffed on. Save to apply."; fallback helper "Service-line sharing is not available yet" (AC10.4) |
| `walls.columns` | "Person" · "Walled from" · "Reason" · "Added" · "Approved by" |
| `walls.helper` | "Walled people cannot open, search, be assigned to, or run agents on these clients." (DEC-43, DF-14: the sentence about counts in Go… is dropped) |
| `walls.awaiting` | "Awaiting {partner}" |
| `walls.stepUp` | "Confirm it's you to view walls" |
| `sheet` | "New ethical wall" · "Person" · "Walled from" · "Reason" · "Effect" · "Remove from {n} current assignments" · "Hide from search, Go… and Inbox" · "Block agent runs she starts on this client" · "Exclude from portal threads" · "Approval" · "Requires a partner: {partner}" · "Save" |
| `sheet.conflict` | "{person} leads this relationship. Reassign the relationship partner first." |
| `toast.wall` | "Wall added · approval requested from {partner}" (DEC-73, INV-5) |
| `log` | "Ethical wall added by {person}" · "Approved by {person}" · "Wall lifted by {person}" |
| `offshore.rows` | "Offshore / restricted group" "{n} members" · "Clients with a valid offshore consent" "{n}" + "Consent registry ›" · "Block offshore assignment without consent" (helper "Required by firm policy; cannot be turned off.") · "Mask TINs for restricted members" · "Quarterly access review" (G-02's; hidden until it registers) |
| `offshore.groupHelp` | "Members can be assigned only to clients with a valid §7216 consent to disclosure to offshore preparers; SSNs stay masked (Treas. Reg. §301.7216-3(b)(4); Rev. Proc. 2013-14 §5.07)." (DEC-352) |
| `offshore.banner` (d) | "{person} can't be assigned to a client until its offshore consent is signed. SSNs stay masked." (DEC-352) |
| `readOnly` (e) | "Only firm admins can edit these settings." |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "22 seats" on an office | ADM-02 `?office=<id>` | built by G-01-T10 (fixture) |
| A team's chips | ADM-02 `?team=<id>` | built by G-01-T10 (fixture) |
| A wall row | the wall log drawer `?ov=wall:<id>` | in-screen |
| "Opens ADM-07 · Audit log filtered to this wall" | ADM-07 | planned (G-02) |
| "Consent registry ›" | ADM-05 filtered to "Disclosure to offshore preparers" | planned (T-01) |
| Office code | ADM-08 office mapping | planned (T-01) |
| Section list ("Opens ADM-01 · Settings home", "Opens ADM-02 · People", …) | ADM-01 · ADM-02 · ADM-04 (AI policy) · ADM-05 (Consents) · ADM-06 (Security) · ADM-07 (Audit log) · ADM-08 (Integrations) · ADM-09 (Developer) · ADM-10 (Portal) · ADM-11 (Quality) · ADM-12 (Monitoring) | ADM-01 built; ADM-02 built (T10); others planned |

Inbound: ADM-01 (Offices & teams, an office row, At a glance), ADM-02 (wall tags, office filter), the `wall_approval_requested` notification ("Review" → `/settings/offices?ov=wall:<id>`).

## Acceptance
- ADM-03 acceptance: offices tie to ADM-01 (22/14/10 seats; 98/64/62 returns) and carry codes CHI/DEN/NYC used in ADM-08.
- ADM-03 acceptance: teams 16 + 21 + 7 + 2 = 46; groups EQR pool 2, Monitoring reviewers 5, Seasonal 5, Offshore 0.
- ADM-03 acceptance: three walls, each with reason, adder, date and a partner approver; the Lena Park wall is dated today 9:20 AM and matches ADM-07.
- ADM-03 acceptance: the offshore group is consent-gated with locked toggles; SSN masking is explicit (§301.7216-3(b)(4)).
- ADM-03 acceptance: fieldset bands, sub-header rows and indented rows match the Edit Agent sheet grammar.
- ADM-03 acceptance (R2): the Service lines fieldset sits between Teams & groups and Ethical walls.
- ADM-03 acceptance (R2): Audit & assurance is locked to engagement team only.
- ADM-03 acceptance (R2): the Granite Peak example uses only seeded staff (MO, HL, SB, CH; LW, IM, VH).
- ADM-03 acceptance (R2): offices, teams (46 seats), walls and offshore fieldsets are unchanged.
- G-01 AC8.7: no response carries `hidden`, `hidden_count` or a field derived from walled rows; the walls helper names no count.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Offices | 22 + 14 + 10 = 46 seats; 98 + 64 + 62 = 224 returns | `fixtures/firm-people.foot.test.ts` |
| Teams | 16 + 21 + 7 + 2 = 46 | same |
| Groups | EQR 2 · Monitoring 5 · Seasonal 5 · Offshore 0 (d: 1) | same; ADM-03 scenario tests (T14) |
| Walls | 3 (VH Two Rivers Brewing Co. Feb 3, 2026 approved MO; LP Ashford today 9:20 AM approver MO; PS Harold Stein Feb 18, 2026 approved DR) | same |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, invented staff or clients, colour-coded office badges, org-chart diagrams, any way to bypass the offshore lock. From R2: service lines replacing ethical walls; any way for admins to open content; changing fieldsets A–D or the 46-seat totals; colour-coded badges; blue; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-43 / DF-14 | The walls helper drops "Results hidden by a wall show only as a count in Go… (SHL-02)." | Walls use 404 semantics everywhere; nobody sees a hidden count | DEC-43 |
| DEC-73 / INV-5 | The save toast reads "Wall added · approval requested from Margaret Okonkwo", not "Wall added · approval recorded"; the new row reads "Awaiting Margaret Okonkwo" until she approves with fresh MFA | A wall applies at once; a firm admin cannot record a partner's approval | DEC-73; parity masks the toast (b, c) and the Approved by cell (f) |
| SPEC-002 Q2 / R-5 | A "Confirm it's you to view walls" step-up row when MFA is not recent | `wall.list` keeps `mfa_recent` | G-01 R-5 |
| AC11.2 | ADM-03e: Daniel Reyes sees "+ Wall" and per-row Approve and Lift where he is the named approver or a partner, instead of a fully locked board | DEC-73 gives walls to partners; confirmed in T01 | DEC-352 |
| DEC-352 (TASK-1207) | ADM-03d's banner reads "Remy Vidal can't be assigned to a client until its offshore consent is signed. SSNs stay masked." instead of "Remy Vidal can see 0 clients until offshore consents are signed."; the group helper reads "Members can be assigned only to clients…" instead of "Members see only clients…" | Offshore is not a wall (TASK-1207, DEC-319 narrowed): an offshore member sees and works what their roles reach; consent gates assignment (`409 offshore_consent_required`) and reveals stay refused (`not_offshore`) | DEC-352; parity masks both strings (d) |
| AC10.4 | h is fixture-only and the fieldset read-only at "Engagement team only" unless the service-line decision is accepted by Fri Jan 29, 2027 | Widening content reads is red and never defaults on silence | G-01 §11 OQ-1 |
| — | "Quarterly access review" in fieldset D is hidden until G-02 registers it | G-02 owns access reviews | G-01 §2.1 |
| — | g (the wall log drawer) and h have no spec letter | Added in the build; h is revision R2 state f | handoff README |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–g | C (locked in G-01-T17) | not run | b, c masked on the toast; d masked on the banner and group helper (DEC-352); f masked on "Awaiting …"; the walls helper string masked (DEC-43) |
| h | C if Prod, report-only if fixture-only | not run | AC10.4 |
| host | D | — | band 33, value row 34, sub-header 34, wall rows 40, toggle 38×22, sheet 500, drawer 480 |

## Open gaps
- The handoff's toast and helper copy predates DEC-43, DEC-73 and TASK-1207; the strings above are the product's words until a design refresh redraws d, b and the helper.
- The service-line policies are 501 until G-01-T12; the fieldset renders read-only from the fallback until then.
- Returns per office are T-02's office facts (fixture until then).
