# KNW-04 · Firm standards & thresholds

| Field | Value |
|---|---|
| Route and params | `/knowledge/standards` (Knowledge); `?section=review_checklists|review_levels|return_approval|aje_thresholds|variance_thresholds|materiality_ranges|document_confidence|ssars_cas|deadline_rules`, `?version=<n>`; overlays `?ov=publish-standard:<id>:<v>` (ConfirmDialog with step-up) and `?ov=import-standard:<id>`. Artboards: `/components/screens/KNW-04?st=a…i,j` |
| Template and host frame | T12 `SettingsLayout` (section list 240 · form pane 1126; fieldsets ≤ 760) · `Wave 3 - Closes & Knowledge.dc.html#knw04` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-04 Firm standards and thresholds - Brightwater Hale/` (README.md, spec.md; no revision.md, no deviations recorded) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | K-02 · contract K-02-T02 (this file); read states a–h T13; draft and publish i T14; deadline rules j T17; content T18; parity, axe and journeys T19 |
| Spec and ADRs | SPEC-500 AC-13, AC-14; ADR-300; DEC-36, DEC-38, DEC-43, DEC-53 |
| Flags | `knowledge.firm_standards` (route and every `/v1/standards*`); `rules.reference_sets` (section j) |
| Manifest status | planned with path `/knowledge/standards` (K-02-T13 built a–h on fixtures; planned until walked on staging, DEC-195); `live` with T08 (reads) and T14 (draft and publish) |

## States
Clock E0, Mon Sep 14, 2026, 9:24 AM CT (f: 11:12 AM); viewer Priya Raman (Partner · CAS & Advisory) unless noted.

| Artboard | Viewer | Data condition | Parity tier | Status |
|---|---|---|---|---|
| a | priya-raman | AJE thresholds: BH AJE thresholds v2 published Jan 20, 2026 by Priya Raman; seven rows; policy acceptance off (display-only, ADM-04); Copperleaf's August entries sorted (4 within, 20,020, batch by Raj Malhotra; 1 held, 14,900, Priya); Timeline v2 current, v1 Superseded | C (lock) | fixture (T13) |
| b | priya-raman | Review checklists: six TY2025 checklists, applied to 224 returns; 1040 v7 (TY2026) draft row (partners only); the TAX-14 run card (1065 v4, 9:18 AM, Samuel Ito); Apply to returns… enabled | C (lock) | fixture (T13) |
| c | priya-raman | Review levels: three tiers with criteria | C report | fixture (T13) |
| d | priya-raman | Return approval: BH-TAX-02 rule, applies-to list → Daniel Reyes, export condition | C report | fixture (T13) |
| e | priya-raman | Variance thresholds v3: close flux, SSARS review analytics, tax two-year; Copperleaf R&M example | C report | fixture (T13) |
| f | priya-raman (11:12 AM) | Materiality ranges v2: Northwind decided by Margaret Okonkwo; Granite Peak proposed by Accrued Agent, Blocked on a partner decision | C report | fixture (T13) |
| g | priya-raman | Document confidence v1: hold below 90%, auto-accept above 98% off (policy principal dormant); BrokerWindow 62% example | C report | fixture (T13) |
| h | priya-raman | SSARS & CAS: early adoption off; Copperleaf August → AR-C 70 preparation | C report | fixture (T13) |
| i | priya-raman | Draft v3 of AJE thresholds: two changed limits (amber, struck prior), effective Oct 1, 2026, sticky Save bar, Publish v3…, Discard draft | C (lock) | T14 |
| **j (composed, DF-10)** | grace-holloway | Deadline rules: TY2025–TY2027 reference sets (due-date rules, holidays, postponements, 8879 form set and tolerances, information-return thresholds, retention minimums), each with version, effective date and source; no edit control for any firm role | report-only | T17 |

Non-artboard: **draft hidden** (Cole Hart, staff, on b: the 1040 v7 draft row absent, its version 404); **not allowed** (a portal principal: 404); **flag off** (T12 frame with the C-20 "not turned on" state); **examples empty** (no provider registered, live until C-01/A-04: the designed empty state, never invented rows); **walled example** (row absent, no "n hidden", totals recomputed); loading and error (F-05 ViewStates).

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/standards?kind=` | `ListPage[StandardOut]` | `firm_standard.read` | every firm role; drafts partners only |
| read | `GET /v1/standards/{id}?version=` | `StandardDetailOut` | `firm_standard.read` | |
| read | `GET /v1/standards/{id}/versions/{v}` | `StandardVersionOut` | `firm_standard.read` | draft: 404 to non-partners |
| read | `GET /v1/standards/{id}/versions/{v}/diff?against=` | `StandardVersionDiffOut` | `firm_standard.read` | i |
| read | `GET /v1/standards/{id}/examples?period=` | `StandardExamplesOut` | `firm_standard.read` | `visible()`-filtered, no counts |
| read | `GET /v1/standards/{id}/versions/{v}/export.xlsx` | workbook | `firm_standard.read` | Export |
| write | `POST /v1/standards` | `StandardCreateIn` → `StandardOut` | `firm_standard.create` | QM owner, practice leader; fresh MFA |
| write | `PUT /v1/standards/{id}/owner` | `StandardOwnerIn` | `firm_standard.assign_owner` | owner must be a partner |
| write | `POST /v1/standards/{id}/versions` | → `StandardVersionOut` | `firm_standard.draft` | owner only: New version… |
| write | `PATCH`/`DELETE /v1/standards/{id}/versions/{v}` | `StandardDraftPatchIn` (If-Match) | `firm_standard.draft` | owner only |
| write | `POST /v1/standards/{id}/versions/{v}/publish` | `StandardPublishIn` (If-Match, Idempotency-Key) | `firm_standard.publish` | owner only; fresh MFA; human only |
| write | `POST /v1/standards/{id}/imports` · `POST /v1/standards/imports` | `StandardImportIn` → `StandardImportResultOut` | `firm_standard.import` | Import…; never publishes |
| read | `GET /v1/reference-sets?kind=`, `/{key}?as_of=`, `/{key}/versions` | `ReferenceSetOut`, `ReferenceSetResolvedOut` | `reference_set.read` | j; read-only for every role |

The agent never holds a write; the policy acceptance and auto-accept toggles are display-only (DEC-53, ADR-149) and link ADM-04.

## Status
`firm_standard_version` (Draft neutral · Published green-tint · Superseded soon, computed · Discarded hidden); `reference_set_version` (Draft · Published · Superseded · Withdrawn) on j. Examples use the StatusDisc olive ✓ / ring and the amber "Review required", red-tint exceptions and amber "Blocked on a partner decision" pills of their owning screens.

## Copy (key strings, verbatim from spec.md)
| Key | String |
|---|---|
| `subbar.title` | "Firm standards & thresholds" · "Brightwater Hale LLP" |
| `sections.header` | "Standards" |
| `sections` | "Review checklists" · "Review levels" · "Return approval" · "AJE thresholds" · "Variance thresholds" · "Materiality ranges" · "Document confidence" · "SSARS & CAS" |
| `header.newVersion` | "New version…" |
| `header.apply` | "Apply to returns…" |
| `aje.helper` | "Within-threshold entries still need a named person; they are approved together as one batch under this policy version." |
| `aje.policyToggle` | "Let the policy accept within-threshold entries without a person (logged as 'Policy: BH AJE thresholds v2')" |
| `aje.policyHelper` | "Managed in Firm settings › AI policy. Never applies to attest clients." |
| `aje.examplesTitle` | "How v2 sorted the August 2026 closes" |
| `aje.openAjes` | "Open Copperleaf AJEs ›" |
| `versions.title` | "Versions" |
| `materiality.reserved` | "Decisions are reserved to the engagement partner." |
| `ssars.toggle` | "Early-adopt SSARS 27 for CAS monthly statements" |
| `ssars.helper` | "Off: periods ending before Dec 15, 2026 are prepared under AR-C 70 with 'No assurance is provided' on each page. Periods ending on or after Dec 15, 2026 are CAS by-products with no SSARS report or legend." |
| `draft.publish` | "Publish v{n}…" · "Discard draft" |
| `draft.saveBar` | "Draft v{n} · {count} changes from v{prev} · visible to partners only" (K-02 US-3.2) |

## Links
Inbound: KNW-01 (Firm standards cards), TAX-14 (standard chip), CLS-06, AUD-07, ADM-04. Outbound:
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens KNW-01 · Knowledge (designed link, handoff link graph) | KNW-01 | as the target's manifest status |
| Opens ADM-04 · AI policy (designed link, handoff link graph) | ADM-04 | as the target's manifest status |
| Apply to returns… (b) | TAX-14 | planned |
| Open Copperleaf AJEs › (a) | CLS-06 | planned |
| Northwind / Granite Peak examples (f) | AUD-07 | planned |

## Acceptance
- KNW-04 acceptance: fieldset, toggle and value-row grammar matches the Edit Agent sheet; the checklist "last run" card agrees row for row with TAX-14 (started 9:18 AM by Samuel Ito; Ridgeline 2 and Marlowe 3 exceptions; Northgate running; three passed).
- KNW-04 acceptance: Granite Peak materiality shows as proposed and blocked on Margaret Okonkwo's decision; only Northwind's is decided.
- KNW-04 acceptance: the AJE example foots: 11,860 + 700 + 2,140 + 5,320 = 20,020 within threshold; 14,900 > $10,000 held.
- KNW-04 acceptance: the materiality examples sit inside the ranges and foot (252,200 × 75% = 189,150; × 5% = 12,610; 155,000 × 75% = 116,250; × 5% = 7,750).
- KNW-04 acceptance: checklist "applied to" counts sum to 224 TY2025 returns; 1065 Review Checklist v4 has 42 checks.
- KNW-04 acceptance: SSARS 27 is off and the routing text matches CLS-08.

## Figures
AJE 11,860 + 700 + 2,140 + 5,320 = 20,020; held 14,900. Checklists 162 + 38 + 12 + 5 + 6 + 1 = 224. Northwind 1.5% × 16,812,400 = 252,200 (rounded); PM 189,150; CT 12,610. Granite Peak 5% × 3,100,000 = 155,000; PM 116,250; CT 7,750. Copperleaf R&M 3,200 vs 640 (+400%, +2,560). Proved by the fixture foot test with T13.

## AVOID
Gradients, emoji, saturated blue toggles, heavy shadows, invented colours, lorem ipsum, boxed inputs, the agent as approver, thresholds without a version and an owner.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | The effective-date control is the F-05 DatePicker, not a free text field | keyboard-operable (K-02 §5) | K-02 §5 |
| D2 | j "Deadline rules" is composed (no artboard) from T12 grammar | DF-10 | K-02 §2.1 |
| D3 | Examples are empty in the live product until C-01 and A-04 register providers | no invented rows (US-3.1) | DEC-1151 |
| D4 | Materiality ranges uses `circle-dot` for lucide Target | the icon set has no Target yet | DEC-1154 |
| D5 | The version chip and Published pill sit in the T12 pane header's centre slot, not beside the title | `SettingsLayout`'s pane title is text only | DEC-1154 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a, b, i | C (lock by S19) | — | measured with T19 |
| c–h | C report | — | |
| j | — | — | composed |

## Open gaps
- The handoff's toggles are display-only in the product (policy principal dormant, DEC-53); their "on" colour is never shown.
