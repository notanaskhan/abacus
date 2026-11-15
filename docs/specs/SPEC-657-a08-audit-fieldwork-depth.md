---
id: SPEC-657
title: A-08 Audit fieldwork depth — JE and attribute testing with expansion (AUD-12), analytics (AUD-13), confirmations (AUD-14) and the respondent page (POR-17), the SSARS workspace (AUD-26)
status: approved
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-007, ADR-014, ADR-018, ADR-027, ADR-031, ADR-040, ADR-042, ADR-050, ADR-052, ADR-064, ADR-078, ADR-089, ADR-090, ADR-111, ADR-136, ADR-139, ADR-140, ADR-146, ADR-151, ADR-152, ADR-157, ADR-160, ADR-161, ADR-163, ADR-166, ADR-179, ADR-186, ADR-230, ADR-232, ADR-233, ADR-300, ADR-320, ADR-340, ADR-342, ADR-400]
related_specs: [SPEC-640, SPEC-655]
created: 2026-11-15
updated: 2026-11-15
epic: A-08
task: A-08-T01 (TASK-8043)
---

# SPEC-657 · Audit fieldwork depth

> **Instructions for coding agents**
> - The design is `docs/plan/epics/A-08.md` §1 to §8; task rows are `docs/plan/epics/A-08.tasks.csv`.
>   The acceptance criteria below are the epic's §3 stories, numbered here (AC-n.m: feature n,
>   criterion m) and adopted as the spec of record; each line states the testable part. Where the
>   epic and a line here differ, the epic's wording wins and this file is corrected.
> - Screen contracts: `docs/screens/AUD-12.md`, `AUD-13.md`, `AUD-14.md`, `AUD-26.md`, `POR-17.md`
>   (29 post-revision artboards; AUD-13 Substantive and the AUD-11 MUS option are composed, DF-05).
>   Contracts provided: `docs/contracts/fieldwork-testing.md`, `audit-analytics.md`,
>   `ssars-workspace.md` (A-08-T05) and `confirmations.md` (A-08-T06).
> - **Code computes, models judge** (ADR-050): the population tie, criteria hits, JE scores, the
>   selection, MUS, UDL, flux changes and thresholds, confirmation differences, coverage and
>   unreconciled amounts are `Decimal` outputs of code with `engine_version` and `inputs_hash`.
>   The agent proposes cited values, explanations and reconciliations; people adopt, accept,
>   approve, send and raise exceptions (INV-1).
> - **The public family** `/v1/confirm/*` is the first route family a stranger can call. It
>   answers only through a link principal (ADR-146) and only as the P-45 amendment enumerates
>   (A-08-T02); a client principal gets 404 on every confirmation route (I-CONFIRMATION-ISOLATION).

## 1. Summary
A Brightwater Hale team runs a nonissuer FS audit's fieldwork and an SSARS engagement inside
Accrued. JE testing (AU-C 240) builds a GL population proved complete by code, scores it against
the firm's risk criteria (database content), draws a seeded selection and lets the agent test each
entry against its support with cited values; staff adopt at L1 and raise exceptions to AUD-15; a
named approver alone releases a sample expansion. Tests of details and controls share A-05's
attribute grid. Analytics (AU-C 520) evaluate a dual threshold from performance materiality;
explanations count only with a verified source; unexplained lines become firm-templated client
questions. Confirmations (AU-C 505) stay under the firm's control: an address the client alone
supplied cannot be sent to, the client signs only the authorization (C7), and respondents answer
on a tokenised, firm-branded single page as a link principal. The SSARS workspace adapts review,
compilation and preparation on one cockpit, with "No assurance is provided." on every preparation
page. Two red extensions: GL JE fields (P-58) and link principals with the public family.

## 2. Gate check (main ae0055816, 2026-11-15; DEC-5028)
Checked by P-ID against `docs/adr/backlog.md`'s "Numbers minted" line and each ADR file's own
`status:` (the file wins). The epic's bracketed ADR numbers are F-02 reservations; the repo's are:

| P-ID / decision | Subject | On main | State | What A-08 does |
|---|---|---|---|---|
| P-09 (DEC-34) | Client identity, scoped grants, link principals | ADR-146 | accepted | `link_principal` actor; POR-17 never gets a portal shell (T06, T15, T19) |
| P-45 (+ amendment, T02) | Unauthenticated routes; the `/v1/confirm/*` family | ADR-152 | accepted (base); amendment drafted in A-08-T02 | ROUTE-001 exception list, padded responses, WAF rule 6, OTP lockout (T06, T15) |
| P-54 (DEC-35) | Authentication, lockout | ADR-141 | accepted | 10-minute codes, lockout, `__Host-` cookie with CSRF (T15) |
| P-58 (DEC-82) | Document-extracted snapshots; GL JE fields | ADR-400 | **proposed** (acceptance: Ayush) | Expand-only `gl_entries` fields; "Not available from this ledger" (T09, T12) |
| P-57 (DEC-81) | Sampling engine | ADR-340 | accepted | `je_score_selection` and `monetary_unit` as new frozen sampler versions (T10, T12, T13, T17) |
| P-07 (DEC-36) · P-35 | Review grammar · suggestions, grants | ADR-160 · ADR-161 | accepted | L1 adopt, gate kinds, SHL-10/12/15 (T14, T17, T18, T21) |
| P-48 | Citation v2, number provenance | ADR-166 | accepted | Value chips cite verified regions; numbers by reference (T14, T21, T23) |
| P-26 (DEC-25) | E-signature | ADR-342 (supersedes ADR-149) | accepted | Envelope purpose `confirmation_authorization` (T18) |
| P-11 (DEC-59) | White-label portal, branded email | ADR-163 | accepted | POR-17 on the firm's host and letterhead; "Accrued" never appears (T19, T30) |
| P-14 (DEC-71) | Retention, holds | ADR-179 | proposed (acceptance: both, with counsel) | Record types `je_test`, `confirmation`, `confirmation_response`, `analytics_set` (T03, T19) |
| P-25 (DEC-79) | Model-drafted text to clients | not drafted | to draft (N-03) — bounding, not gating | Ships off: questions, reminders and second requests are firm templates edited by a person (DV-4) |
| P-15 · P-22 · P-24 · P-47 | SSE · capability specs · structured output · runs | ADR-232 · ADR-233 · ADR-230 · ADR-169 | proposed · **proposed** · accepted · accepted | Modes on spec v2 `workpapers.section_drafter`; C6 v2 run rows (T23, T24) |
| P-49 (DEC-50) | Autonomy, Auto mode | ADR-186 | accepted | Runs start from a person's Begin… or Run; Auto mode off (T24) |
| P-62 (DEC-76) | Platform reference data | ADR-300 | accepted | `legal_holidays` set version enters `inputs_hash` (T10, T12) |
| P-04 (DEC-07) | Work items, engagement types | ADR-136 | accepted | `preparation` verified before any swap (T22, OQ-5) |
| P-19 · P-28 · P-29 · P-36 · P-39 | XLSX · entitlements · busy season · API · registries | ADR-320 · ADR-148 · ADR-151 · ADR-139 · ADR-140 | accepted · accepted · proposed · accepted · accepted | Deterministic exports; flags expire outside the window |
| P-66 | Platform controls and kill switches | ADR-157 | proposed (acceptance: Ayush) | `confirmation_links` registered as a control (T03); the control check lands with T15 |
| DF-05 · DF-31 · DF-04 · DF-34 | Undesigned states · vocabulary · AI unavailable · seed contradictions | ch09 rows | decided | AUD-13 Substantive and AUD-11 MUS composed; AUD-14 statuses in §3.3.1; DV-3; DV-8 (CM-0628 vs CM-6281) |

**Red rows open:** P-58 (ADR-400) and P-22 (ADR-233) are proposed; the P-45 amendment is drafted in
T02. The plan's stop rule is replaced by the solo amendment (`docs/plan/AMENDMENT-solo.md`): A-08
builds on the proposed text exactly as T-07 did on P-69, records it in DEC-5028, and leaves the
acceptances to Ayush. No migration of T09 merges before ADR-400 reads accepted on main (the
row's own acceptance); the batch merge carries that check.

## 3. Open questions (epic §11.2) — the plan's recommended answers (DEC-5028)
OQ-1 one dual-threshold flux engine in `workpapers/compute/flux.py`, shared by `assurance` and
`closes`; C-01 landed none first, so nothing moves · OQ-2 no new P-ID: the route family is an
amendment of P-45 (ADR-152) · OQ-3 the sending address stays on the confirmation (confidential);
only a fingerprint on the link principal; the response keeps the verified address as typed · OQ-4
second request and expiry are firm standards loaded as content (BH: 10 days, 21 days after the
latest request) · OQ-5 T22 checks for `preparation` first and swaps only if absent · OQ-6 manager
and EP may accept a reconciliation, never the reconciler · OQ-7 JE criteria are
`threshold_policies.kind = je_risk_criteria` · OQ-8 no external confirmation network; a recorded
channel only · OQ-9 POR-17 joins the next delta pen test; DEC-1389 defers pen tests, so real
respondent links stay behind `audits.confirmations` and the kill switch.

## 4. Scope
- Five screens, 29 artboards: AUD-12 a–h (incl. R2 f–h), AUD-13 a–e (+ composed Substantive),
  AUD-14 a–e, AUD-26 a–e, POR-17 a–f. AUD-11 gains the composed Monetary unit method (DV-10).
- Modules: `sampling`, `workpapers`, `assurance` (amber); `ledger`, `connections`, `identity`,
  `communications`, `evidence`, `agents` (red); consumers of `review`, `signatures`, `requests`,
  `reporting`, `engagements`, `notifications`, `portal`.
- Flags (A-08-T03, default false): `audits.fieldwork_testing`, `audits.analytics`,
  `audits.confirmations`, `audits.ssars_workspace`, `sampling.monetary_unit`,
  `audits.fieldwork_agents`. Kill switch (control, not a flag): `confirmation_links` (ADR-157).
- Out of scope (epic §2.3): SHL-19 review packages (K-04), agent-proposed extra JE flags (A-11),
  model-drafted client or respondent wording (N-03), an external confirmation network, negative
  confirmations, HR or ticketing populations, a live NetSuite connector, AUD-27, statements studio.

## 5. Acceptance criteria
Invariants asserted everywhere (F-04 `assertInvariants`): INV-1 the agent never decides; INV-2
every citation shown is verified; INV-3 walls hold (404, no counts); INV-4 portal scopes are
isolated; INV-5 attribution is correct ("‹person› via Agent" for runs; a named human, or a
link principal with a verified email fingerprint, for every decision or submission).

### F0 · Contract, data and vocabulary (S45 rows)
- **AC-0.1 (T01)** Every artboard maps to one fixture scenario, one endpoint set and one parity tier
  in its `docs/screens/<ID>.md`, and each screen adds loading, error, not-allowed and flag-off rows.
- **AC-0.2 (T01)** Codegen emits the new status StrEnums (`confirmation`, `link_principal`, `je_test`,
  `je_criterion`, `fieldwork_test_result`, `sample_expansion`, `analytics_set`, `analytics_line`)
  and their `status.gen.ts` words; the copy lint rejects "opinion" on AUD-26.
- **AC-0.3 (T03)** The generated matrix test denies the agent principal every adopt, accept, decide,
  send and close action in the A-08 rows; every client principal is denied every confirmation route.
- **AC-0.4 (T05)** Every stub route answers 501 under its one action behind its flag; typed fixtures
  foot 236 unique hits, 14 = 8 + 6 lines and 4,174,000 revenue.
- **AC-0.5 (T05)** The consumer suite asserts coverage 897,950 / 5,860,000 = 15.3%, one confirmation
  per POR-17 payload and no client-visible confirmation field.
- **AC-0.6 (T06)** The confirmations stub serves POR-17 a–f fixtures only on the fixture tenant, and
  every client principal gets 404 on every confirmation route.
- **AC-0.7 (T09)** Existing snapshots report the JE fields as unavailable; new imports fill them where
  the export carries them; no immutable row is updated.
- **AC-0.8 (T08)** The loaded scenario ties 214 of 214 accounts at $0.00 and its criteria hit exactly
  142, 38, 61, 17 and 9 for 236 unique entries.
- **AC-0.9 (T10)** Pure scoring functions reproduce the seed's hits, and every non-zero score carries
  at least one reason code.

### F1 · JE testing (AUD-12 a, d, e)
- **AC-1.1** Creating a JE test builds a `general_ledger` population (18,426 entries, 412,903 lines)
  and records the tie "214 of 214 accounts · $0.00"; scoring is refused 409 `population_not_tied`
  until the tie reads `tie`.
- **AC-1.2** Scoring evaluates every entry in code: 142 · 38 · 61 · 17 · 9 → 236 unique; weekend hits
  are true Saturdays and Sundays; Fri Jul 3, 2026 carries "Holiday" from the published set.
- **AC-1.3** A snapshot without posting user or source shows "Manual by senior management" as "Not
  available from this ledger" with 0 hits, and the unique count excludes it.
- **AC-1.4** A selection of score ≥ 61 plus 6 unpredictable picks writes a sample-set version
  (`je_score_selection`, seed, sampler version) with 34 + 6 = 40 items; approval is by someone other
  than the preparer.
- **AC-1.5** The agent's values arrive as suggestions with verified region citations; only value chips
  are source links; JE-26-17994's difference $1,246.85 and "below CT $7,750" are code.
- **AC-1.6** The agent never writes `pass`, `exception` or `no_effect`; unsupported rows read "Needs
  human".
- **AC-1.7** "Adopt results (L1)…" records an L1 sign-off with the version's content hash; a later
  change stales it.
- **AC-1.8** "Raise exception…" submits through `assurance.api.record_finding` and AUD-15 lists it;
  the agent cannot raise it.
- **AC-1.9** "JE Testing.xlsx" is byte-identical for the same version, accounts masked to the last four.

### F2 · Tests of details and controls (AUD-12 b, c)
- **AC-2.1** Northwind's 25 rows recalculate in code; rows 8 and 15 flag "No deferral, no opt-out → EBP-03".
- **AC-2.2** 0 deviations of 25 read UDL 8.8% < tolerable 10%; 2 of 25 recompute 19.9% and turn amber.
- **AC-2.3** The segmented control keeps per-variant state; Escape closes dialogs and sheets.

### F3 · Expand testing (AUD-12 f, g, h)
- **AC-3.1** The sheet computes "Selected becomes 50"; an empty rationale or no approver answers 422
  `expansion_rationale_required` / `approver_required`.
- **AC-3.2** A request leaves the 40 entries, scores and attributes unchanged and raises a HOME-02 gate
  `sample_expansion_approval` for the named approver.
- **AC-3.3** Approval appends exactly the next 10 by score; the first 40 keep their positions
  (`items_hash` of the prefix); the decider is the named approver, never the requester or the agent.
- **AC-3.4** Northwind's "Add participants" follows the same rule.

### F4 · Monetary-unit sampling (J04 step 8)
- **AC-4.1** The same seed and sampler version reproduce identical items; every item at or above the
  interval is selected; existing sampler versions are untouched.

### F5 · Analytics (AUD-13 a–e)
- **AC-5.1** 14 lines evaluate against 10% **and** $116,250; interest at 26.8% stays Within; tallies
  read 14 · 8 · 6 · 2.
- **AC-5.2** A decided materiality computes a new set version without editing the old one.
- **AC-5.3** An explanation without a verified citation is refused 422 `explanation_uncited`.
- **AC-5.4** "Send to client" publishes a T-02 questionnaire built from firm templates; only a person sends.
- **AC-5.5** An answered line reads "Client answer Sep 16 · Luis Ferrante"; the acceptor is never the author.
- **AC-5.6** The Final tab reads adjusted FY2026 against audited FY2025 (DV-5), pre-tax income −114,480.

### F6 · Confirmations (AUD-14 a–e)
- **AC-6.1** A client-only address disables Send with the red helper and the API answers 409
  `address_not_verified`.
- **AC-6.2** An address is `independent` only with a non-client source cited.
- **AC-6.3** One C7 envelope (`confirmation_authorization`) per request; tiles read Draft 3 ·
  Authorization requested 1.
- **AC-6.4** Send issues single-use link principals and template emails; C1 is a recorded network send;
  an agent or client send is refused.
- **AC-6.5** Unreconciled $0.00 and the Below CT comparison are code; only a manager or EP who did not
  enter the reconciliation may accept it (403 otherwise).
- **AC-6.6** A non-response prompts a second request after the firm interval and alternative procedures
  after expiry.
- **AC-6.7** Coverage reads $897,950.00 of $5,860,000.00 (15.3%); tiles sum to the log.
- **AC-6.8** A client principal gets 404 on every confirmation route and response id.

### F7 · Respondent page and link principal (POR-17 a–f)
- **AC-7.1** The page returns data for this confirmation only; invoice detail foots 138,200 + 151,750 +
  122,650 = 412,600.
- **AC-7.2** `POST …/code` answers 202 after a padded minimum for any input; five wrong codes lock the
  link for 15 minutes.
- **AC-7.3** Submit needs a choice, a verified code and the attestation; the server recomputes the difference.
- **AC-7.4** Unknown, expired and revoked tokens are indistinguishable in status, body and timing (DV-7).
- **AC-7.5** A replayed POST answers 409 `already_answered` with the original receipt.
- **AC-7.6** The kill switch off renders d's copy on every `/v1/confirm/*` call.

### F8 · SSARS workspace (AUD-26 a–e)
- **AC-8.1** Review mode shows Inquiries · Analytics · FS · Report and no audit-only rows.
- **AC-8.2** Publishing the inquiry program reaches POR-05; the canvas reads "Answered 11 · Open 3".
- **AC-8.3** Revenue foots 4,174,000 and expenses 4,014,000; only Grants exceeds 10% and $50,000.
- **AC-8.4** The agent's explanation reads "I have not concluded — please review the explanation."
  until Laura accepts.
- **AC-8.5** Compilation shows "Read the FS for obvious material misstatements" (L1) and the AUD-23 report row.
- **AC-8.6** Preparation reads "No assurance is provided." on every page; a report is refused 409
  `no_report_for_preparation`.
- **AC-8.7** No SSARS surface says "opinion" (copy lint, AC-0.2).

### F9 · Agent seams (T23–T25)
- **AC-9.1** The agent principal holds none of `test.adopt`, `sample_expansion.decide`,
  `analytics.accept`, `client_question.send`, `confirmation.send`,
  `confirmation.accept_reconciliation`, `confirmation.close`.
- **AC-9.2** Injected respondent text cannot change a reconciliation proposal (containment 1.0).
- **AC-9.3** A closed data boundary shows DF-04 and records no model call.

## 6. Task map
S45: T01 this SPEC, screen contracts and vocabulary · T02 P-45 amendment (red) · T03 protected
bundle (red) · T06 confirmations stub · T05 stubs and consumer tests · T09 GL JE fields (red,
migration) · T08 Granite Peak content · T10 JE scoring v1. S46: T11 goldens, T12 JE test service,
T15 link principals, T16 confirmations core, T20 flux engine, T26 L3 kit, T33 tests. S47–S50 as
the epic's §9.

## 7. Deviations
DV-1 to DV-10 as the epic's §2.4, each recorded in its screen contract. DV-11 (DEC-5028): pen tests
are deferred (DEC-1389), so "after the Nov 2028 delta" reads "behind `audits.confirmations` and the
`confirmation_links` control until Ayush turns real respondent links on".
