# POR-02 · Portal home

| Field | Value |
|---|---|
| Route and params | `/` in the portal entry (origin root, no `/client` prefix, DEC-59); `?scope=<scope id>` selects the scope, default the first full-client scope (P-08 §5.1). `beforeLoad` sends unauthenticated visitors to POR-01 `/sign-in?return=…`. Artboards: `/components/screens/POR-02?st=a…h` and `?st=M` |
| Template and host frame | T7 (F-05 `PortalLayout variant="split"`: rail 336 + main 1030) with `PortalToolbar`; T7-M (`variant="mobile"`, `MobileTabBar`) at 390 · `Wave 1 - Client Portal.dc.html#por02` |
| Surface | portal (white-labelled: the firm's mark, name and people; nowhere "Accrued") |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/POR-02 Portal home - Feld household/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-08 · contract P-08-T03; contract stub P-08-T01; stage projection P-08-T12; home read model P-08-T13; portal entry and shell data P-08-T07; data P-08-T08; a, b, c, f P-08-T15; d, e, g, h, M P-08-T23; parity and accessibility P-08-T27 |
| Manifest status | fixture (`routes/manifest/por.ts`): a, b, c, f built by P-08-T15 (TASK-989); d, e, g, h and M by P-08-T23 (TASK-1219); the portal route renders it for Home with `?scope=` and T7-M below 768 px |

Code to come (P-08 §5.2): `src/routes/portal/{root,home}.tsx`, `src/shell/portal/{PortalToolbarData,EntitySwitcher}.tsx`, `src/domain/portal/{queries,mutations,messages}.ts`, `src/screens/POR-02/{index.tsx, scenarios.ts, copy.ts, POR-02.test.tsx}`.

**White label (AGENTS frontend rule 7, DEC-01, ADR-133, DEC-59).** Portal code never renders "Accrued": not in copy, `title`, favicon, alt text, aria labels or bundle strings. The toolbar's mark and name come from `GET /v1/portal/branding`. Nothing on the page names the agent: files the agent or code matched read "Brightwater Hale sorted 37 of your files" (INV-5, DEC-19).

## States

Fixture scenarios (P-08-T08 and P-08-T23, `fixtures/scenarios/POR-02.ts`, data in `fixtures/seed/portal-home.ts`): a–h and M are written and footed (`fixtures/portal.foot.test.ts`: Upload 2 = Intake 2, 3 = 2 + 1, binder 19 of 21 with 37 sorted, Copperleaf 7 of 9, Tessellate 26 / 3 / Sep 12). g and h are fixture-only behind their entitlements. The screen is P-08-T15's (part 1) and P-08-T23's (part 2).

9 artboards in the handoff (a–f from spec.md; g and h from revision R2; M at 390), 9 built here.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | claire-feld (Claire Feld, taxpayer, Feld household) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Taxpayer grant on the Feld household scope; binder 19 of 21 with 37 sorted; 2 open client-visible requests; 3 open questions; nothing to sign; 2 deliverables; return at Review | built · fixture (T15) |
| b | claire-feld | **Mon Feb 2, 2026** (header "Monday, February 2") | E0 at Feb 2 | First visit: binder 0 of 21, engagement letter and two §7216 consent envelopes pending, `welcome_dismissed` false for the scope | built · fixture (T15) |
| c | claire-feld | Mon Sep 14, 2026, 9:24 AM CT | E0 | Every open item done: no open to-dos of live kinds (`all_done`) | built · fixture (T15) |
| d | tess-moreno (Tess Moreno, Owner, Copperleaf Coffee Roasters, Inc.) | same | E0 | Entity owner grant: Approvals in the nav; 2 open requests, one due Sep 5 (derived overdue); close requests 7 of 9; TY2025 Form 1120-S filed and accepted | built · fixture (T23) |
| e | meera-shah (Meera Shah, role union) | same | E0 | Taxpayer grant on her own 1040 + K-1 recipient grant on Ridgeline; K-1 package below `released` | built · fixture (T23) |
| f | claire-feld | same | E0 | `GET /v1/portal/home` never answers (`never()` handler) | built · fixture (T15) |
| g | luis-ferrante (Luis Ferrante, CFO, Granite Peak Outdoor Supply) | **Thu Oct 22, 2026, 8:30 AM CT** | E0 at Oct 22 | `statements_studio` entitlement; draft FY2026 statements shared for co-review by Hannah Leclerc on Oct 21 | built · fixture only (T23; data source A-10 with R-02) |
| h | marisol-vega (Marisol Vega, Tessellate Health Cloud) | Mon Sep 14, 2026, 9:24 AM CT | E0 | `attest` entitlement; 26 open control requests synced with Drata; 3 exceptions; system description approved Sep 12 | built · fixture only (T23; data source X-01) |
| M | claire-feld | Mon Sep 14, 2026, 9:24 AM CT | E0 | Viewport 390 × 844; badges Documents 2 · Messages 1 | built · fixture (T23) |

Personas not yet in the TS seed (`tess-moreno`, `marisol-vega`, and any of `luis-ferrante` the seed lacks) are added by P-08-T08; `claire-feld` and `meera-shah` exist.

Non-artboard states (data conditions, never an `st` prop):

| State | Data condition | Rendering |
|---|---|---|
| Error | `GET /v1/portal/home` fails | F-05 C-20 `ErrorRow` |
| Scope not found | `?scope=` names a scope the user holds no grant on: `404` | not-found (same as any unknown id; INV-4) |
| No active grant | signed in, no active full-client grant | C-20 `EmptyState` naming the branding support contact (copy key `empty.noGrant`; string written by T15, see Open gaps) |
| Third party only | `GET /v1/portal/home` answers `404` for Sam Ortiz | the SPA lands on POR-14 (`/requests`), never POR-02 |
| Flag off | `portal.home_v2` false | legacy `ClientHome.tsx` |
| Production, planned source | a to-do kind, card or nav item whose source is `planned` | hidden in production, rendered in fixture builds (P-08 §2.2) |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/me` (extended) | `portal: {shell, scopes[{kind, id, label, role_label}], nav[], landing}`, `mfa: {enrolled, required, trusted_until}` | `SELF` (existing) | nav includes Approvals only for entity scopes (DEC-129) |
| read | `GET /v1/portal/home?scope_id=` | `PortalHomeOut`: `scope`, `todos[{kind, count, state ∈ open\|none\|overdue, due_date?, facts, target}]`, `work_cards[{work_item_id, kind, title, sub, pill {code, variant}, stages[{code, state, facts}], note_code?}]`, `binder {done, total, sorted_count}`, `team[{user_id, display_name, role_code}]`, `earlier[]`, `my_k1s[]`, `recent_threads[]`, `notices_info[]`, `first_visit`, `welcome_dismissed`, `all_done`; every field classified; no firm status code, amount, materiality, agent name or confidence | `portal.home.read` · `scope_only` | full-client roles on the scope; third party, agent and system deny |
| write | `PUT /v1/portal/preferences {scope_id, welcome_dismissed, version}` | Per user and scope; `409` on version mismatch; audits `portal_preferences.updated` | `portal.preferences.update` · self | the signed-in user only |
| read | `GET /v1/portal/branding` | Public branding (POR-01) | none · P-45 exception | — |

Words come from the frontend copy registry keyed by codes (ADR P-36 code → words); `title` and `sub` are the work item's client-safe display fields. Every aggregate is filtered by the grant that covers its own target scope, so role union never leaks one scope into another (INV-4).

## Status
Status objects shown, from `docs/product/status-vocabulary.yaml`, always in their `client_label` wording:
- `request` `overdue` (derived, never stored; red-tint) — the d pill "Overdue · due Sep 5", the only red on the page.
- `k1_package` `not_prepared` / `draft` → client label "Not released yet" (neutral pill, e). The firm label "Draft K-1 · pre-release" never reaches the portal.
- Work-item stages come from `modules/portal/stages.py` over the C2 canonical code (P-08-T12): StageTracker discs done (olive ✓) · current (half disc) · upcoming (ring); pills are state (amber tint) for in-flight and green-tint for "Filed and accepted". The pill words below are client stage labels, never firm statuses ("In review · Manager").

## Copy
Copy keys live in `screens/POR-02/copy.ts`; every string below is verbatim from spec.md, revision.md and the built artboards. Names, counts and dates are data from the Brightwater Hale seed (P-08-T08), shown as they render.

Chrome and fixed strings:

| Key | String |
|---|---|
| `nav` | "Home" · "Documents" · "Questions" · "Approvals" (entity scopes only) · "Sign" · "Messages" · "Deliverables" |
| `rail.title` | "Your team" |
| `rail.recent` | "Recent messages" |
| `rail.account` | "Account & people" |
| `greeting` | "Good morning, Claire" (template `Good morning, {first_name}`) |
| `date` | "Monday, September 14" (template from `useNow`) |
| `todo.goDocuments` | "Go to Documents →" |
| `todo.goQuestions` | "Go to Questions →" |
| `todo.goDeliverables` | "Go to Deliverables →" |
| `todo.goSign` | "Go to Sign →" |
| `todo.goConnections` | "Go to Connections →" |
| `todo.goApprovals` | "Go to Approvals →" |
| `todo.upload` | "Upload 2 documents" (template `Upload {n} document(s)`) |
| `todo.answer` | "Answer 3 questions" (template `Answer {n} question(s)`) |
| `todo.nothingToSign` | "Nothing to sign yet" / "Your Form 8879 comes after our review." |
| `todo.ready` | "2 documents ready" (template `{n} documents ready`) |
| `todo.nothingToApprove` | "Nothing to approve yet" / "Your August statements come to Approvals after our review." |
| `todo.reconnect` | "Reconnect American Express" / "We can't bring in your August card activity until it's reconnected." |
| `todo.reviewStatements` | "Review your FY2026 financial statements" / "Shared by Hannah Leclerc on Oct 21 · suggest edits or comment on any page" (R2) |
| `todo.controlRequests` | "Answer control requests" / "26 open requests · synced with Drata" (R2) |
| `todo.exceptions` | "Respond to 3 exceptions" / "CC6.2 · CC8.1 · A1.2 — tell us what changed" (R2) |
| `todo.descriptionApproved` | "System description approved" / "Approved Sep 12" (R2) |
| `pill.overdue` | "Overdue · due Sep 5" (template `Overdue · due {date}`) |
| `binder.title` | "Documents" |
| `binder.line` | "19 of 21 requests done · Brightwater Hale sorted 37 of your files" (b: "0 of 21 requests done") |
| `binder.open` | "Open binder" |
| `earlier.title` | "Earlier" |
| `earlier.view` | "View" |
| `myK1s.title` | "My K-1s" |
| `myK1s.expected` | "Expected by Sep 15 · you'll get an email" |
| `welcome.title` | "Welcome to Brightwater Hale's client portal." |
| `welcome.body` | "Drop documents, answer questions and sign here — your team sees everything you send." |
| `welcome.dismiss` | aria "Dismiss welcome" |
| `allSet.title` | "You're all set for now." |
| `allSet.body` | "We'll email you when your return is ready to sign." |
| `mobile.team` | "4 people · Message Kevin" |
| `mobile.more` | "More" |

Work-card stage labels and pills (client stage codes → words):

| Work item kind | Stages | Pills |
|---|---|---|
| Tax return (1040) | "Gather documents" · "Prepare" · "Review" · "Sign Form 8879" · "File" | "We're getting started" (b) · "We're preparing your return" (e) · "We're reviewing your return" (a) |
| Close | "Requests" ("7 of 9") · "Reconcile" · "Review" · "Statements" | "We're reconciling your accounts" (d) |
| Filed return | — | "Filed and accepted" (d, green-tint) |
| Financial statement audit | "Planning" · "Fieldwork" · "Statements review" · "Report" | "We're finishing your audit" (g) |
| SOC 2 | "Scoping" · "System description" · "Testing" · "Exceptions" · "Report" | "Testing is under way" (h) |

Per-artboard data (seed rows, P-08-T08; verbatim from the artboards):
- **a** household card "Jonah & Claire Feld" / "Household · Brooklyn, NY"; team Daniel Reyes "Partner — signs your return" · Samuel Ito "Manager — reviews your return" · Kevin Osei "Preparer — your day-to-day contact" · Grace Holloway "Client service"; recent "A question about digital assets" / "Kevin Osei · Sep 11" (unread dot) · "Your 2025 return — what happens next" / "Grace Holloway · Sep 1"; to-do lines "Form 1095-C and your 2025 estimated payment confirmations" · "2 in your 2025 organizer · 1 from Kevin Osei" · "Your 2025 extension confirmation and signed engagement letter"; work card "2025 Tax Return · Form 1040" / "Extended to Oct 15, 2026"; note "We're waiting on one partnership K-1 (Ridgeline Property Partners, LP). Brightwater Hale prepares it — nothing for you to do. Expected by Sep 15."; Earlier "2025 extension (Form 4868) filed · Apr 14, 2026" · "Engagement letter and §7216 consents (use · AI disclosure) signed · Feb 2, 2026" · "2024 Form 1040 filed and accepted".
- **b** to-dos "Sign your engagement letter and two §7216 consents" / "Read and sign before we start on your 2025 return." · "Upload your 2025 documents (21 requested)" / "Drop files in your 2025 binder and they're sorted for you."; work card "Due Apr 15, 2026"; recent "Welcome to your client portal" / "Grace Holloway · Feb 2"; Earlier "2024 Form 1040 filed and accepted".
- **d** household card "Copperleaf Coffee Roasters, Inc." / "S corporation · Colorado"; team Priya Raman "Partner" · Raj Malhotra "Your close preparer" · Grace Holloway "Client service"; to-dos "Upload 2 documents for the August close" / "Requested by Raj Malhotra for your August books." · "Answer 3 questions" / "About August transactions, from Raj Malhotra"; work cards "August 2026 Close" / "Monthly bookkeeping" and "TY2025 Form 1120-S" / "2025 S corporation return"; info row "Colorado Department of Revenue notice (2025 withholding) — Brightwater Hale is reviewing it. Nothing needed from you."; recent "Questions about August transactions" / "Raj Malhotra · Sep 11" · "Reconnect your American Express card" / "Raj Malhotra · Sep 8".
- **e** card "Meera Shah" / "Individual"; team Neil Ashcroft "Partner" · Lena Park "Preparer" · Grace Holloway "Client service"; to-dos "Upload 1 document" / "Your 2025 business mileage log for your consulting work (Schedule C)" · "Answer 1 question" / "From Lena Park"; note "Waiting on your K-1 from Ridgeline Property Partners, LP."; My K-1s row "Ridgeline Property Partners, LP · 2025 Schedule K-1"; recent "One question about your 2025 return" / "Lena Park · Sep 11".
- **g** work card "FY2026 Financial Statement Audit"; team Margaret Okonkwo "Engagement partner" · Hannah Leclerc "Manager" · Simone Baptiste "Your day-to-day contact".
- **h** card "Tessellate Health Cloud, Inc." / "Service organization · Denver, CO"; work card "SOC 2 Type 2 · Oct 1, 2025 – Sep 30, 2026" / "Security · Availability · Confidentiality"; team Celia Marsh "Engagement partner" · Laura Kemp "Manager" · Jasper Bell "Your day-to-day contact"; recent "Exceptions from testing" / "Laura Kemp · Sep 14".

Accessibility labels (P-08 §5.6): the tracker is an ordered list with `aria-current="step"` and disc labels "Done", "In progress", "Not started"; count badges read "Documents, 2 to do".

Copy bans on this screen (P-08-T04 glossary rows, L2/L7): never "Accrued", "password", "task" for a to-do, an agent name, a firm status word ("In review · Manager", "Draft K-1 · pre-release"), materiality, an amount, a control result or a deviation rate.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Go to Documents →", "Open binder", binder progress, nav Documents | POR-03 `to.POR03()` (a: opens POR-03a) | planned (R-01; until then `/documents` renders legacy `ClientEngagement.tsx`, P-08 §2.2) |
| A request to-do row (overdue d) | POR-04 | planned (R-01) |
| "Go to Questions →", nav Questions | POR-05 | planned (T-02) |
| "Go to Sign →" (b), nav Sign | POR-06 | planned (N-02) |
| Team MessageCircle (new thread to that person), Recent messages rows, nav Messages | POR-07 | planned (N-03) |
| Nav Approvals (entity scopes), "Go to Approvals →" (h, inside POR-21) | POR-08 | planned (R-02) |
| "Go to Deliverables →", "Review your FY2026 financial statements" (g co-review), My K-1s row (e), work card (deliverables), nav Deliverables | POR-09 | planned (R-02; My K-1s T-02) |
| User menu "Billing & payments" | POR-10 | planned |
| Close request to-dos (d) | POR-11 | planned (C-01) |
| "Account & people", user menu "Account & people" | POR-12 | planned (N-03) |
| "Go to Connections →" (d), user menu "Connections" (entity clients) | POR-16 | planned (A-02) |
| "Answer control requests" / "Respond to 3 exceptions" (h) | POR-21 | planned (X-01) |
| User menu: switch scope (each scope with its role chip, for example "Feld Household · Taxpayer"), "Sign out" | the same screen with `?scope=`; POR-01 after sign-out | in-screen |
| Welcome card close (b) | `PUT /v1/portal/preferences` | in-screen |

Inbound: POR-01 (role-routed landing), every POR-20 email CTA, POR-12, CLI-04 "rendered as a contact", ADM-10 preview, TPL-15, mobile tab "Home". In fixture builds a `planned` target renders "Not built yet"; in production a control whose target or source is `planned` is hidden (P-08 §2.2). All targets are manifest IDs that `link-contract.test.ts` knows, and every designed link of POR-02 in `handoff-links.json` (POR-03, 05, 06, 07, 09, 10, 11, 12, 16, 21) is named above.

## Acceptance
- POR-02 acceptance: the toolbar matches `platform-portal.png` (brand left, icon nav centered, user pill right) with Brightwater Hale; Approvals hidden for the household, shown for Copperleaf.
- POR-02 acceptance: to-do counts tie: 2 documents (= Intake 2 on TAX-03 / TPL-07), 3 questions (2 organizer + 1 from Kevin, = POR-05), nothing to sign before review.
- POR-02 acceptance: the Ridgeline K-1 is described in plain words; the internal "Draft K-1 · pre-release" chip never appears.
- POR-02 acceptance: the stage tracker uses the canonical discs (olive ✓, half disc, ring); "We're reviewing" is amber state, never red.
- POR-02 acceptance: the role-union frame shows Meera's own 1040 plus a "My K-1s" card and nothing of the Ridgeline return itself.
- POR-02 acceptance: the overdue frame uses red-tint only on the past-due item; the 390 frame has the bottom tab bar with count badges.
- POR-02 acceptance (R2): states a–f are unchanged; the new to-do kinds use the existing card grammar.
- POR-02 acceptance (R2): state g matches J21 (draft shared Oct 21, 4:30 PM; Luis's co-review follows on Oct 23).
- POR-02 acceptance (R2): state h matches §9.5 (26 open requests, 3 exceptions, description approved Sep 12).
- POR-02 acceptance (R2): no control results or materiality reach the portal.
- P-08 Story 6.2: dismissing the welcome persists per user and scope and audits `portal_preferences.updated`.
- P-08 §1 / INV-4: Sam Ortiz's session gets `404` from `GET /v1/portal/home` and never reaches POR-02.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Upload 2 | = binder open client-visible requests = TAX-03 "Intake 2" | P-08-T08 footing test |
| Answer 3 | = 2 organizer + 1 from Kevin Osei (= POR-05) | same |
| Binder | 19 of 21 requests done; 37 sorted; bar 90 % | same |
| Binder (b) | 0 of 21 | same |
| Copperleaf close | Requests 7 of 9 | same |
| Meera's K-1 | "Not released yet" (package below `released`) | same |
| Tessellate (h) | 26 open requests; 3 exceptions; approved Sep 12 (§9.5) | X-01 slice; scenario test h |
| Badges (M) | Documents 2 · Messages 1 | scenario test M |

## AVOID
Each becomes a test in `POR-02.test.tsx` ("POR-02 avoid: …"): gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, KPI numbers above 22px, firm statuses ("In review · Manager", "Draft K-1 · pre-release"), agent mentions, red for anything that is not overdue, donut charts; from R2: firm statuses, control results, deviation rates or materiality on the portal, changing states a–f, blue, "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DEC-58(d) | No bell in the PortalToolbar; the client is reached by email plus the Home to-do list | No portal bell (amends SPEC-032 Q2); `ClientBell.tsx` is retired by F-05-T23 | decision-log DEC-58 |
| DEC-59 | Served at the origin root of `<slug>.<neutral-portal-domain>`; `/v1` same-origin; the host is a branding hint only; mark and name from branding | White label; X-12 | decision-log DEC-59; ADR P-11 (P-08-T30) |
| DEC-35 | No change on this screen; sign-out and expired sessions return to POR-01, whose link and lock rules are DEC-35's | Recorded for completeness of the epic's deviation set | decision-log DEC-35 |
| DF-17 | Not on this screen (the trusted-device and setup states live on POR-01) | — | P-08 §0.1 |
| DF-24 | Not on this screen | — | P-08 §0.1 |
| DF-03 | M is built from the POR-02-M frame; the bottom tab bar Home · Documents · Sign · Messages · More (DEC-45) replaces T7-M top pills | DEC-45 portal responsive scope | P-08 §0.1 DF-03 |
| — | b renders at Mon Feb 2, 2026 (its header reads "Monday, February 2"); the README's "Mon 14 Sep 2026" render label is canvas metadata | revision.md > spec > README (DEC-04/DEC-15) | P-08 §2.1 |
| — | g and h are gated by the `statements_studio` and `attest` entitlements, not flags, and stay fixture-only until A-10/R-02 and X-01 register their home sources | ADR P-28, DEC-55 | P-08 §0 |
| — | The catalogue's "progress ring" is superseded by the built 5-step StageTracker | The built screen reflects later decisions | P-08 §2.1 |
| — | Planned to-do kinds, cards and nav items are hidden in production and render in fixture builds | Chapter 04 §2.1 rule 4 | P-08 §2.2 |

### Part 1 notes (P-08-T15)
- The skeleton (f) and the error are drawn by the screen from tokens: the kit's ViewState module carries the firm's product words, which the portal bundle may not hold (DEC-196). Error strings: "Couldn’t load your home." · "We could not reach the server. Nothing was lost; try again in a moment." (the kit's portal line) · "Retry"; the skeleton's status label "Loading".
- A first visit's to-do cards read the request in full (`detail`) as the title, with b's line under it ("Read and sign before we start on your 2025 return." · "Drop files in your 2025 binder and they're sorted for you.").
- The greeting is the handoff's "Good morning, {first_name}" at every hour: no other greeting is designed (open gap).
- `PUT /v1/portal/preferences` needs a `version` the home does not carry: a scope never dismissed sends 0 (DEC-196).
- The scope switcher and the role chips are P-08-T23's (e).

### Part 2 notes (P-08-T23)
- The user chip opens the menu: each scope with its role label as the chip line, then the planned account links (fixture builds only) and Sign out. A full-client scope switches the home (`?scope=`); a K-1 recipient's scope opens POR-13 (planned) and never becomes a home (DEC-346).
- g's "Nothing to sign yet" line is the frame's "The representation letter comes after your review."; g's card lines "C corporation · Colorado" and "Year ended Jun 30, 2026" and every recent-message row come from the built frames.
- The to-do kinds reconnect, review_statements, control_requests, exceptions and description_approved are planned sources: fixture builds draw them, production hides them (Story 6.7).
- The 390 layout switches below 768 px. Badges: Documents = open upload to-dos; Messages = unread recent threads (planned, N-03).
- Household-card icon tiles (House, Building, person) are not drawn: the scope carries no household-or-individual kind (parity masks them, T27).

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C (threshold 0.20, maxDiffPixelRatio 3 %) | not run (unbuilt) | locked (blocking) at P-08 exit (T27); mask the skeleton pulse in f |
| g, h | C | not run | report-only (their sources are later epics) |
| M | C | not run | POR-02-M board uses the 940 × 1800 crop rule; locked at exit |
| host | D | — | toolbar 46, rail 336, main 1030, pane header 46 with a 14.5/500 title, TodoCard 243×116 r12, pill 21, StatusDisc 15, progress 3 px, tab bar 64 |

Tier B for T7 and T7-M is F-05's (F-05-T49).

## Open gaps
- **Spec vs built copy.** spec.md and the built artboards agree on every string listed; b's lines ("Read and sign before we start on your 2025 return.", "Due Apr 15, 2026", "We're getting started", "0 of 21 requests done") exist only in the built frame and are taken from it (the built screen reflects later decisions).
- **h nav.** The built h shows Approvals in the nav (entity scope, R2 links "Go to Approvals →"); R2 does not say it, the frame does: kept.
- **No-active-grant copy.** No handoff string exists for `empty.noGrant`; T15 writes it on the C-20 grammar, records it here and keeps it inside the copy bans.
- **OQ-5 "Your day-to-day contact".** Derived per work-item kind (tax preparer, close preparer, assurance senior in charge) by a code rule in `home_sources/identity.py`, decided before T13 (P-08 §11.2).
- **Questions count for Copperleaf (d).** "Answer 3 questions" on d comes from close transaction questions (POR-11, C-01), not the organizer; fixture-only until C-01 registers its source.
