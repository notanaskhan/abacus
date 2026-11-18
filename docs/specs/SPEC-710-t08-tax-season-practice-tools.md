---
id: SPEC-710
title: T-08 Tax season and practice tools (TY2028) — ENG-07, HOME-03, TAX-10, TAX-14, TAX-15, TAX-16
status: approved
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-014, ADR-024, ADR-050, ADR-052, ADR-136, ADR-138, ADR-139, ADR-140, ADR-143, ADR-148, ADR-151, ADR-161, ADR-167, ADR-179, ADR-232, ADR-233, ADR-300, ADR-320, ADR-342]
related_specs: [SPEC-651, SPEC-702]
created: 2026-11-18
updated: 2026-11-18
epic: T-08
task: T-08-T01 (TASK-8600)
---

# SPEC-710 · Tax season and practice tools (TY2028)

> **Instructions for coding agents**
> - The design is `docs/plan/epics/T-08.md` §1 to §8; task rows `docs/plan/epics/T-08.tasks.csv`.
>   US-1.1 to US-6.2 and AC1.1 to AC7.5 are adopted verbatim; this file numbers their testable
>   cores AC-1 to AC-40 and records the gate check and the open-question answers.
> - Screen contracts: `docs/screens/{ENG-07,HOME-03,TAX-10,TAX-14,TAX-15,TAX-16}.md` (33 artboards).
> - **Code computes, models judge** (ADR-050, DEC-77): manifest tallies, due dates and rolls, risk
>   tiers, Δ and Δ%, check outcomes, savings estimates and amendment changes are code. Tax, the
>   IL-1040-X tax and the imputed underpayment are engine imports or a labelled
>   "Accrued tie-out (shadow)".
> - Agents propose; named people approve cohorts, accept explanations, raise opportunities, approve
>   amendments and decide elections (INV-1). §7216 consents (`use`, `ai_disclosure`) before every
>   `tri` agent read (C19). Walls are 404 with no count (DEC-43). Never transmit (R-04).
> - Code identifiers say `filing_deadline` or `due_date`, never a bare `deadline` (DEC-14).

## 1. Summary
Grace builds the TY2025 roll-forward manifest in six cohorts and Samuel approves each one before
anything is created; Home › Deadlines shows every due date computed from the C21 rules; Samuel
accepts cited explanations for every line of the Feld two-year comparison that moved past the
threshold; a firm checklist runs across many 1065s with exceptions linked to existing issues;
Daniel raises consent-filtered planning opportunities himself; Yusuf amends an accepted return
without touching the original and Neil decides the BBA route.

## 2. Gate check (main 1ca51eec9, 2026-11-18; DEC-5600)

| Decision (T-08 §0.1) | On main | State | T-08 use |
|---|---|---|---|
| DEC-07 / P-04 work items | ADR-136 | accepted | `tax_return` and `advisory_project` work items; a cohort row creates one engagement and N returns |
| DEC-08 / P-34 status registry | ADR-138 | accepted | status rows in T-08-T03 |
| DEC-12 / P-36 API conventions; DEC-13 / P-39 per-module registries | ADR-139, ADR-140 | accepted | list envelope, `allowed_actions`, `Idempotency-Key`; per-module matrix and flag files |
| DEC-23 / P-15 real time | ADR-232 | proposed | SSE for ENG-07 c, TAX-14 A, TAX-10 e with polling fallback; T-08 ships polling first and needs nothing ADR-232 has not drafted |
| DEC-24 / DEC-28 / P-35 suggestions, proposals, grants | ADR-161 | accepted | single-use approval grant per cohort; amendment proposals; compensating undo |
| DEC-25 / P-26 e-signature | ADR-342 | accepted | letters and §7216 consents as draft envelope documents; the 1040-X 8879 through C7 |
| DEC-27 / P-37 demo clock | ADR-143 | accepted | epochs Mon Jan 12, 2026 (ENG-07), Wed Sep 9 (TAX-10 d), E0 Mon Sep 14 9:24 AM CT, Tue Sep 15 (TAX-16 b) |
| DEC-36 / P-07 review grammar | ADR-134 | accepted | issues and links (dedupe), decision cards (BBA), sign-offs, checkpoints (as-filed baseline) |
| DEC-41 / P-22 agent model | ADR-233 | accepted | capability specs in code; numbers by reference |
| DEC-44 / P-19 deterministic documents | ADR-320 | accepted | byte-stable xlsx for the manifest, comparison and deadlines |
| DEC-49 / P-18 tax-engine route | ADR-150 | accepted | CY/PY values from the CCH file bridge; never transmit |
| DEC-52 / P-12 §7216 and TINs | ADR-167 | accepted | gateway condition 6 on `two_year`, `planning_screen`, `amendment`; planning consent filter |
| DEC-55 / P-28 flags vs entitlements | ADR-148 | accepted | six rollout flags; the `tax` entitlement gates the module |
| DEC-68 / P-29 busy season | ADR-151 | accepted | dark, flag-off, expand-only until Oct 20, 2028 |
| DEC-71 / P-14 retention | ADR-179 | accepted | retention rows for new record types arrive as DB content through Q-05's FIL-02 |
| DEC-76 / P-62 reference data | ADR-300 | accepted | TY2028 sets as DB rows; TAX-10 line maps and planning limits as reviewed repo files |
| DEC-79 / P-25 model text to clients | not drafted | open (accept-by Fri Dec 8, 2028) | TAX-15 raise uses the firm's database template or firm-written text; an agent draft prefills only on a synthetic tenant |

Contracts on main: C3 (review grammar), C7 (envelopes), C19 (`docs/contracts/c19-consent-gate.md`),
C21 (`backend/tests/contracts/c21_*`), F-07 T13 calendar kit (`packages/ui`), T-02 `ReturnFrame`.
No red row is open, so no T-08 task stops. P-25 only limits TAX-15 b to template text (AC-27).

## 3. Open questions (T-08 §11.2; answered with the recommended option; DEC-5600)
OQ-1 carry continuance forward unless a CLI-07 risk fact changed (changed facts become exceptions) ·
OQ-2 the checklist's `parameters.two_year_threshold` wins, the variance policy is the default, the
popover names the source · OQ-3 TAX-14 is model-free · OQ-4 done chips render green on their
completion date · OQ-5 both exports as one-off downloads with fresh MFA, no feeds · OQ-6 screening
is event-driven · OQ-7 unchanged reviewed-year K-1s with a "Form 8986 statement" note · OQ-8 the
running pill reads "Creating engagements for cohort 3 · approved by Samuel Ito" · OQ-9 invitations
are created pending and sent at binder publish · OQ-10 TAX-15 raise uses an O3 send sheet over
`message.send` until INB-04 · OQ-11 TAX-16 b runs at Tue Sep 15, 2026 · OQ-12 Sep 15 holds 12 ·
OQ-13 any manager or partner may approve a cohort, a firm admin never · OQ-14 T-08 publishes the
TY2028 information-return thresholds · OQ-15 TAX-10 line maps are repo files reviewed yearly ·
OQ-16 DF-10 internal targets are stored and exported, HOME-03 shows statutory dates · OQ-17 relief
is applied by a firm admin, manager or partner, human-only with fresh MFA.

## 4. Acceptance criteria

### Season setup (ENG-07; SS-1)
- **AC-1** Six cohorts foot 214 = 65 + 30 + 42 + 19 + 38 + 20 engagements, 224 returns and 241
  binders; created so far 126 = 65 + 30 + 31; every figure from `engagements/season/manifest.py`.
- **AC-2** The C5 Feld row carries forms, carried assignments, binder source with 7 requests, a
  renewal letter with fee +4% and a separate consent set of two purposes.
- **AC-3** Exception rules flag exactly Osterberg and Farouk (seasonal preparer) and Barlow (bounced
  contact) in cohort 5; reassign and exclude answer 409 `cohort_approved` once approved.
- **AC-4** An ask is answered only by a person (`answered_by`); with the planner unavailable the
  ambiguity becomes a code exception and the manifest is otherwise identical.
- **AC-5** Approval writes one insert-only row pinning `rows_hash` and the manifest version with a
  single-use grant; a firm admin, staff and the agent get 403; withdrawal after the first step
  answers 409 `execution_started`.
- **AC-6** Execution steps are idempotent on (row, step); progress comes from the step log; nothing
  is sent; every created record carries actor `system`, `on_behalf_of` the approver and the grant.
- **AC-7** A walled user sees no row, count or assignee offer for the walled client.
- **AC-8** The manifest export is byte-stable and formula-escaped under `export.create` with fresh MFA.

### Filing deadlines (HOME-03; FD-1)
- **AC-9** At E0 risk tiers are computed on the server in the firm zone and never stored.
- **AC-10** Sep 15 holds 12 = 8 × 1065 + 3 × 1120-S + 1 estimate row.
- **AC-11** The rule popover's rule text and reference-set version come from the `filing_deadlines`
  row (C21), never the browser.
- **AC-12** List rows include the Thornbury 706 Nov 2, 2026 (4768 → May 3, 2027) and Lakeshore 990
  Nov 16, 2026 (8868 → May 17, 2027).
- **AC-13** Person │ Daniel Reyes leaves exactly five.
- **AC-14** Walled clients contribute no row, day count or "+n more"; firm admins see metadata only.
- **AC-15** Recompute is idempotent on `inputs_hash`; a postponement shows the struck original.
- **AC-16** Exports carry no TIN or amount and need fresh MFA; no subscription URL exists.
- **AC-17** At most one `filing_deadline.approaching` per (deadline, threshold, due date).
- **AC-18** Every portal principal gets 403 on `/v1/filing-deadlines*`.
- **AC-19** TY2028 goldens: 1040/1041 Tue Apr 17, 2029; 1065/1120-S Thu Mar 15, 2029, extended Mon
  Sep 17, 2029; Q4 1040-ES Tue Jan 16, 2029.
- **AC-20** An unregistered `source_kind` fails closed at startup.

### Two-year comparison (TAX-10; TP-1)
- **AC-21** Feld TY2025 flags exactly 8 lines; 2b and 34 stay unflagged; Δ and Δ% by code.
- **AC-22** The threshold source used is named and its version pinned.
- **AC-23** "Explain…" runs only with both Felds' consents; unverified citations never stream.
- **AC-24** Acceptance is insert-only with the values hash; a preparer and the agent get 403.
- **AC-25** A changed CY or PY value makes the acceptance stale by computation.

### Standards runs (TAX-14; TP-1)
- **AC-26** Six returns = 1 running + 3 passed + 2 with exceptions at 9:24 AM; Ridgeline's two
  exceptions link to open issues (count stays 11); Marlowe's three create issues; re-runs never
  duplicate; no model call anywhere in TAX-14; manual items confirmed by a reviewer only.

### Planning (TAX-15; TP-1)
- **AC-27** The strip and queue tie by code (58 clients, 9 of 71); only consented clients reach the
  model; Ferris is Not screened with no outreach control; raise is a person's send through
  `message.send` on a database template; dismiss needs a reason and is insert-only.

### Amendments and AARs (TAX-16; TP-1)
- **AC-28** Amending creates a new linked return with an as-filed baseline; refund due 2,708 =
  41,000 − 37,678 − 614; IL change (495); the original stays read-only (409 `return_accepted` and a
  DB trigger).
- **AC-29** Supersession is an insert-only row written on the accepted acknowledgement.
- **AC-30** The BBA election is decided only by the signer through `decision.decide`;
  14,800 = 40,000 × 37% as engine value or labelled shadow tie-out.

### Agent gates, data and platform
- **AC-31** The agent is denied every action listed in T-08 AC7.1; generated tests prove each.
- **AC-32** Non-cleared firms see the DF-04 state and the gateway refuses `boundary_refused:<reason>`.
- **AC-33** `two_year`, `planning_screen` and `amendment` declare `data_classes: [tri]`.
- **AC-34** Six flags exist default-off with `expires: 2028-12-20`.
- **AC-35** Migrations are expand-only with forced RLS; IO tables refuse UPDATE and DELETE; human-only
  CHECKs refuse non-human actors.
- **AC-36** Every new route answers 501 under its own action until its service task lands, and the
  api-client regenerates.
- **AC-37** Consumer suites fail when a field the 33 artboards read is removed.
- **AC-38** Audit payloads carry IDs only (DEC-60).
- **AC-39** Fixture mode opens all 33 artboards from seed-derived fixtures.
- **AC-40** The agents-off journey completes every human path (R-01 #4).

## 5. Task map (S50)
T01 this file and the contracts (AC-1…AC-40 traceability) · T02 design follow-ups · T03 protected
bundle (AC-31, AC-34) · T04 FD-1, SS-1, TP-1 stubs (AC-36, AC-39) · T05/T06/T07 migrations (AC-35,
AC-20) · T08 consumer tests (AC-37). Services, screens and journeys land S51–S55 per the epic.
