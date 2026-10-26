# ADM-04 · AI policy & approval gates

| Field | Value |
|---|---|
| Route and params | `/settings/ai-policy` behind `ai_policy.v1` (G-02 §5.1). `?history=1` opens the version drawer, `?version=4` opens it at v4, `?approve=4` opens the publish sheet for the approver (the C13 gate's target). Legacy `/admin/autonomy` redirects here once G-01 has moved its Letter policy and Time zone cards to ADM-01 |
| Template and host frame | T12 `SettingsLayout` (ADM-01 frame), section "AI policy"; fieldsets 1100 with ValueRow, Toggle, Lock, a table inside a fieldset, provenance chip; Dialog (ConfirmDialog 440), O3 sheet 500, O2 drawer, popover 320, Toast |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ADM-04 AI policy and approval gates/` (README.md, spec.md, revision.md: R2 waves 5 and 8; revision wins for what it lists) |
| Epic and tasks | G-02 · contract stub T15 · seed and fixtures T07 · migration T23 · services T24 · screen T25 · AC suite T22 · parity and journeys T26 · rollout T27 · this contract T03 |
| Manifest status | planned (`routes/manifest/adm.ts`): built by G-02-T25 behind `ai_policy.v1` |

Code (G-02-T25): `apps/web/src/screens/ADM-04/{index.tsx, scenarios.ts, copy.ts, ADM-04.test.tsx}`, `apps/web/src/domain/governance/{queries.ts, mutations.ts, joins.ts}`.

## States

11 artboards: a–j from the original handoff plus revision R2's benchmark ConfirmDialog (handoff letter "f" in the revision, mapped here as **k** so it does not collide with the original f). Persona and clock are E0 unless stated.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Owner · status |
|---|---|---|---|---|---|
| a | margaret-okonkwo (Managing Partner, QM owner) | Mon Sep 14, 2026, 9:24 AM CT | E0 | v1 Jan 5, v2 Jan 9, v3 Jan 14 published (Margaret publishes, Daniel Reyes approves); draft equals v3, so "Save as v4…" is disabled; policy principal Off + Lock | G-02-T25 · fixture + staging |
| b | margaret-okonkwo | 9:24 AM | E0 | draft differs from v3: Override tolerance 8% → 6%; "Unsaved changes"; "Save as v4…" enabled | G-02-T25 · fixture + staging |
| c | margaret-okonkwo | 9:24 AM | E0 | ConfirmDialog "Allow policy acceptance?"; "Allow" waits for the attest-client checkbox | G-02-T25 · **fixture only** (dormant P-08, DEC-53) |
| d | margaret-okonkwo | 9:24 AM | E0 | O3 500 sheet "Save as v4": diff "Override tolerance 8% → 6%", Effective Sep 15, 2026, Approver **Daniel Reyes** (DV-1), "Publish v4" | G-02-T25 · fixture + staging |
| e | hannah-leclerc (Manager) | 9:24 AM | E0 | not a partner: banner "Only partners can change the AI policy." and Lock 12 on every band | G-02-T25 · fixture + staging |
| f | margaret-okonkwo | 9:24 AM | E0 | after c: band pill "On · non-attest only", toast "Policy acceptance on · logged" | G-02-T25 · **fixture only** (dormant P-08) |
| g | margaret-okonkwo | Tue Sep 15, 2026, 9:24 AM CT | E0 + v4 | v4 approved by Daniel Reyes, effective Sep 15: chip v4, ADM-07 event "AI policy v4 published by Margaret Okonkwo" | G-02-T25 · fixture + staging |
| h | margaret-okonkwo | 9:24 AM | E0 | scrolled to fieldsets C and D: Auto mode off for every audit and assurance type; §7216 row with the three blocked clients | G-02-T25 · fixture + staging |
| i | margaret-okonkwo | 9:24 AM | E0 | gate row popover 320: where the gate appears (SHL-10, SHL-11, SHL-12, CLS-07, TAX-09) and how it is logged | G-02-T25 · fixture + staging |
| j | margaret-okonkwo | 9:24 AM | E0 | `?history=1`: version drawer v1 (Jan 5), v2 (Jan 9), v3 (Jan 14) with diffs | G-02-T25 · fixture + staging |
| k | margaret-okonkwo | 9:24 AM | E0 | revision R2 fieldset G: ConfirmDialog 440 "Join the benchmark network?"; the seed stays not joined | **I-03-T37** (S62) · deferred |

**New v1 frames (G-02-T03 revision; built by T25):**

| Frame | Viewer | Data condition | Owner · status |
|---|---|---|---|
| Immediate-controls band | grace-holloway (Firm Admin) | client-data opt-in on since Jun 1 (fixture) with the disclosure dialog and step-up; agent stages Shadow / Live; "Pause all agents" | G-02-T25 · fixture + staging |
| Autonomy level row | margaret-okonkwo | the firm's autonomy level from the policy (replaces `Autonomy.tsx`'s card) | G-02-T25 · fixture + staging |
| Awaiting approval | daniel-reyes (Partner, approver) | v4 requested by Margaret: chip "Awaiting approval · Daniel Reyes" between d and g; the requester is never the approver (409 `approver_is_requester`) | G-02-T24, T25 · fixture + staging |
| Real-firm Auto mode | margaret-okonkwo on a non-synthetic test firm | Auto mode forced off with the Season 1 reason; toggles locked | G-02-T25 · staging |
| Locked fieldset B and §7216 row | margaret-okonkwo | policy principal "Off + Lock" (P-08 dormant); §7216 consent row locked on | G-02-T25 · fixture + staging |

**Revision R2 frames owned elsewhere (mapped, not built here):** fieldset F "Triggers & agent columns" and the fieldset A footer "Triggers, agent columns and Board moves never adopt, accept, sign off or send." → **K-04** (requested ≈ 1.0 task ahead of K-04-T21); fieldset G learned-context rows → **K-05** (beside K-05-T10); fieldset G benchmark row and state k → **I-03-T37**.

Non-artboard states: loading (T12 skeleton), error (`ViewState` error with Retry), not-allowed (client, agent and system principals: 404 or 403 from the matrix; never rendered), flag off (route absent; `/admin/autonomy` unchanged).

## API

| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons |
|---|---|---|---|---|
| read | `GET /v1/firm/ai-policy` | effective version, pending version, draft summary, gate catalogue rows (A), sections B–E, immediate controls, sub-processors and model family | `ai_policy.read` | partners edit; others read-only with "Only partners can change the AI policy." |
| read | `GET /v1/firm/ai-policy/versions`, `…/versions/{n}` | history with diff against n − 1 | `ai_policy.read` | — |
| write | `GET/PUT/DELETE /v1/firm/ai-policy/draft` | draft (If-Match; section rules; stricter-only validator, 422 `policy_loosening_refused`) | `ai_policy.draft` | partners |
| write | `POST /v1/firm/ai-policy/versions` | `{effective_from, approver_user_id}` → `awaiting_approval`; raises the C13 gate | `ai_policy.publish` (fresh MFA) | partners; the approver must be another partner |
| write | `POST /v1/firm/ai-policy/versions/{n}/approve`, `/decline`, `/withdraw` | second-partner decision; requester withdraws | `ai_policy.approve` (fresh) / `ai_policy.publish` | approver only |
| read | `GET /v1/firm/ai-policy/effective?engagement_type=&at=` | effective cells (ENG-03, KNW-04, run planner) | `ai_policy.read` | — |
| write | `POST /v1/firm/agents/pause`, `/resume` | Pause all agents | `firm_agents.pause` | firm admin, security admin, quality partner |
| write | Q-02's opt-in route (SPEC-036) | "AI on your clients' data" with disclosure | `firm.ai_client_data` (fresh) | firm admin |

Contract: `docs/contracts/` AI-policy family (G-02-T15). Every write is audited and appears in ADM-07.

## Status

`ai_policy_version` states (draft, awaiting approval, published, superseded); toggles on/off; pills amber "Off" (policy principal), green-tint "On · non-attest only" (fixture-only f).

## Copy

Verbatim from the handoff spec and revision, through `copy.ts`. Key strings: header chip "BH AI policy v3 · published Jan 14, 2026 by Margaret Okonkwo"; band "Agents draft, test, propose and chase. People approve."; footer "Defaults from 01 §2.4 and the IRS OPR AI guidance (Jun 24, 2026). Firms may only make them stricter."; read-only banner "Only partners can change the AI policy."; c "Allow policy acceptance?" with "I understand attest clients are excluded"; f toast "Policy acceptance on · logged"; k "Join the benchmark network?" (I-03-T37). With the T03 deviations below.

## Links

| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Consent registry ›" | ADM-05 (T-01) | planned |
| policy names | KNW-04 (K-02) | planned |
| Override tolerance helper | ADM-11 (Q-05) | planned |
| gate popover rows | SHL-10, SHL-11, SHL-12 (P-04), CLS-07 (C-01), TAX-09 (T-01) | planned |
| every saved change | ADM-07 `?target=ai_policy:<n>` | live with G-02-T13 |

## Acceptance

- ADM-04 acceptance: twelve approval-gate rows; only rows 1 and 5 offer policy acceptance, both Off + Lock; the attest column reads "Never" wherever policy acceptance exists.
- ADM-04 acceptance: the policy principal is explained as a firm rule, off by default, logged, reversible, non-attest only, and stays dormant in production (c and f fixture-only).
- ADM-04 acceptance: threshold amounts match "BH AJE thresholds v2" (payroll accruals $15,000; other classes $10,000).
- ADM-04 acceptance: §7216 switch on; the three blocked clients match ADM-05 (Ferris, Stein, Thornbury).
- ADM-04 acceptance: Auto mode off for every audit and assurance type, consistent with ENG-03.
- ADM-04 acceptance: the approver is never the requester; v4 waits "Awaiting approval · Daniel Reyes" until he approves.
- ADM-04 acceptance (R2, owners K-04, K-05, I-03): FS audits allow triggers and Run agent on move; preview, budget check and duplicate blocking locked on; benchmark network opt-in and off; fieldsets A–E and the v3 chip unchanged.

## Figures

- Policy history v1 Jan 5 · v2 Jan 9 · v3 Jan 14, 2026; v4 effective Sep 15, 2026 (G-02-T07 seed goldens).
- Thresholds: payroll accruals ≤ $15,000; other accruals, prepaids, depreciation, deferred revenue ≤ $10,000; document confidence ≥ 98%.
- §7216: 3 clients blocked (Morgan & Kai Ferris 1 of 2 signed · Harold Stein declined · Estate of Walter Thornbury not requested).
- Override tolerance 8% (b: 6%); monthly accuracy sample 25 outputs per agent; run trace retention 7 years.

## AVOID

Gradients, emoji, saturated blue toggles, heavy shadows, invented colours, lorem ipsum; any control that lets the Accrued Agent approve, sign off, release, send final, post or export; "Approved by Accrued Agent"; policy acceptance for attest clients; sparkle "AI" decoration; (R2) any control letting a trigger, column or move approve, sign off, release or send; the agent approving learned context; "task" for a to-do.

## Deviations

| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-1 | d names **Daniel Reyes** as approver, not Margaret Okonkwo | the approver must not be the requester (two-partner publish) | G-02 §2.1; DEC-411 |
| DV-2 | Fieldset D sub-processors generated from `docs/operations/provider-terms.yaml`; no "+ Add" mini-pill; no "Anthropic · model inference" row until a provider-terms entry exists | DF-16: the register is the source of truth | DEC-411 |
| DV-3 | Immediate-controls band, autonomy level row, Awaiting approval state, real-firm Auto mode forced off, locked fieldset B and §7216 row are new v1 frames | v1 behaviour the handoff did not draw (SPEC-036 opt-in and stages; P-49 autonomy; Season 1 Auto mode rule) | DEC-411 |
| DV-4 | c and f are fixture-only; production shows policy acceptance "Off + Lock" | DEC-53 / ADR P-08: the policy principal stays dormant | DEC-53, DEC-411 |
| DV-5 | Revision R2 fieldsets F and G and state k are mapped to K-04, K-05 and I-03-T37 | each needs its owner's backend (runtime v2, learned context, benchmark consent) | G-02 §2.3; DEC-411 |

## Parity

| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a, b, d, e, g, h, i, j | C (threshold 0.20, maxDiffPixelRatio 3%) | — | locked by Fri May 14, 2027 (G-02-T26); DV-1 and the band report-only until the boards are revised |
| c, f | C report-only | — | fixture mode only (T26) |
| k | — | — | I-03-T37 |

Tier D on every state: toolbar 46, pane header 46 with 14.5/500 title, rows 40, pills 19, radius 12.

## Open gaps

- The design-tool frames for the new v1 states and the design-fidelity sign-off are made on the Wave 3 canvas outside the repository; until then the deviations above stay report-only in parity.
- The revision's own new-state letter "f" collides with the original f; this contract calls it k.
