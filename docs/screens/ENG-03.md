# ENG-03 · New engagement wizard

| Field | Value |
|---|---|
| Route and params | `/engagements/new` (O6 modal route over ENG-01; P-07 §5). Search params `client`, `entity`, `type` (prefill from CLI-01, CLI-02), `draft` (resume). `/engagements/new/ai` (ENG-14) is planned (K-04). Artboards: `/components/screens/ENG-03?st=a…h` |
| Template and host frame | O6 `Wizard` (O4 geometry, step list 220; F-05-T20) with the TPL-18 data-driven type catalogue and gate cards (F-05-T38) · `Wave 2 - Home & Records.dc.html` (ENG-03 section) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-03 New engagement wizard - Fairhaven Foods 401-k- Plan/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T01 · fixtures P-07-T11 · catalogue, drafts and create P-07-T16 · screen core P-07-T21 (a, b, c, d, f) · remaining types P-07-T34 (e, g, h) · parity lock P-07-T63 |
| Manifest status | planned (`routes/manifest/eng.ts`, path `/engagements/new`): a, b, c, d, f built on fixtures by P-07-T21 (TASK-990) behind `engagements.v2`; kept `planned` for CLI-02's reason (DEC-195) |

Code to come (P-07 §5): `src/screens/ENG-03/{index.tsx, scenarios.ts, copy.ts, ENG-03.test.tsx}`, `src/domain/engagements/{TypeCatalogue.ts, GateBlock.tsx, IndependenceChip.tsx, mutations.ts}`. Flag `engagements.v2`.

## States

8 artboards post-revision (a–f from spec.md; g, h from revision.md R2), 8 built here: 5 live in production, 3 fixture-only until their epic registers the target.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc (Hannah Leclerc, Audit Senior Manager) | Tue Sep 8, 2026, 9:40 AM CT | E0 − 6 days | Step 1, Fairhaven Foods, Inc. / Fairhaven Foods 401(k) Plan, EBP audit selected; continuance approved Aug 28 (G1 met); draft saved 9:39 AM | built · live (T21) |
| b | hannah-leclerc | same | same | Step 2: methodology BH Audit Methodology · EBP v3 pinned, §103(a)(3)(C) scope | built · live (T21) |
| c | hannah-leclerc | same | same | Step 4: five team rows, Fiona Nash's independence requested 9:38 AM and unconfirmed (G2 blocks Fiona only) | built · live (T21) |
| d | hannah-leclerc | Mon Aug 24, 2026, 10:05 AM CT | Aug 24 snapshot | Granite Peak Outdoor Supply, Inc., FS audit, no acceptance decision for this service and period: G1 unmet, Next disabled | built · live (T21) |
| e | hannah-leclerc | Mon Sep 14, 2026, 9:24 AM CT | E0 | Morgan & Kai Ferris, Form 1040: a duplicate TY2025 Form 1040 exists ("Create anyway" taken); §7216 consents 1 of 2 signed | built · fixture until T-01 (C19 consents) |
| f | hannah-leclerc | Tue Sep 8, 2026, 9:40 AM CT | E0 − 6 days | Step 1 with the pointer over the Single audit "Coming soon" tile: its tooltip shows | built · live (T21) |
| g | margaret-okonkwo (Margaret Okonkwo) | Mon Sep 14, 2026, 9:51 AM CT | E1 | Harlow & Pike Holdings, Inc., FS audit with Group audit (SAS 149) on; accepted Sep 9 with a condition; "Set up with AI…" hovered | built · fixture until A-09 (entitlement `group_audit`); "Set up with AI…" planned until K-04 |
| h | celia-marsh (Celia Marsh) | Mon May 11, 2026, 10:00 AM CT | E2 | Tessellate Health Cloud, Inc., SOC 2 selected; step 2 methodology "BH SOC 2 · TSC 2017 (rev. 2022) v1"; period Oct 1, 2025 – Sep 30, 2026 · Type 2 | built · fixture until X-01 (entitlement `attest`) |

Loading: the sheet's step body shows F-05 skeleton fieldsets while the catalogue and draft load. Not-allowed: a member without `engagement.create` never reaches the route ("+ New engagement" is hidden; a deep link renders C-20 not-allowed); the agent never creates an engagement. A walled client is not offered in the Client picker. Flag off: the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagement-types` | Catalogue: family, label, standard line, availability, entitlement, step schema. Tax 8 · Audit & assurance 8 · CAS & Advisory 2; never `single_audit` | `engagement.create` | partner, manager, seniors by `firm_setting(seniors_can_create)` (DEC-38) |
| write | `POST /v1/engagement-drafts` · `PATCH /v1/engagement-drafts/{id}` · `DELETE …` · `POST …/validate` | Autosave with `seen_version` ("Draft · saved 9:39 AM"); per-step validation; Escape → "Discard this draft?" → DELETE | `engagement.create` | own drafts only (OQ-17) |
| write | `POST /v1/engagement-drafts/{id}/start-acceptance` | d: "Start acceptance" saves the draft, creates a Prospect engagement and an acceptance record, opens CLI-07 | `client.intake` | firm_admin, partner, manager (OQ-2) |
| write | `POST /v1/engagement-drafts/{id}/create` | `{confirm_duplicate?}` → one unit of work: engagement (Accepted), work items by type cardinality, team and independence requests, methodology pin, `engagement.created`; `Idempotency-Key`; 409 `possible_duplicate`, 409 `gate_unmet` G1, 422 `unknown_engagement_type` (including `single_audit`) | `engagement.create` | as above; agent and system deny |

## Status
Step discs: current (half disc), to do (ring), done (olive ✓). Gate block discs: met ✓, not met ring. Independence chips: "✓ Confirmed" (green solid), "○ Requested {time}" (muted). Acceptance value "Continuance approved · {date} ✓" (green ink). The Coming soon badge is the `soon` pill.

## Copy
Copy keys live in `screens/ENG-03/copy.ts`; strings verbatim from spec.md and revision.md (revision wins).

| Key | String |
|---|---|
| `header.title` | "New engagement" |
| `header.saved` | "Draft · saved {time}" (a: "Draft · saved 9:39 AM") |
| `footer` | "Back" · "Save draft" · "Next" · "Create" · "Create & draft letter" |
| `steps` | "Client & type" · "Standards & methodology" · "Period & deadlines" · "Team & independence" · "Binder & portal" · "Letter & review" |
| `gates.g1` | "G1 Continuance approved — {person} · {date}" (a: "G1 Continuance approved — Margaret Okonkwo · Aug 28, 2026") |
| `gates.g2` | "G2 Team independence — step 4" |
| `gates.g3` | "G3 Letter signed — after Create" |
| `gates.g2Met` (g) | "G2 Team independence — all confirmed" |
| `gates.g2NotRequired` (e) | "G2 Independence — not required (non-attest)" |
| `stepByKind` (e; spec.md interactions) | step 2 reads "Return setup" for a tax return and "Close plan template" for Monthly close (fixture builds; planned until C-01) |
| `closePlan.hint` (DEC-345) | "Close plans arrive with closes (C-01)." (fixture builds only) |
| `toast.createFailed` (DEC-345) | "Couldn’t create the engagement." |
| `ai.title` (R2) | "Start from last year's files" |
| `ai.body` (R2) | "Attach prior statements, a component list or a draft letter; the agent proposes a plan you confirm." |
| `ai.action` (R2) | "Set up with AI…" |
| `card.client` | "Client"; keys "Client" · "Entity" · "Relationship" · "Acceptance" · "Proposal" · "Office" |
| `card.type` | "Engagement type"; groups "Tax" · "Audit & assurance" · "CAS & Advisory" (rendered uppercase) |
| `types.tax` | "Form 1040" "Individual" · "Form 1041" "Trust or estate" · "Form 1065" "Partnership" · "Form 1120-S" "S corporation" · "Form 1120" "C corporation" · "Form 990" "Exempt organization" · "Forms 706 / 709" "Estate & gift" · "Notice response" "IRS or state notice" |
| `types.assurance` | "EBP audit" "AU-C 703 · ERISA" · "FS audit" "GAAS nonissuer" · "Review" "AR-C 90" · "Compilation" "AR-C 80" · "Preparation" "AR-C 70" · "Agreed-upon procedures" "AT-C 215" · "SOC 1" "AT-C 320" · "SOC 2" "AT-C 205" (R2) |
| `types.cas` | "Monthly close" "Client accounting services" · "Advisory project" "Scoped project" |
| `comingSoon.singleAudit` | "Single audit" "Uniform Guidance" with badge "Coming soon" (static tile, never a catalogue type; D10) |
| `comingSoon.tooltip` (f, R2) | "Not in this release. Run single audits outside Accrued for now." |
| `card.name` | "Name"; keys "Engagement name" · "Display" |
| `groupAudit.label` (R2) | "Group audit (SAS 149)" |
| `groupAudit.helper` (R2) | "Adds the Group band (structure, scoping, component auditors) to the cockpit. SAS 149 applies to periods ending on or after Dec 15, 2026." |
| `card.standards` (b) | "Standards & methodology"; keys "Methodology" · "Standards set" · "Audit scope" · "Certification" · "Framework" · "Plan type" · "Form 5500 filer" |
| `scope.options` (b) | "§103(a)(3)(C)" · "Full scope" |
| `card.agentDefaults` (b) | "Agent defaults"; keys "Auto mode" · "PBC list" |
| `agentDefaults.autoHelper` (b) | "Firm policy: Auto mode off for audits." (see Deviations) |
| `card.team` (c) | "Team" |
| `team.confirmed` (c) | "✓ Confirmed" |
| `team.requested` (c) | "○ Requested {time}" ("○ Requested 9:38 AM") |
| `team.eqrEligible` (c) | "EQR eligible — not on team, no cooling-off conflict" |
| `team.g2Footer` (c) | "Fiona Nash cannot be assigned or sign off until she confirms independence (G2)." |
| `gate.g1Banner` (d) | "Acceptance is not approved yet (G1)." (see Deviations) |
| `gate.startAcceptance` (d) | "Start acceptance" |
| `duplicate.notice` (e) | "{type} already exists for {client} · Open it · Create anyway" ("TY2025 Form 1040 already exists for Morgan & Kai Ferris · Open it · Create anyway") |
| `consents.card` (e) | "§7216 consents" |
| `consents.helper` (e) | "Agents cannot read Ferris return information until both spouses sign." (see Deviations) |
| `discard.title` | "Discard this draft?" |
| `toast.created` | "Engagement created · {name}" ("Engagement created · PY2025 EBP Audit") |
| `advisory.proposal` | "Start from proposal ⇕" |

Picker values (clients, entities, relationship and acceptance lines, proposal "Accepted Sep 4 · $26,500 fixed ›", methodology chips, standards lines, team rows, g's acceptance condition, h's period) are seed data, never `copy.ts`. The catalogue's labels come from `GET /v1/engagement-types` and are held in the copy registry (OQ-15); only the Coming soon tile and its tooltip are static.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Create" ("Creates the engagement and opens ENG-02") | ENG-02 `to.ENG02({ engagementId })` | planned (P-07-T20) |
| "Create & draft letter" ("Creates the engagement and opens ENG-04") | ENG-04 | planned (N-02); the button is hidden in production until then |
| Acceptance row; d "Start acceptance" ("Opens CLI-07") | CLI-07 | planned (P-07-T46) |
| An independence chip ("Opens CLI-08 · independence and conflicts") | CLI-08 | planned (P-07-T48) |
| Proposal row; "Start from proposal ⇕" ("Opens ENG-09") | ENG-09 | planned (T-09); hidden in production |
| "Set up with AI…" ("Opens ENG-14 · Set up with AI") | ENG-14 | planned (K-04); the card is hidden in production |
| Step 5 "Binder template" preview after create ("Opens BND-02") | BND-02 | planned (P-06-T12) |
| Advisory project after create | PRJ-01 | planned (T-09) |
| The sheet's backdrop and close (×) | ENG-01 `to.ENG01()` (the host route) | planned (P-07-T27) |
| Type cards, Next and Back, "Save draft", Escape | the wizard's own steps and the discard Dialog (local) | in-screen |

Inbound: ENG-01 "+ New engagement", CLI-01 row "···" New engagement, CLI-02 "+ New engagement", SHL-02 "New engagement…", AUD-01, CLS-01, TAX-01, TAX-15. All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- ENG-03 acceptance: sheet geometry matches O6: inset 14, top 60, radius 14, #F8F8F6 body, white header and footer, 220 step list.
- ENG-03 acceptance: type cards borrow the arc-agents card grammar: 28–34px colored icon tile, 13.5/500 name, ink-3 line, badge top-right; "Coming soon" uses the soon badge, ink-4.
- ENG-03 acceptance (R2 over spec): AUP, SOC 1 and SOC 2 are selectable; only Single audit carries "Coming soon" and cannot be selected.
- ENG-03 acceptance: fieldset rows match agent-schedule: 33px band, 34px rows, ⇕ stepper glyphs, 38×22 olive toggle.
- ENG-03 acceptance: an EBP audit pins "BH Audit Methodology · EBP v3" and AU-C 703; §103(a)(3)(C) requires the certification; Auto mode is off by firm policy; the EQR is not on the engagement team.
- ENG-03 acceptance: G1 shows ✓ before Create; G2 blocks the pending person, not the engagement; a missing §7216 consent blocks agents only.
- ENG-03 acceptance (R2): step 1 opens with the Set up with AI card linking to ENG-14 (fixture build; hidden in production until K-04).
- ENG-03 acceptance (R2): the Group audit (SAS 149) toggle appears only with FS audit selected (and entitlement `group_audit`).
- ENG-03 acceptance (R2): frames g and h match J20 (Sep 14, 9:52 AM hand-off to ENG-14) and J25 (May 11, SOC 2 template).
- P-07 §3.6 Story 6.3: the catalogue never contains `single_audit` and a create with `type=single_audit` answers 422 `unknown_engagement_type`; d keeps Next disabled with the reason announced through `aria-describedby`; Escape asks "Discard this draft?"; a duplicate answers 409 `possible_duplicate` until `confirm_duplicate`; SOC cards are selectable only with entitlement `attest`.

## Figures
| Figure | Foots | Proven by |
|---|---|---|
| Catalogue | Tax 8 · Audit & assurance 8 selectable + 1 static Coming soon tile = the designed 9 · CAS & Advisory 2 | P-07-T14 (no `single_audit`), P-07-T21 scenario test |
| Steps | 6 steps; gate block G1–G3 | scenario test |
| Team (c) | 5 rows = 4 "✓ Confirmed" + 1 "○ Requested 9:38 AM" (Fiona Nash); EQR Celia Marsh not on the team | P-07-T11 seed test |
| Draft time (a) | "saved 9:39 AM" at a 9:40 AM clock | clock test |
| Consents (e) | "1 of 2 signed (Morgan ✓ · Kai ○)" | fixture test (T-01 owns consents) |

## AVOID
Gradients in product UI, emoji, saturated blue, heavy shadows, invented colors, lorem ipsum, native selects, bordered inputs, a horizontal progress bar stepper, making Coming-soon cards look clickable, the words Accrual/Arc/ACME. R2: making Single audit selectable; changing frames a–e; a horizontal progress stepper; blue; the agent creating an engagement without a person's confirm; "task" for a to-do. D10: any `single_audit` catalogue type, enum member or seed row.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D10 | Single audit is a static tile from `copy.ts`, not a catalogue type; the server knows no `single_audit` code | Scope guardrail (DEC-19, chapter 01 §1.7.1) | P-07 §2.1, §3.6 Story 6.3 |
| — | "Create & draft letter", the "Set up with AI" card, the Proposal row and "Start from proposal ⇕" are hidden in production until N-02, K-04 and T-09; "Create" is then the footer's primary button | Planned targets are hidden in production | P-07 §2.1 |
| — | d adds "Start acceptance" (save the draft, create a Prospect engagement and an acceptance record, open CLI-07) | DEC-39: Prospect engagements exist before acceptance | DEC-39; P-07 §3.6 Story 6.3 |
| — | Screen IDs in parentheses inside handoff strings ("…decision in CLI-07.", "(ADM-04)") are canvas cross-references, not product copy: `copy.ts` drops them and the reference becomes the link or action beside the string | Internal codes never show in product chrome (DF-22's rule for ENG-14 "A28"; ENG-02 "no internal engagement number") | DEC-138 |
| — | The CAS "Close plan template" step is planned until C-01 and the "PBC list — Build from template" toggle seeds requests deterministically from the pinned methodology (no agent run) | C-01 owns close plans; agents propose only | P-07 §2.1 |
| DEC-345 | Steps re-shape from the selected type's catalogue `steps` (field codes): standards set and the EQR only where the schema asks; the §103(a)(3)(C) scope only for EBP audit; SOC types show the period on step 2; step 2 reads "Return setup" for tax returns and, in fixture builds, "Close plan template" (with Approver of record on step 5) for Monthly close | spec.md "a type card click … re-shapes steps 2–6"; the catalogue serves the schema | DEC-345 |
| DEC-345 | e's §7216 consents card is fixture-only: the screen takes it as a `consents` prop that only the gallery passes; the route never does, so production draws no card until C19 serves consents | No consents API until T-01 (C19); data only through the generated client | DEC-345 |
| DEC-345 | e's duplicate notice shows when Create answers 409 `possible_duplicate` (with "Open it" to the named engagement and "Create anyway" sending `confirm_duplicate`), not on step 1 | The draft has no duplicate read before Create | DEC-345 |
| DEC-345 | "Set up with AI" card and "Start from proposal ⇕" render disabled with their hints in fixture builds only | ENG-14 (K-04) and ENG-09 (T-09) are planned | DEC-345 |

### Core notes and contract gaps (P-07-T21)
- The G1 reason is the gate card's status region; Next is disabled while G1 is unmet (DEC-197).
- Discard dialog: title "Discard this draft?", buttons "Discard" · "Keep editing" (written for this task). Save failure toast: "Couldn’t save the draft."
- Gaps, drawn as the draft's facts or "—" until P-07-T16's step schemas and a methodology read: the methodology chip and its version line, the independence request time, the Relationship, Proposal and Office rows, the Display line, the Agent defaults card, and the editors of steps 3, 5 and 6 (DEC-197).
- Fixture names follow the handoff: client "Fairhaven Foods, Inc.", entity "Fairhaven Foods 401(k) Plan" (the TS seed names the client after the plan; open gap for F-04-T31's exported seed).

- P-07-T34 gaps (DEC-345): g and h's G1 line reads "Acceptance approved" in the handoff; the draft's gate does not say whether G1 was an acceptance or a continuance, so the line keeps "Continuance approved"; the methodology row reads "—" until a methodology read exists (h's "BH SOC 2 · TSC 2017 (rev. 2022) v1"); h's "Categories" row and e's Binder card are not in the draft; a coming-soon SOC card (no `attest`) shows the kit's one soon tooltip, which names single audits.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d, f | C (locked before M8) | not run (unbuilt) | P0 lock at Tier C (T63) on the fixture build (the Set up with AI card shows there); mask the tooltip region's timing in f |
| e, g, h | C (report) | not run | fixture only (T-01, A-09, X-01) |
| host | D | — | sheet inset 14, top 60, radius 14; header 46; footer 56; step list 220 with rows 38; fieldset band 33, rows 34; TypeCards 172×76 |

## Open gaps
- spec.md lists three Coming soon cards and an older tooltip naming AUP and SOC; revision.md R2 makes AUP, SOC 1 and SOC 2 selectable and narrows the tooltip to Single audit. The revision wins.
- The handoff's c footer uses "she" for Fiona Nash; a person-neutral template for other pending members is not designed. P-07-T21 adds it to this contract's copy table before it merges (P-07 R-9).
- d's clock (Mon Aug 24, 2026) predates E0: the Granite Peak acceptance decision and letter E14 (Sep 2) are absent in the Aug 24 snapshot that P-07-T50 builds; until then the scenario overrides the acceptance record only.
- g's acceptance line names a condition ("predecessor auditor communications (AU-C 510) before fieldwork"); conditions stay on the acceptance record until P-05 makes them to-dos.
