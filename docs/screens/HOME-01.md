# HOME-01 · Home dashboard

| Field | Value |
|---|---|
| Route and params | `/home` (the firm landing page; `/` redirects here once I-01-T13 removes P-01's interim redirect to `/engagements`). Segmented targets: `/home/approvals?gate=<uuid>` (HOME-02), `/home/deadlines` (HOME-03), `/home/capacity` (HOME-04), `/home/insights/:tab` (INS-*); `?brief=1` (HOME-05) is I-02's. Artboards: `/components/screens/HOME-01?st=a…i` |
| Template and host frame | T11 `DashboardLayout` (F-05-T46; twin of TPL-11): subbar 42 · tile row 99 · queue flex + right column 420 · `Wave 1 - Module Shells.dc.html#home01` |
| Surface | firm (never in the portal bundle; client principals get 403 on `/v1/home`, INV-4) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/HOME-01 Home dashboard/` (README.md, spec.md, revision.md R2; revision wins over spec, DEC-15) and, for the spec-only role states b–e, `TPL-11 Dashboard specimen - Home/` (DF-06) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | I-01 · contract I-01-T01 (this file); home stub T02; fixtures T05; main region T06; `GET /v1/home` T10; right column, chrome and b–e T11; client activity T12; lite wire-up T13; MVP proof T14; R2 bands T24, wired T27; final proof T25; docs T26 |
| Manifest status | planned (`routes/manifest/home.ts`); `fixture` with I-01-T05/T06; `live` with I-01-T13 behind `home.dashboard` |

Code to come (I-01 §5.1): `apps/web/src/routes/firm/home.tsx`, `src/screens/HOME-01/{index.tsx, scenarios.ts, copy.ts, HOME-01.test.tsx}`, `src/domain/home/{queries.ts, gateClasses.ts, messages.ts, HomeSegmented.tsx, WaitingOnYou.tsx}`, `src/fixtures/handlers/{home,human-gates}.ts`, `src/fixtures/seed/home.ts`. The legacy `src/home/WaitingOnYou.tsx` (TASK-102) is replaced, not extended.

## States

HOME-01 has 6 artboards (a, a2, f, g, h, i), 4 spec-only role states (b–e, DF-06: content from spec.md STATES and the TPL-11 frames) and 3 interaction states. Clocks are the artboards' "Rendered" times; E0 is Mon Sep 14, 2026, 9:24 AM CT (DEC-27). Tiers are I-01 §5.4's.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Parity tier | Status |
|---|---|---|---|---|---|---|
| a | daniel-reyes | Mon Sep 14, 2026, 9:24 AM CT | E0 | Daniel's open gates: 3 `decision`, 6 `sign_off_request`, 1 `final_approval`, 1 `send` → "Waiting on you 11" = 3 + 6 + 2; four tax tiles, Audits, Closes and Notices providers registered; 4 deadlines in 14 days; 6 activity items; 3 runs `running` | C report; **C lock before M8** (Fri May 28, 2027) | to build: fixture T05, screen T06/T11 |
| a2 | daniel-reyes | 9:24 AM | E0 | a, with the left pane scrolled to the bottom: To-dos 0 ("Nothing assigned"), Mentions 0 ("No new mentions") (R2), and "Your returns 6" (Daniel's 6 assigned tax work items; label rule in Copy) | C report; **C lock before M8** | to build: fixture T05; your-work band T11; R2 bands T24 (unwired), live T27 |
| b (spec-only) | margaret-okonkwo | 9:24 AM | E0 | 2 `decision` (Northwind and Granite Peak planning materiality) + 2 `send` (countersignatures E14 Granite Peak Sep 16, E11 Fairhaven Sep 18) → 4 = 2 + 2; your-work band "Your engagements" (4 assurance work items); R2 adds the empty To-dos and Mentions bands and "Open Today" | — (scenario test only, no artboard) | to build: fixture T05, composition T11 |
| c (spec-only) | samuel-ito | 9:24 AM | E0 | 0 `decision`, 4 `sign_off_request`, 2 `proposal` → summary "0 decisions · 4 sign-offs · 2 agent outputs" (6) | — (scenario test only) | to build: fixture T05, composition T11 |
| d (spec-only) | kevin-osei | 9:24 AM | E0 | No gate is Kevin's (staff); the left pane carries the your-work band "My work 4" (4 assigned work items) and no decision rows | — (scenario test only) | to build: fixture T05, composition T11 |
| e (spec-only) | grace-holloway | 9:24 AM | E0 | Firm admin (ADR-024, DEC-20): admin tile set from the `signatures_out`, `inbox_waiting`, `portal_invites_pending`, `binders` home counts; 2 `send` gates assigned to Grace (Send Form 8879-PE; Resend invite). Counts and metadata only | — (scenario test only) | to build: fixture T05, composition T11; tiles appear as N-02, N-01 register |
| f | daniel-reyes | 9:24 AM | E0 | `GET /v1/human-gates/counts` total 0 → left pane EmptyState | C report; **C lock before M8** | to build: T06 |
| g | daniel-reyes | 9:24 AM | E0 | `GET /v1/home` and the counts call pending → 9 px tile skeleton bars, 6 skeleton rows, `aria-busy` | C report; **C lock before M8** | to build: T06 |
| h | hannah-leclerc | Mon Sep 14, 2026, 12:40 PM CT | E0 | Left pane scrolled to the R2 bands: To-dos 0; Mentions 2 from Margaret Okonkwo (12:35 PM unread, 8:31 AM read). Gates and tiles are Hannah's own (see Open gaps) | C report; C lock at S35 (left-pane bands region) | to build: T24 (unwired, fixture only), live T27 |
| i | marcus-delaney | 12:40 PM CT | E0 | To-dos 1 (from Margaret, chip "Northwind · Exceptions row 6", due Sep 16); Mentions 0 | C report; C lock at S35 (left-pane bands region) | to build: T24, live T27 |
| office-denver (interaction) | daniel-reyes | 9:24 AM | E0 | Office chip set to Denver → every tile, band and list recomputes for `office_id`=Denver; chip amber-tint | — (scenario test; TPL-11f is F-05's specimen) | to build: T11 |
| tile-popover (interaction) | daniel-reyes | 9:24 AM | E0 | Hover or focus on a tile → 266 px popover with `by_office` from the same response | — (scenario test) | to build: T11 |
| today-brief-off (interaction) | daniel-reyes | 9:24 AM | E0 | `today_brief.enabled` off → no "Open Today →" after the date (the production default until I-02) | — (scenario test) | to build: T06 (slot), T24 |

Non-artboard states:

| State | Persona | Data condition | Rendering |
|---|---|---|---|
| Walled (`walled`) | lena-park | Lena is walled from Ashford | No Ashford tile contribution, gate, deadline, work item or activity row; the response has the shape of a firm without Ashford; an Ashford gate id answers 404 (INV-3, DEC-43) |
| Error | any | `/v1/home` or the counts call fails | F-05 error ViewState in the failed region with Retry; tiles and the queue fail independently |
| Flag off | any | `home.dashboard` off | the legacy landing (P-01's interim redirect) until T13; no HOME-01 data call |
| Provider missing | any | a home-count key is not registered | that tile or pill is absent, never faked; the row ends early on bare ground (AC3.1) |
| Shadow stage | any | the firm's agent stage is shadow (PW1, Jun 1 – Jul 12, 2027) | no `proposal` gate is projected or counted; human review gates still are (AC1.6) |
| Not allowed | client, agent, system or support principal | — | 403 on `/v1/home` and `/v1/human-gates*` (`home.read` deny, INV-1, INV-4); there is no portal route |

Personas: all eight exist in `apps/web/src/fixtures/seed/people.ts`; none is added for this screen.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/home?office_id=` | `HomeVM`: `greeting {first_name, date}` (from `kernel.clock`, firm time zone), `tiles[] {key, label, caption, total, by_status[{code, n, filter}], by_office[{office_id, n}], target}`, `your_work {label, rows[]}`, `deadlines {rows[], next}`, `client_activity[]` (first 20), `running_count`, `segments {deadlines, capacity, insights}` availability | `home.read` (new, I-01-T02; every firm role, OWN projection) | read-only screen; role shapes the tile set (admin: counts only) |
| read | `GET /v1/human-gates/counts?office_id=` | `{total, bands {decisions, sign_offs, agent_outputs, approvals_sends}, overdue, snoozed}` — **the one count source** for the pane header, the summary line and the Approvals badge | `human_gate.read` (P-04) | to-dos and mentions never counted |
| read | `GET /v1/human-gates?assignee=me&state=open&office_id=&sort=deadline` | rows with presentation facts (`title`, `context`, `due_on`, `risk`, `blocked {reason_code, facts}`, `subject_route`, `overlay`, `glyph`, `allowed_actions`) from the owners' resolvers | `human_gate.read` | HOME-01 renders no gate verb; a row only opens its host or HOME-02 |
| read | P-05 My to-dos and mentions (`P-05-T06`, `P-05-T09`) | to-do and mention rows | owners' | R2 bands h, i; behind P-05's flags |

Polling: 60 s and on focus; the running pill every 30 s while visible; `staleTime` 10 s (DEC-23; no SSE in I-01). The contract is `docs/contracts/home-and-gates.md` (C13 home half, I-01-T02).

## Status
- Tax tiles: `return` codes `prepared` "Prepared" (neutral), `in_review` "In review" (state), `action_required` with its `home_and_tax_tiles` context label "Issues" (red-tint), and "Ready" (green-tint; see Open gaps).
- Audits tile columns: `audit_engagement` `planning`, `fieldwork`, `in_review`, `ready_to_release`, `released` (captions "Planning", "Fieldwork", "In review", "Ready to release", "Released").
- Closes tile: `close` `in_progress` "In progress" (state). Notices tile: `notice` `received` "New" (red-tint micro pill "2 New").
- Your work and deadlines pills: `return` ("In review · Partner", "Ready", "Prepared", "In review · Manager", "Gathering"), `notice` `analyzing` "Analyzing", `envelope` `sent` "Sent".
- Due-chip risk tiers (computed by code on `kernel.clock`, AC2.2): red-tint ≤ 7 days, amber-tint ≤ 30 days, neutral beyond, each also stated in words. Gate state words "Open · Done · Snoozed until … · Voided" and the tier words arrive with I-01-T02's status-vocabulary rows.
- To-do rows: `todo` `open` (ring), due chip.

## Copy
Copy keys live in `screens/HOME-01/copy.ts` (screen) and `domain/home/messages.ts` (shared with HOME-02). Verbatim from spec.md and revision.md; templates in braces.

| Key | String |
|---|---|
| `subbar.greeting` | "Good morning, Daniel" (template `Good morning, {first_name}`; h and i read "Good afternoon, Hannah" / "Good afternoon, Marcus" at 12:40 PM: `Good afternoon, {first_name}`) |
| `subbar.date` | "Monday, September 14" |
| `subbar.openToday` | "Open Today" + "→" (R2; behind `today_brief.enabled`) |
| `segmented` | "My work" · "Approvals" + Count "11" · "Deadlines" · "Capacity" · "Insights" (R2, DF-39) |
| `subbar.office` | "Office │ All offices ⇕" (MapPin; set state shows the office name) |
| `subbar.running` | "3 running" (template `{n} running`) |
| `tiles.taxCaption` | "Tax returns · TY2025 · 79 open" (template `Tax returns · {tax_year} · {n} open`; Denver: "Denver · 64 returns", TPL-11f) |
| `tiles.tax` | 17 "Prepared" · 15 "In review" · 11 "Issues" · 7 "Ready" |
| `tiles.audits` | "Audits & assurance · 27" · 7 "Planning" · 9 "Fieldwork" · 6 "In review" · 2 "Ready to release" · 3 "Released" |
| `tiles.closes` | "11" + "In progress" + "of 22 · August 2026" |
| `tiles.notices` | "9" + "Notices open" + "2 New" |
| `tiles.admin` (e) | "Signatures out 17" · "Inbox waiting 23" · "Portal invites pending 2" · "Binders 241" |
| `pane.title` | "Waiting on you" |
| `pane.openQueue` | "Open queue →" |
| `pane.summary` | "3 decisions · 6 sign-offs · 2 approvals & sends · sorted by deadline" (c: "0 decisions · 4 sign-offs · 2 agent outputs"; summary rule: Decisions and Sign-offs always, Agent outputs and Approvals & sends when > 0, AC1.2) |
| `bands` | "Decisions" · "Sign-offs" · "Agent outputs" · "Approvals & sends" · "To-dos" · "Mentions" (R2) · your-work band (below) |
| `yourWork.label` | "Your returns" (all tax returns) · "Your engagements" (all assurance work items) · "My work" (staff and seniors) — inferred rule, AC4.2 |
| `bands.emptyTodos` | "Nothing assigned" |
| `bands.emptyMentions` | "No new mentions" |
| `mention.title` | "Margaret Okonkwo mentioned you" (template `{person} mentioned you`) |
| `todo.from` | "From Margaret Okonkwo" (template `From {person}`) |
| `empty.title` | "Nothing waiting on you." |
| `empty.body` | "Decisions, sign-offs and approvals that need you appear here." |
| `deadlines.title` | "Your deadlines · next 14 days" |
| `deadlines.calendar` | "Calendar →" |
| `deadlines.next` | "Next: Sep 30 · Calloway Family Trust · Form 1041 (extended)" (template `Next: {date} · {client} · {filing}`) |
| `activity.title` | "Client activity" |

**Rows of a (seed, verbatim).** Decisions: "§754 election — Ridgeline Property Partners, LP" / "6/30/2025 transfer to Pell Street II LLC · §743(b) placeholder 28,595 · Accrued Agent recommends filing without the election" / "Sep 15 · 1 day"; "CP2000 position — Marcus & Dana Whitley, TY2024" / "2 Forms 1099-INT not on the return: 1,870 + 1,250 = 3,120 · proposed tax 686.40 + interest 66.61 · recommended: agree" / "Sep 23 · 9 days"; "Acceptance — Estate of Walter Thornbury (Form 706 · estate Form 1041)" / "Pre-screened Sep 11 · Moderate risk · 3 flags · recommended: accept with conditions" / "Form 706 Nov 2 · 49 days". Sign-offs ("Partner sign-off — Ridgeline 2025 Form 1065 · {section}", all "Sep 15 · 1 day"): Summary & preparer memo / "Reviewed · SI ✓"; Financials (TB → TTB) / "AJE-1 18,500 · TJE-1 reclass 6,200 · Unmapped 0 · Reviewed · SI"; Schedule K / "Box 2 1,231,600 · box 5 18,400 · 18A 6,200 · 19A 600,000 · Reviewed · SI"; Capital Accounts / "M-2 ties · off 6,200 — fix proposed by Accrued Agent, awaiting Samuel Ito" (amber); Basis / "Pell Street II off 28,595 — §743(b) placeholder, needs decision 1" (amber); States & PTET / "IL 46.0% · CO 31.5% · NY 22.5% · PTET 28,044 / 17,070 / 18,982 · Reviewed · SI". Approvals & sends: "Final approval & export — Ridgeline 2025 Form 1065 (BH-TAX-02)" / "Unlocks after the 6 sign-offs → export to CCH Axcess → release 5 K-1s"; "Send Form 8879-PE — Harborview Dental Properties, LP" / "Ready · Synced Sep 11 · signer Dr. Sofia Lindqvist".

**a2 "Your returns 6".** "2025 Form 1065 · Ridgeline Property Partners, LP · In review · Partner"; "2025 Form 1065 · Harborview Dental Properties, LP · Ready"; "2025 Form 1041 · Calloway Family Trust · Prepared"; "2025 Form 1040 · Jonah & Claire Feld · In review · Manager" + tag "Draft K-1 · pre-release"; "2025 Form 1040 · Estate of Walter Thornbury · Gathering"; "CP2000 TY2024 · Marcus & Dana Whitley · Analyzing".

**Deadlines of a.** "Sep 15 · Ridgeline Property Partners, LP · Form 1065 (extended, Form 7004) · In review · Partner"; "Sep 15 · Harborview Dental Properties, LP · Form 8879-PE to send · Ready"; "Sep 23 · Marcus & Dana Whitley · CP2000 response, TY2024 · Analyzing"; "Sep 24 · Ridgeline Property Partners, LP · Engagement letter — cost segregation & §754 · Sent". The rule-derived filing labels are fixture content until T-08's `filing_deadlines` (AC4.1).

**Client activity of a.** "9:12 AM · Claire Feld emailed 2 health insurance forms" / "Waiting to be filed · Inbox"; "8:40 AM · You sent the engagement letter "Ridgeline cost segregation & §754 analysis" to Owen Calder" / "Envelope · due Sep 24"; "Sep 11 · Dana Whitley emailed "Re: estimated payments"" / "Filed to 2025 Binder"; "Sep 11 · Accrued Agent pre-screened the Estate of Walter Thornbury" / "3 flags · awaiting your decision"; "Sep 9 · Paul Thornbury uploaded the asset summary" / "New engagement intake · Estate of Walter Thornbury"; "Sep 9 · Eleanor Calloway uploaded the Harborline Trust Company custodial statements" / "Calloway 2025 Binder". Inbound mail and envelope rows are fixture content until S29 adds those sources (T23).

**b (Margaret, TPL-11 content).** "Planning materiality — Northwind Robotics 401(k) Plan, PY2025" / "Proposed v1 by Accrued Agent on unadjusted net assets $16,812,400: 1.0% = $168,100 or 1.5% = $252,200 (recommended). Blocking 3 workpapers." / "Blocked on a partner decision"; "Planning materiality — Granite Peak Outdoor Supply, Inc., FY2026" / "Proposed by Accrued Agent: 5% of pre-tax income $3,100,000 = $155,000 · PM $116,250 · CT $7,750" / "Blocked on a partner decision"; "Countersign engagement letter — FY2026 FS audit · Granite Peak Outdoor Supply" / "Luis Ferrante signed · your signature" / "Sep 16 · 2 days"; "Countersign engagement letter — PY2025 EBP audit · Fairhaven Foods 401(k) Plan" / "Sent Sep 8 to the plan administrator and to you" / "Sep 18 · 4 days". "Your engagements": Northwind Robotics 401(k) Plan · Planning · run "Processing" · PBC 11 of 24 · Granite Peak Outdoor Supply, Inc. · Planning · Fairhaven Foods 401(k) Plan · Planning · Arbor Senior Living 401(k) Plan · Fieldwork.

**c (Samuel).** Agent outputs: "Approve M-2 fix — add tax-exempt interest 6,200 as other increase (Ridgeline)"; "Approve treatment — Ridgeline K-1 box 2 passive (Feld 1040)" / "Prior-year treatment and the current K-1 support passive activity classification". Sign-offs: Feld 1040 Manager review (Review 37, Issues 4) · Calloway Trust Calculation DNI 400,000 · Calloway Instrument interpretation · Ridgeline Capital Accounts re-review after the M-2 fix.

**d (Kevin) "My work 4".** Feld 1040 In review · Manager (Issues 4) · Whitley CP2000 Analyzing (respond by Sep 23) · Sunil & Asha Rao 1040 Filed (transmitted Sep 11) · acknowledgment pending · Feld · 2 attachments waiting in Inbox.

**e (Grace).** Tiles as `tiles.admin`; "Portal invites pending 2" covers Summit Plan Administrators and Paul Thornbury. Queue: "Send Form 8879-PE — Harborview" · "Resend invite — Summit Plan Administrators (expires Sep 24)".

**h (Hannah).** "Margaret Okonkwo mentioned you" / "'this cutoff item drives AJE-1 — show it as factual on the SUM.' · Northwind · Exceptions row 3" / "12:35 PM" (unread dot); "Margaret Okonkwo mentioned you" / "'did the bridge letter request go to Keystone for Oct–Dec 2025?' · AUD-03 Source Documents" / "8:31 AM".

**i (Marcus).** "Request opt-out elections for the 4 auto-enrolled participants" / "From Margaret Okonkwo" / chip "Northwind · Exceptions row 6" / due chip "Sep 16".

Undesigned strings (no handoff source; added by T06/T11 and marked as such in `copy.ts`): the accessible badge name "Approvals, 11 waiting" (I-01 §5.5), the due-tier words ("due in 1 day"), the blocked words ("Blocked: off 6,200"), the popover's office rows.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Segmented "Approvals" / "Open queue →" / any Waiting-on-you row (flag on) | HOME-02 (`/home/approvals?gate=`) | the segment is wired (DEC-1273; HOME-02 answers its flag-off state while `home.approvals` is off); "Open queue →" and the rows wait for I-01-T21 |
| Waiting-on-you rows, flag off (AC2.4) | AUD-03 (evidence review on a PBC list), CLI-07 (acceptance), CLI-08 (independence, EQR eligibility), BND-02 (uploads awaiting review on a binder), the follow-up drafts screen (sends) | live from I-01-T13 (DEC-803): AUD-03 and BND-02 through `subject_route`, CLI-07 and CLI-08 by the gate's ids; sends stay text until their host is built |
| Decision 1 / Decision 3 / sign-off rows / row 10 / row 11 (HOME-02 interactions) | SHL-11 inline · CLI-07 · SHL-12 over TXP-01 · SHL-12 final approval · SIG-01 "To send" | through HOME-02; tax hosts fixture-only until T-04/T-05 |
| Segmented "Deadlines" / "Calendar →" | HOME-03 | planned → T-08; hidden in production |
| Segmented "Capacity" | HOME-04 | planned → I-04; hidden in production |
| Segmented "Insights" | INS-01 | planned → I-03, behind the `insights` entitlement; hidden in production |
| "Open Today →" | HOME-05 | planned → I-02, behind `today_brief.enabled` |
| Tax tiles (Issues filters to Action required) | TAX-01 filtered by status | wired (DEC-1273): `?tile=<status>`; a tile with an office breakdown opens it from its popover's All offices line |
| Audits columns | AUD-01 filtered by phase | per manifest (A-01) |
| Closes tile / Notices tile | CLS-01 / NOT-01 | planned (C-01 S51 / N-04 S29) |
| "3 running" | WB-01 filtered to running | planned → W-02 (S42) |
| Deadline rows | TAX-02 · SIG-01 · NOT-02 | planned |
| Activity rows | INB-01 · SIG-01 · CLI-07 · BND-02 | per manifest |
| To-do row / mention row | SHL-17 / SHL-18 (thread on its object) | planned → P-05 |

Inbound: SHL-06 (after sign-in), SHL-01 "Home", SHL-02 palette, and HOME-02/03/04 "My work". Production hides planned targets (chapter 04 §2.1 rule 4); fixture and dev builds show them for parity, with "Not built yet" on activation.

## Acceptance
- HOME-01 acceptance: tax tiles are 120 × 99, radius 14, 22/400 numerals, pills Prepared 17 · In review 15 · Issues 11 · Ready 7 in neutral / amber / red-tint / green-tint.
- HOME-01 acceptance: the counts tie to 01 §9.5: 17 + 15 + 11 + 7 = 50 of the 79 open; audits 7 + 9 + 6 + 2 + 3 = 27; closes 11 of 22; notices 9 with 2 New.
- HOME-01 acceptance: Waiting on you 11 = 3 + 6 + 2, and every sign-off row is a Ridgeline section due Sep 15.
- HOME-01 acceptance: the Ridgeline figures foot: K box 2 1,231,600; PTET 566,536 × 4.95% = 28,044, 387,954 × 4.40% = 17,070, 277,110 × 6.85% = 18,982; the apportionment adds to 1,231,600.
- HOME-01 acceptance: Whitley 1,870 + 1,250 = 3,120 and 22% × 3,120 = 686.40.
- HOME-01 acceptance: the agent only "recommends" or "proposes"; Daniel decides, signs and sends.
- HOME-01 acceptance: the greeting (20 px) and the tile numerals (22 px) are the only text above 15 px; the Office chip is the split filter chip.
- HOME-01 acceptance: the toolbar is SHL-01 with Home active, "Workbench" and "Brightwater Hale".
- HOME-01 acceptance (R2): the Home segmented reads My work · Approvals 11 · Deadlines · Capacity · Insights.
- HOME-01 acceptance (R2): "Open Today" sits after the date and opens HOME-05 with identical counts.
- HOME-01 acceptance (R2): To-dos and Mentions follow Approvals & sends; Daniel's read 0; the 11 is unchanged.
- HOME-01 acceptance (R2): Margaret's state b still shows its 4 items (2 materiality decisions, 2 countersignatures) with the same counts.
- HOME-01 acceptance (R2): frames h and i use only seeded mentions and to-dos.
- I-01 AC1.1/AC1.4: the pane header, the summary and the Approvals badge come from one counts call and equal SHL-04's Approvals tab.
- I-01 AC5.1: Grace's variant opens nothing outside ADR-024's metadata.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Tax tiles | 17 + 15 + 11 + 7 = 50 of 79 open (79 = 2 + 8 + 9 + 17 + 15 + 11 + 7 + 10; 224 = 79 + 145) | T05 seed footing test |
| Audits | 7 + 9 + 6 + 2 + 3 = 27 | T05 |
| Closes | 11 of 22 (22 = 3 + 11 + 5 + 3) | T05 |
| Notices | 9 open, 2 New | T05 |
| Waiting on you (a) | 11 = 3 + 6 + 2 | T05; count equality T25 |
| Margaret (b) | 4 = 2 + 2 | T05 |
| Samuel (c) | 6 = 0 + 4 + 2 | T05 |
| Kevin (d) / Grace (e) | My work 4 (4 rows) / queue 2 (2 rows) | T05 |
| Your returns (a2) | 6 rows | T05 |
| Schedule K / States & PTET | 1,231,600 × 46.0% = 566,536; × 31.5% = 387,954; × 22.5% = 277,110; 566,536 + 387,954 + 277,110 = 1,231,600; PTET 566,536 × 4.95% = 28,044; 387,954 × 4.40% = 17,070; 277,110 × 6.85% = 18,982 (rounded to the dollar) | T05 |
| Ridgeline cross-ties | box 2 1,231,600 + box 5 18,400 = 1,250,000 (HOME-02c income); 18A 6,200 = TJE-1 reclass 6,200 = M-2 off 6,200; 19A 600,000 = HOME-02c distributions | T05 with HOME-02's T15 |
| Basis row | 28,595 = HOME-02's 17,943,095 − 17,914,500 | T15 |
| Whitley | 1,870 + 1,250 = 3,120; 22% × 3,120 = 686.40 (interest 66.61 is drawn, not derived) | T05 |
| Materiality (b) | 1.0% × 16,812,400 = 168,124 → 168,100; 1.5% → 252,186 → 252,200 (rounded to 100); Granite Peak 5% × 3,100,000 = 155,000; 155,000 × 75% = 116,250; 155,000 × 5% = 7,750 | T05 (TPL-11 checklist) |
| Mentions (h) / To-dos (i) | 2 (1 unread) / 1; neither counted into any gate count | T24 |

## AVOID
Each becomes a test in `HOME-01.test.tsx` ("HOME-01 avoid: …"): gradients in product UI, emoji, saturated blue SaaS accents, heavy shadows, invented colors, lorem ipsum, KPI numerals above 22px, donut or gauge charts, colored tile backgrounds, 600/700 weights, the words Accrual/Arc/ACME, the agent "approving" anything; (R2) changing tile counts or rows, to-dos or mentions counted into the 11, a new nav item, blue, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | b–e are spec-only: compositions of a's grammar with TPL-11's content (b reuses TPL-11a; d and e follow spec.md STATES over TPL-11c/d), scenario-tested, not pixel-compared | No artboard; DF-06 | DEC-403 |
| DV-2 | Production hides the planned segments (Deadlines, Capacity, Insights), "Open Today →" and planned row targets; fixtures show them for parity | Chapter 04 §2.1 rule 4; DF-39 | DEC-403 |
| DV-3 | With `home.approvals` off (MVP, through Nov 2027) a row opens its host gate (AUD-03, CLI-07, CLI-08, BND-02, follow-up drafts), not HOME-02 | HOME-02 ships after P-04's UI (AC2.4) | I-01 §3 F2 |
| DV-4 | A tile exists only for a registered provider: Audits from S11, Tax from T-02 (tax-pilot firms), Notices from N-04 (S29), Closes from C-01 (S51); admin tiles as N-02 and N-01 register | Never fake a count (AC3.1) | I-01 §2.1 |
| DV-5 | The running pill counts runs with `status = running` and no `queued_reason`: a run dispatched at 9:24:00 and still queued reads "3 running" until 9:25 ("4 running") | AC3.4 | I-01 §3 F3 |
| DV-6 | The R2 bands (To-dos, Mentions) are built unwired in S35 and wired after Apr 20, 2028 (T27) | Busy-season freeze, P-29 rule 2 | I-01 §2, DEC-68 |
| DV-7 | Tax content (Daniel's gates, deadlines and returns) is fixture-only until T-02, T-04 and T-05 register their subkinds; the live analog is the audit half | Owning epics | I-01 §2.1, R5 |
| DV-8 | Toolbar overflow (Signatures under More ⌄ at ≤ 1440, as every artboard draws) is P-01's | DF-39, DEC-131 | DEC-131 |

N's sign-off of these deviations at Contract Monday (Mon Mar 8, 2027) is a solo-edition formality: decided and recorded as DEC-403 (`docs/plan/AMENDMENT-solo.md` items 1, 2, 7).

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, a2, f, g | C (report every build; lock before M8, Fri May 28, 2027) | not run (unbuilt) | `data-contrast="reference"` (DEC-11); masks: the running-pill spinner |
| h, i | C (report; lock at S35) | not run | compare the left pane's To-dos and Mentions bands; tiles, badge, deadlines and activity masked (Open gaps) |
| b, c, d, e | — | — | spec-only: scenario tests, no pixel compare |
| office-denver, tile-popover, today-brief-off, walled | — | — | scenario tests |
| host | D (blocking through T11) | — | toolbar 46, subbar 42, tile 120 × 99 r14, Audits tile 360, pane header 46 with a 14.5/500 title, band 31, row 44, right column 420, gutter 10, edge 12 |

Axe AA: 0 serious or critical findings in every scenario; minimum width 1280 (DEC-15).

## Open gaps
- **a2's capture.** The a2 screenshot shows the pane from its top (each artboard is captured in the state it opens in); the below-the-fold bands come from spec.md ("Your returns 6", 38 h rows) and revision.md item 3. Band order, decided: Decisions · Sign-offs · (Agent outputs) · Approvals & sends · To-dos · Mentions, then the your-work band.
- **h and i frames reuse Daniel's data.** Both draw Daniel's tiles, "Approvals 11", deadlines and activity (including "You sent the engagement letter … to Owen Calder") beside Hannah's and Marcus's bands. Decided: the scenarios load Hannah's and Marcus's own E0 sets; Tier C compares only the R2 bands region. The h frame's pane header also omits the count.
- **"Ready" tile word.** `return` has no code labelled "Ready" (the seed's "Ready 7"; `action_required` carries a `home_and_tax_tiles` label "Issues"). Decided: I-01-T02 adds the tile context label on the code the seed counts as Ready (`approved`), with the status-vocabulary rows it already owns.
- **Kevin's (d) and Grace's (e) counts.** The handoff draws no header count or summary for d and e. Decided (inferred): d's gate count is 0 with the summary rule applied and "My work 4" in the pane; e's is 2 (two `send` gates) under Approvals & sends.
- **Row targets.** spec.md routes every row to HOME-02; I-01 AC2.4 routes rows to their host gate while `home.approvals` is off (DV-3).
- **TPL-11b vs HOME-01a.** TPL-11's Daniel frame (final approval, K-1 release, §754 letter) is F-05's specimen; HOME-01a is the production content and wins.
- **Grace's tiles.** "Signatures out" and "Inbox waiting" render only once N-02 and N-01 register their counts; until then e shows Portal invites pending and Binders (I-01 §1).
- **C13 slot name.** I-01 §4.3 says `review.register_gate_kind(subkind, resolver, gate_class)`; on `main` the C13 projection slot is `review.api.register_gate_source(GateSource)` (DEC-320) because `register_gate_kind` names the G1–G5 checks. I-01-T02/T04 extend `register_gate_source`.
