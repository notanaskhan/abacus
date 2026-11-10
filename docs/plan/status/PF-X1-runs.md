# PF-X1 runs: every S0–S25 row that needs a pilot firm (DEC-4100)

Decided 2026-11-10 by Ayush (DEC-4100, amending DEC-1530 and DEC-1391 rule 2): every S0–S25 row
whose acceptance needs a pilot firm runs on the synthetic test pilot firm **PF-X1** (Brightwater
Hale), as an internal test of progress, and is reported as **synthetic (PF-X1)**, never as a live
firm's. The run records are in [`docs/ops/pilot/pf-x1/`](../../ops/pilot/pf-x1/README.md); the
real-firm version of each clause is a go-live check in
[`docs/ops/go-live/PF-X1.md`](../../ops/go-live/PF-X1.md) §Real-firm go-live checks.

## How the rows were found

`docs/plan/backlog.csv`, sprints 0 to 25, rows (any type) whose title or acceptance names a pilot,
LOI or live firm, a design partner, a partner firm, a champion or a PF code: 117 by search, read
one by one. **On this list (86):** the rows whose acceptance needs the firm itself. **Left off:**

| Why | Rows |
|---|---|
| Already ran on PF-X1 (DEC-1530, DEC-1680, DEC-2081) | Q-04-T050, Q-04-T054, T-01-T47, Q-04-T063, Q-04-T084 to T091 (S25.md) |
| "Pilot" names a period or a thing, not a firm (the 2027 Q3 lanes, the DR pilot light, code rows on the rehearsal tenant) | Q-03-T117 to T121, T126 to T128, T134, T135, T141 to T143, T149, T158, T163 to T165; Q-01-T29, Q-03-T058, Q-03-T116; Q-04-T001, T006 to T012, T015; T-02-T06, T-02-T14; P-11-T13; P-08-T29 |
| Programme cadence notes (solo rituals: the bookkeeping session's) | F-09-T19, T29, T40, T54, T60, T68, T76, T83, T88, T94, T100, T106, T112, T118, T124, T130, T136, T143, T150, T155, T162, T168, T174, T179, T185 |
| Counsel, vendor, price or company facts whose acceptance names no firm (DEC-2098) | F-09-T01, T02, T13, T16, T34, T45, T52, T58, T66, T78, T99, T132; F-09-T62 |
| Deferred under DEC-1389 (pen tests) | N-01-T29 (its per-firm flips wait on delta #1) |

Status words: **done** (the acceptance holds on PF-X1, synthetic), **partial** (part ran; the
reason and the command for the rest), **todo / blocked** (nothing could run; the reason).
Every row is marked the same way in `status-verified.csv`, evidence starting "synthetic (PF-X1)".

**Totals:** 25 done, 43 partial, 18 blocked.

## Go-live: dossiers, M9/M10, A1–A3, contract

Held PR branch `pfx1-go-live`.

| Row | S | Needs | Outcome | Evidence |
|---|---|---|---|---|
| F-09-T110 | 12 | first firm's contract-and-legal dossier section: synthetic signed MSA, DPA, pilot terms; pen-test letter (DEC-1389) | partial | docs/ops/go-live/PF-X1.md: contract-1 green (synthetic) from files/pf_x1/; contract-2 and contract-4 are counsel's and DEC-1389's |
| F-09-T114 | 13 | the second and third firms' contract sections (one test firm, DEC-1530) | blocked | blocked: no second or third firm; PF-X1 is the only test firm (DEC-1530) |
| Q-04-T021 | 15 | M9 dossier part N with `make go-live-check LEVEL=shadow` output, signed by both founders | partial | docs/ops/pilot/pf-x1/go-live-rehearsal.md: go_live --rehearse-real LEVEL=shadow fails 7 checks (provisioned, SSO, MFA, break-glass, provider terms, opt-in, no_writes); dossier filled; founders unsigned |
| Q-04-T022 | 15 | M9 dossier part AY; firm admin's written shadow-rules acknowledgement | partial | docs/ops/pilot/pf-x1/go-live-rehearsal.md: communications-1 green (synthetic), shadow rules acknowledged (synthetic); content-1 and integrations not green |
| Q-04-T024 | 16 | M9 shadow go-live A1: go-live-check LEVEL=shadow green (tenant.real rehearsed), dossier signed | partial | docs/ops/pilot/pf-x1/go-live-rehearsal.md: shadow flips under the flip guard; LEVEL=shadow not green (7 checks) |
| Q-04-T026 | 16 | A2 shadow go-live or the slide recorded | done | the PW1 slide for A2 is recorded in DEC-4100, owner AY; docs/ops/pilot/pf-x1/go-live-rehearsal.md |
| Q-04-T033 | 17 | A3 shadow go-live if a third firm signed, or closed as not needed | done | closed as not needed: no third audit firm signed (DEC-4100) |
| Q-04-T034 | 17 | A3 content load (conditional), or closed as not needed | done | closed as not needed: no third audit firm signed (DEC-4100) |
| Q-04-T039 | 18 | M10 R3: LEVEL=client_facing per firm, delta #1 closed (DEC-1389), both founders sign | partial | docs/ops/pilot/pf-x1/go-live-rehearsal.md: LEVEL=client_facing fails the same 7 checks; delta #1 deferred (DEC-1389) |

## Pilot 0 (S2–S15)

Held PR branch `pfx1-pilot0`.

| Row | S | Needs | Outcome | Evidence |
|---|---|---|---|---|
| F-09-T32 | 2 | M3 LOI count or the fallback: PF-X1 stands as Pilot 0 on synthetic data (DEC-4100 records the fallback) | done | docs/ops/pilot/pf-x1/pilot-0.md: 0 signed LOIs; the M3 fallback (Pilot 0 on synthetic data) is recorded by DEC-4100 |
| F-09-T33 | 2 | Google Workspace check across LOI firms: PF-X1's synthetic mail and identity profile; CASA go/no-go is Ayush's (DEC-2098) | partial | docs/ops/pilot/pf-x1/pilot-0.md: PF-X1 runs no Google Workspace, so no CASA application; the CASA go/no-go is Ayush's (DEC-2098) |
| F-09-T51 | 3 | discovery notes per LOI firm on ledger, tax engine, e-signature: PF-X1's seeded stack (fake QBO/NetSuite, fake CCH, DocuSeal) | done | docs/product/discovery/pf-x1-discovery.md: ledger, tax engine, e-signature from the scenario |
| F-09-T56 | 4 | Pilot 0 plan: dated sessions, a sandbox request, the firm's PBC template for import (synthetic workbook in the scenario) | done | docs/ops/pilot/pf-x1/pilot-0.md: waves A-F walked 2026-11-10; PF-X1 is the sandbox; PBC template = Northwind AUD-03 |
| Q-01-T55 | 4 | three staging provisions with synthetic = true (staging only: `make seed-staging`, TenantProvisioningWorkflow) | partial | staging-only: make seed-staging RESET_CLOCK=E0 plus two TenantProvisioningWorkflow runs with synthetic = true (Ayush) |
| F-09-T61 | 5 | Pilot 0 readiness dry run of the J02 script on the demo tenant (local stack; staging for the hosted walk) | partial | docs/ops/pilot/pf-x1/pilot-0.md: J02 passed in fixture mode; staging walk: pnpm -C apps/web exec playwright test --project=staging e2e/journeys/J02-client-onboarding.spec.ts |
| F-09-T69 | 6 | session wave A: J02-audit-core and J12-core walked on PF-X1, notes filed | done | docs/ops/pilot/pf-x1/pilot-0.md: wave A, J02 and J12 fixture walks passed (40 passed, 14 skipped in the run); no issue to file |
| F-09-T70 | 6 | usability log: each finding with screen ID, state letter, severity, owning epic | done | docs/ops/pilot/pf-x1/pilot-0.md: automated walks found no S1/S2 finding; abacus_tools.quality.pilot_log passes |
| F-09-T72 | 6 | tax-partner track: a named CCH admin (seeded persona), 5-15 returns sketched, Apr-May sessions | partial | docs/ops/pilot/pf-x1/pilot-0.md: CCH admin = the seeded Tax Manager seat; Feld 2025 enrolled; the 5-15 returns not listed |
| F-09-T73 | 6 | M5 checkpoint: attendance, champion responsiveness (RK-02), RK-01 trigger | partial | docs/ops/pilot/pf-x1/pilot-0.md: M5 note for PF-X1; RK-01 is met in fact (no real LOI): the wedge review is Ayush's |
| F-09-T74 | 6 | negotiation round 1: the draft agreement and a named champion per LOI firm (draft text needs counsel, DEC-2098) | partial | docs/ops/pilot/pf-x1/pilot-0.md: champion named (practice leader seat); the draft agreement is counsel's text (DEC-2098) |
| F-09-T77 | 7 | session wave B: J02/J12 retests; the firm's PBC template through the legacy request-list import | partial | docs/ops/pilot/pf-x1/pilot-0.md: J02/J12 retests passed; legacy request-list import not run (make dev: ImportRequestList on PF-X1) |
| F-09-T82 | 7 | each partner's reaction to the founding price in pricing-signals.md (a price is Ayush's, DEC-2098) | blocked | blocked: a synthetic firm's price reaction is no signal and the price is Ayush's (DEC-2098) |
| F-04-T32 | 8 | J04-PBC slice walkable on staging; Sep 24 snapshot loaded for Pilot 0 | partial | docs/ops/pilot/pf-x1/pilot-0.md: J04 passed in fixture mode; staging walk and the Sep 24 snapshot load are staging-only |
| F-09-T84 | 8 | session wave C: J04-PBC slice (request, portal upload, scan, screening, accept or return) | partial | docs/ops/pilot/pf-x1/pilot-0.md: J04-PBC fixture walk passed; full stack (portal upload, scan, screening) needs make dev + make e2e |
| F-09-T86 | 8 | agreement round 2 with counsel's redlines (counsel, DEC-2098) | blocked | blocked: counsel's redlines (DEC-2098) |
| F-09-T89 | 9 | session wave D: J04-PBC on the partner's PBC list | done | docs/ops/pilot/pf-x1/pilot-0.md: wave D, J04-PBC on Northwind's AUD-03 list passed (fixture) |
| F-09-T93 | 9 | top-10 usability list v1 with owning epic and target sprint | done | docs/ops/pilot/pf-x1/pilot-0.md: top-10 v1 is empty (no S1/S2 finding) |
| F-09-T95 | 10 | session wave E: audit cockpit and TB import | done | docs/ops/pilot/pf-x1/pilot-0.md: wave E, A02 TB connections and J23 cockpit passed (fixture) |
| F-09-T101 | 11 | session wave F: top-10 retests; PBC template re-imported through KNW-01 | partial | docs/ops/pilot/pf-x1/pilot-0.md: KNW-01 catalog walk passed; nothing to retest; the workbook re-import through KNW-01 not run |
| F-09-T109 | 12 | tax session 1: the CCH admin imports one synthetic export file into the fake CCH; differences logged | done | docs/ops/pilot/pf-x1/pilot-0.md: fake CCH import of a synthetic export, 30 passed, no difference logged |
| F-09-T113 | 13 | tax session 2: format differences closed; K-1 release walkthrough | partial | docs/ops/pilot/pf-x1/pilot-0.md: no format difference to close; the K-1 release walkthrough not walked |
| A-01-T27 | 13 | every A-01 item on the top-10 list closed or scheduled before M9 | partial | firm part only: docs/ops/pilot/pf-x1/pilot-0.md, the synthetic top-10 has no A-01 item; the C6 v1 code part is not judged here |
| F-09-T121 | 14 | Pilot 0 exit: each PW0 criterion met or re-dated | partial | docs/ops/pilot/pf-x1/pilot-0.md: top-10 empty, ledger choice recorded; template approvals are counsel's |
| F-09-T122 | 14 | PW1 engagement selection per firm with a PHI check (PF-X1's enrolled Feld return and Northwind audit) | done | docs/ops/pilot/pf-x1/pilot-0.md: Feld 2025 return and Northwind PY2025 EBP audit enrolled; generated data, no PHI |
| F-09-T126 | 15 | retro per partner and PW1 success metrics signed off by the champion | partial | docs/ops/pilot/pf-x1/pilot-0.md: retro and W4-W7 signed off by the synthetic champion; W4-W8 not in thresholds.md (F-09-T62) |
| Q-03-T084 | 15 | the ten Pilot 0 issues closed or re-filed before M9 | done | docs/ops/pilot/pf-x1/pilot-0.md: no Pilot 0 issue was filed, so none is open |

## PW1 and PW2 operations (S14–S19)

Held PR branch `pfx1-pw1-pw2`.

| Row | S | Needs | Outcome | Evidence |
|---|---|---|---|---|
| A-01-T30 | 13 | a pilot rollback run from the runbook by a fresh session | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: flips with rollback links rehearsed; A-01's own pilot rollback runbook not rehearsed |
| Q-04-T014 | 14 | a test support request labelled and answered inside the SLA, no client data in the ticket | blocked | blocked: the shared inbox and office hours are outside the product; a test request needs the desk (Ayush) |
| Q-04-T020 | 15 | on-call rota: firm QI contact per pilot code; the test page (paging tool, Q-01-T41) | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: QI contact = the seeded IT / Security seat; the test page needs the paging tool (Q-01-T41) |
| F-09-T127 | 15 | the firm admin has seen the AI disclosure and records the opt-in in the product | blocked | blocked: the opt-in is refused until the providers' terms are registered (kernel/_provider_terms ENTRIES empty; Ayush, DEC-2098) |
| F-09-T131 | 16 | each firm's W6 baseline recorded | done | docs/ops/pilot/pf-x1/pw1-pw2.md: W6 baseline 14 days on both enrolments |
| Q-04-T025 | 16 | A1 content load through its screens: bulk client import, PBC templates, email templates, branding; admin sign-off | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: content is the seed's through service APIs; the firm admin's own screen load and sign-off is real-8 |
| Q-04-T027 | 16 | A2 content load (no A2: one test firm) | blocked | blocked: no A2 (one test firm, DEC-4100) |
| Q-04-T028 | 16 | a support session requested, approved by the firm, scoped to one work item, expiring in 2 h, audited | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: support requests allowed; the 2-hour session flow needs make dev and an operator session, not run |
| R-01-T34 | 16 | templates, portal settings and a verified sender domain per pilot firm (fake SES; real DKIM is DNS) | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: templates via the import API (P-11-T13), domain on the fake SES; real DKIM and MAIL FROM need SES and DNS |
| F-09-T138 | 17 | champion review with W2 and W8 shadow readouts | done | docs/ops/pilot/pf-x1/pw1-pw2.md: shadow-report readouts for four agents, all 0 runs |
| Q-04-T032 | 17 | per-firm sender domain verified in ADM-10, a test mail passing DKIM and DMARC (real SES) | partial | needs real SES and DNS: verify the sender domain in ADM-10 on staging, then a test mail through DKIM and DMARC (Ayush) |
| Q-03-T112 | 18 | at least 25 scored shadow decisions per agent per firm, or the reason to continue shadow | done | docs/ops/pilot/pf-x1/pw1-pw2.md: 0 scored decisions per agent; reason recorded: no agent cleared, opt-in blocked by unregistered provider terms |
| F-09-T144 | 18 | the champion's written shadow-exit confirmation (W8) | done | docs/ops/pilot/pf-x1/pw1-pw2.md: shadow exit not confirmed; PF-X1's shadow extended in two-week steps (the acceptance's alternative) |
| F-09-T145 | 18 | first invoice date and the 60-day cancellation deadline per firm (no amount) | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: no invoice date, PF-X1 is never client-facing; a real firm's dates go in the vault (real-7) |
| Q-04-T040 | 18 | M10 flip plan: every flag with owner, approver, rollback; first invitation wave agreed with the champion | blocked | not compiled in this run: the M10 flip plan from the R-01, N-01, P-04, G-02 and Q-02 rollouts |
| Q-04-T044 | 19 | PW2 launch: first invitation wave sent by a firm person; daily activation counts for 10 days | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: W4 0.0% (amber) for one day; a wave sent by a firm person and 10 daily counts not run |
| Q-04-T045 | 19 | K-02 flips per pilot firm with a written rollback; the firm publishes a standards version | partial | docs/ops/pilot/pf-x1/pw1-pw2.md: knowledge.firm_standards and rules.reference_sets on for PF-X1 under the flip guard; standards publish not run |
| Q-04-T348 | 18 | retire compliance.legal_holds once on at every live firm (rule 3, unchanged) | blocked | blocked: waits for every live firm (DEC-1530 rule 3, unchanged by DEC-4100) |
| Q-04-T349 | 19 | retire agents.client_data_optin and compliance.incidents once on at every live firm (rule 3) | blocked | blocked: waits for every live firm (DEC-1530 rule 3, unchanged by DEC-4100) |
| Q-04-T350 | 20 | retire compliance.firm_export; firm export works at every live firm (rule 3) | partial | blocked: waits for every live firm (DEC-1530 rule 3, unchanged by DEC-4100) |

## Tax pilot and the autumn window (S19–S25)

Held PR branch `pfx1-season`.

| Row | S | Needs | Outcome | Evidence |
|---|---|---|---|---|
| T-01-T22 | 18 | fake CCH adapter suite against the fake and the partner-validated sample files | done | docs/ops/pilot/pf-x1/season.md: fake CCH adapter suite passes against the fake and the scenario's sample files |
| T-01-T28 | 19 | PWT shadow enablement: consent templates as rows, CCH mappings, flags in shadow for the pilot firm | partial | docs/ops/pilot/pf-x1/season.md: consent templates are counsel's; CCH rows, mappings and shadow flags not set in this run |
| P-04-T47 | 19 | j06 coordination on staging with the fake CCH, the import checkpoint pending until the CCH admin approves | partial | staging-only: pnpm -C apps/web exec playwright test --project=staging e2e/journeys/J06-1040-season.spec.ts after make seed-staging; J06 passed in fixture mode |
| F-09-T158 | 20 | PWT champion check-ins; DocuSeal production KBA (Ayush's account) | blocked | blocked: DocuSeal production KBA is on Accrued's account (Ayush) |
| F-09-T166 | 21 | weekly W10 read from Aug 17 with an owner per exception | blocked | blocked: W10 has no metric source (pilot_metrics computes W4-W7) |
| T-02-T34 | 21 | shadow and rollout runbook rehearsed; flip plans approved by both founders | partial | docs/ops/pilot/pf-x1/season.md: runbook rehearsal is staging-only; the flip plans' approval is the founders' |
| Q-04-T061 | 22 | flag-calendar shows no expiry Sep 1-Oct 20 for any flag on at a live firm | done | docs/ops/pilot/pf-x1/season.md: no flag expires Sep 1-Oct 20, 2027; season.flags_outside_window pass |
| Q-04-T064 | 22 | window notice acknowledged by every live firm's champion and admin | done | docs/ops/pilot/pf-x1/season.md: notice acknowledged by PF-X1's synthetic champion and admin seats |
| Q-04-T065 | 22 | system-of-record confirmation naming the firm person; `make pilot-mode --mode system_of_record` | done | docs/ops/pilot/pf-x1/pw1-pw2.md: Northwind's audit to system_of_record confirmed by the seeded practice leader; refused without a confirmer |
| Q-04-T072 | 23 | deadline-week Sep 13-17 desk: champion contacts and KBA fallbacks logged with first-response times | partial | docs/ops/pilot/pf-x1/season.md: no champion contact or KBA fallback (no live channel) |
| Q-04-T077 | 24 | Tuesday slot Sep 21: sampling.sample_sets per pilot firm after the audit CPA's memo, staging green, both approvals | partial | docs/ops/pilot/pf-x1/season.md: window_rehearsal Sep 21 19:05: slot open, defect_only promotes; the CPA memo, staging and both approvals open |
| Q-04-T079 | 24 | deadline-week Sep 27-Oct 1 desk: champion contacts logged with first-response times | partial | docs/ops/pilot/pf-x1/season.md: no champion contact (no live channel) |
| F-09-T151 | 19 | July retro per partner with its season-2 intent | done | docs/ops/pilot/pf-x1/season.md: PF-X1's retro records its season-2 intent (stay the rehearsal firm) |
| F-09-T146 | 18 | season-2 agreement sent to every partner (agreement text needs counsel) | blocked | blocked: the season-2 agreement is counsel's text (DEC-2098) |
| F-09-T152 | 19 | season-2 negotiation round 1 (counsel, prices: DEC-2098) | blocked | blocked: counsel and prices (DEC-2098) |
| F-09-T154 | 19 | a partner-approved reference (a synthetic firm's reference is no reference) | blocked | blocked: a synthetic firm's reference is no reference |
| F-09-T156 | 20 | season-2 final draft with counsel's redlines (counsel) | blocked | blocked: counsel's redlines (DEC-2098) |
| F-09-T142 | 17 | counsel-approved taxpayer FAQ and partner guidance (counsel) | blocked | blocked: the taxpayer FAQ is counsel-approved (DEC-2098) |
| F-09-T176 | 23 | Type II report distributed to every live partner (no Type II exists) | blocked | blocked: no SOC 2 Type II report exists |
| F-09-T178 | 23 | Sep 15 deadline week: no partner request becomes a live-path change | done | docs/ops/pilot/pf-x1/season.md: window_rehearsal refuses a non-hotfix release in the Sep 13-17 deadline week; no partner request made |
| F-09-T184 | 24 | Sep 30 deadline week: no partner request becomes a live-path change | done | docs/ops/pilot/pf-x1/season.md: window_rehearsal refuses a non-hotfix release in the Sep 27-Oct 1 deadline week; no partner request made |
| Q-03-T151 | 24 | monthly live-stage accuracy sample, 25 outputs per agent per firm, labelled | blocked | blocked: no agent at live stage on PF-X1, so no sample; labelling is a person's |
| Q-04-T037 | 17 | S17 support reserve: hours logged, first responses inside the SLA | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T042 | 18 | S18 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T047 | 19 | S19 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T052 | 20 | S20 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T060 | 21 | S21 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T069 | 22 | S22 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T075 | 23 | S23 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
| Q-04-T082 | 24 | S24 support reserve | partial | docs/ops/pilot/pf-x1/season.md: no request reached the AY-lane desk (no live channel); 0 hours, RK-07 not raised |
