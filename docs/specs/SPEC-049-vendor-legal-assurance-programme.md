---
id: SPEC-049
title: "F-09 vendor, legal, assurance and design-partner programme: sprint 0 and sprint 1 (tracker, vendor filings, counsel, assurance vendors, discovery, LOIs)"
status: approved
owner: builder
risk_zone: red
related_adrs: [ADR-005, ADR-040, ADR-045, ADR-111, ADR-112, ADR-113, ADR-114, ADR-115]
related_specs: [SPEC-036]
created: 2026-10-20
updated: 2026-10-20
---

> **Instructions for coding agents**
> - This is a non-code epic. Nothing here changes a code path or adds a flag. Every output is a document, a ticket, a filing or a vault record.
> - Implement only what this spec describes. If anything is ambiguous or contradicts an ADR, record the answer in `docs/product/decision-log.md` using the plan's proposed option, and carry on.
> - Solo edition (`docs/plan/AMENDMENT-solo.md`): there is one builder. No owners, approvers, second signatures or "other founder" checks. Read any such plan wording as "the builder".
> - Never write an amount in git. Prices, quotes, contract text, partner firm names and counsel advice live in the vault outside git; git holds status, dates and a vault reference.
> - Vendor applications get no task file. The builder submits them by hand from the SU-26 checklist and records the submitted date in the tracker.

## 1. Summary
F-09 starts every external clock the plan depends on: the vendor and legal tracker, the long-lead vendor applications, counsel, the SOC 2 and pen-test vendors, and the first design-partner conversations. This spec covers its sprint 0 (Mon Oct 19 to Fri Oct 30, 2026, milestone M1) and sprint 1 (Mon Nov 2 to Fri Nov 13, 2026) rows. Source: `docs/plan/epics/F-09.md` sections 0, 3, 9, 10 and 11, and `docs/plan/epics/F-09.tasks.csv`.

## 2. Problem and context
Every real-data milestone waits on third parties with lead times (vendors, counsel, auditor, pen tester, insurance, partners). If an application is filed late the dependent slice slips, and if a figure is promised that the plan does not hold, a contract or questionnaire answer becomes wrong in writing. F-09 files everything in week 1, keeps one tracker, and checks every outward claim against the plan of record.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Builder | Files every application, runs the tracker, engages counsel, holds the discovery calls, and checks their own outward claims before they leave |
| Counsel | Gives dated answers batched by gate; advice stays in the vault |
| Vendors (Intuit, Wolters Kluwer, Microsoft, DocuSign, WorkOS, Temporal, Sentry, Better Stack, AWS) | Review applications and issue terms |
| Design-partner firms | Take discovery calls and receive the LOI |

## 4. Goals and non-goals
**Goals**
- Every chapter 06 section 7.6 application has a submitted date by M1 (Fri Oct 30).
- Counsel is engaged with a dated scope, and the SOC 2 compliance tool is contracted, by Fri Oct 30.
- At least 6 conversations are booked by M1 and thresholds W1 to W3 exist before the first call.
- Sprint 1 follow-ups: Xero and NetSuite enquiries, counsel early answers by Fri Nov 13, wave-1 interviews, auditor quotes, first policies in the tool.

**Non-goals**
- Writing the vendor applications' text here. The SU-26 checklist holds the steps.
- Any product screen, flag or code path.
- Sprint 2 and later rows (M3 read, LOIs signed, auditor selection, pen-test RFP, retention floors).
- Payments in the product (ADR P-27); applying to any IRS e-file programme (R-04).

## 5. User stories and acceptance criteria
### Story 1: As the builder I want one tracker and one vault so that no approval silently stalls
- **AC-1** Given chapter 06 section 7.6's vendor table, when the tracker task lands after F-01-T01 makes the repo private, then `docs/ops/vendors/README.md` has one row per application with owner, start, typical lead time [verify], needed-by date, fallback and linked decision, and each row has a GitHub issue labelled `vendor`. Every row has an owner, start date, needed-by date and fallback.
- **AC-2** Given any contract, quote, LOI, partner firm name or counsel memo, then it lives in the vault, and the tracker holds only status, dates and a vault reference. Git holds no price, contract text, partner firm name or counsel advice. Counsel advice stays out of git to protect privilege; prices stay out because vendor terms are often confidential.
- **AC-3** Given the repo is still public on Mon Oct 19, then no issue is opened and nothing is committed until F-01-T01 is done.
- **AC-4** Given Decision Day (Fri Oct 23), when the formation documents, founder agreement and IP assignment are reviewed, then they are filed in the vault and noted beside DEC-03 by Fri Oct 23; if any is missing, partner contracting pauses until it is signed (chapter 11 RK-59).
- **AC-5** Given DEC-03 on Oct 23, when the envelope is approved, then the vault ledger carries each chapter 01 section 1.6.7 line, the cash position and months of runway, and every commitment needs the builder's signature (money never defaults on silence).
- **AC-6** Given monthly spend that exceeds the envelope pro rata for two months, or a quote more than 25% above its line, then RK-05's action applies: optional vendors are deferred; gate spend (SOC 2, pen test, insurance, counsel) never is.
- **AC-7** Given Contract Monday, when the sprint opens, then the note lists every open application, contract and partner with its status, and any RK trigger that fired gets its pre-agreed action that day (chapter 11 section 11.8).

### Story 2: As the builder I want everything filed in week 1, read-only and truthful
- **AC-8** Given DEC-17, when S0 ends (M1, Fri Oct 30), then Intuit (read scopes only), Wolters Kluwer, Microsoft publisher verification, the DocuSign developer account and Go-Live plan, domains, WorkOS, Temporal Cloud, Sentry, Better Stack and GitHub terms each have a submitted date, and the SES production-access and Bedrock quota requests are filed in the AWS account.
- **AC-9** Given Xero and NetSuite SDN, then they are filed as no-fee enquiries on Nov 2 (chapter 06's start date), carry a dated ticket, and no spend is committed on either before Fri Nov 20 or before DEC-70.
- **AC-10** Given an application asks for scopes, then it requests read-only access: no write scope exists until its adapter ADR is accepted (ADR P-17, ADR-040; the W1 posting ADR P-16 for QuickBooks).
- **AC-11** Given a domain purchase, then the portal domain never contains "accrued" (DEC-59, ADR P-11; ADM-10d's fallback host must not reveal the vendor).
- **AC-12** Given the IRS e-file programmes, then nothing is applied for (R-04).
- **AC-13** Given a security questionnaire, when the builder answers it from the ADRs and the threat model, then the builder's own check confirms no answer promises a control, region or certification that the plan of record does not hold on that date, checked against commercial terms, the LOI template and every external claim.
- **AC-14** Given a counsel brief that states technical facts (data flows, regions, sub-processors as in `provider-terms.yaml` and ADR-113), then the builder checks that every technical statement matches an accepted ADR or the register before it is sent.
- **AC-15** Given discovery, when fewer than one design partner runs Google Workspace, then no OAuth or CASA application is filed; when DEC-70 picks QBO, then Xero and NetSuite stay as enquiries until a partner's ledger mix justifies them.
- **AC-16** Given a vendor has not answered within twice its typical lead time, then its chapter 06 section 7.6 fallback is invoked and the dependent slice slips, never the gate (RK-47): file bridge for CCH, file import for ledgers, record mode for signatures, forwarding or upload for the mailbox.
- **AC-17** Given an open application, then no application waits more than 3 business days on an Accrued reply (Intuit assessment questions, Entra verification evidence, DocuSign Go-Live kick-off on Mon Nov 2).

### Story 3: As the builder I want the assurance vendors started on dates
- **AC-18** Given DEC-26, then the compliance tool is contracted by Fri Oct 30, the auditor's engagement letter (as-of Mon Mar 1, 2027; March fieldwork) is signed by Fri Dec 11 (M4), and the pen-test SOW (Feb 15 to Mar 5, retest by Apr 9) is signed by Fri Dec 4.
- **AC-19** Given any auditor or pen-test candidate, when it is a design-partner or target-list firm, then it is excluded (independence; chapter 01 M4, chapter 06 section 5.6).
- **AC-20** Given the SOC 2 auditor RFP (Type I as of Mon Mar 1, 2027; Type II window May 1 to Jul 31; March fieldwork slot), then at least 3 written quotes with March fieldwork slots are in hand by Fri Nov 13.
- **AC-21** Given chapter 06 section 5.7, then draft SOC 2 policies are in the compliance tool by Fri Nov 13, each control area citing its ADR.

### Story 4: As the builder I want counsel engaged with dated, batched requests
- **AC-22** Given RK-50, when counsel is engaged by Fri Oct 30, then the engagement letter lists requests batched by gate: Nov 13 early answers; Nov 27 retention and offshore; Dec 4 e-signature; Dec 11 provider-terms review; Jan 29 M7 drafts; May 14 M8 tax pack; Aug 6 M13 Pub 1345 pack.
- **AC-23** Given DF-11 and DF-16 are due Fri Nov 13, when counsel answers, then SIG-01a and POR-06h stop saying "3 failed KBA → 24-hour lockout" or "1 try left today" (after three failures remote signing closes and the signer is routed to a handwritten 8879), and ADM-04h lists "Amazon Web Services (Bedrock) · model inference · US", generated from the register, with the section 7216 AI-disclosure recipients using the same source.
- **AC-24** Given counsel cannot answer by the date, then the row is re-dated to counsel's committed date; it never defaults on silence. Counsel's answers for DF-11 and DF-16 are recorded against those rows by Fri Nov 13, or both rows are re-dated.

### Story 5: As the builder I want discovery and LOIs that promise only what the plan holds
- **AC-25** Given chapter 11 section 11.6.1, when the first call is booked, then `docs/product/discovery/thresholds.md` already holds W1 to W3 and merges before the first call; they may later be tightened, never loosened; the three blanks in `docs/product/build-plan.md` section 4.1 point to it; and the interview guide covers ledger, tax engine, e-signature, mailbox, Google or M365, PHI exposure, SQMS needs and pricing, giving the inputs to DEC-25, DEC-49, DEC-70, DEC-75 and proposed DEC-100.
- **AC-26** Given chapter 01 section 1.6.4 profiles, then each window (audit/EBP 2 to 3 firms, extension-season tax 1 to 2 on CCH Axcess, CAS 1 on QBO) has a named list of at least 5 firms in the vault by Fri Oct 30, and at least 6 conversations are booked by Fri Oct 30 (M1).
- **AC-27** Given discovery notes, then they use firm codes only and no client data is collected (DEC-05); anonymisation rules are written in the interview guide.
- **AC-28** Given wave 1, then at least 8 interviews (partners, managers, seniors and audited-company controllers) are held by Fri Nov 13, each against the guide and its thresholds.
- **AC-29** Given wave-1 notes, then at least 8 notes merge by Fri Nov 13 under `docs/product/discovery/interviews/`, each tagged for W1 to W3, with no firm or client name; ledger, tax-engine, e-signature and mailbox tallies are started.
- **AC-30** Given the LOI template, then it states synthetic-only use until the real-data gate (DEC-05), chapter 01's windows (shadow Tue Jun 1, client-facing Tue Jul 13, 2027), no fees before the first client-facing month, and a named champion. It never promises autonomous agent decisions (INV-1), model-written client text (ADR-111; ADR P-25 off), group audit before Dec-2028 year-ends (DEC-65), or SQMS screens for 2026 (chapter 01 section 1.7.2).
- **AC-31** Given a qualified call, then the firm receives the LOI within 3 business days of its call, after a screen-share walkthrough of the design-handoff prototypes (no files sent).
- **AC-32** Given the pricing questions for proposed DEC-100, then the instrument asks the same way in every call (platform fee, seats by service-line bundle, agent-minute pool per DEC-51 and ADR P-28; no payments in the product per ADR P-27), and pricing signals are captured in comparable form in every wave-1 interview.

### Story 6: As the builder I want a recorded M1 result
- **AC-33** Given Fri Oct 30 (M1), then the builder records the M1 result in `docs/product/decision-log.md`: every chapter 06 section 7.6 application has a submitted date (Xero and NetSuite on Nov 2), counsel is engaged with a dated scope, the compliance tool is contracted, at least 6 conversations are booked, and thresholds W1 to W3 merged before the first call; any unfiled application is named with a date.
- **AC-38 Partner feature requests triaged (F-09-T128; DEC-19).** Every request in `docs/ops/pilot/feature-requests.md` is triaged against D1–D10 and X-01…X-08 and has a written answer (date and vault reference) naming its epic, its deferral (an epic's cut list or D10) or its exclusion (X-01…X-08, or D4, D6, D7, D8); `abacus_tools.quality.feature_requests` refuses a row that does not (check-fast).
- **AC-37 PW1 AI opt-in briefing (F-09-T127; SPEC-036).** Before Tue Jun 1, 2027, each PW1 firm admin has been walked through the product's own disclosure (provider and region, no training or retention beyond the listed exceptions, sub-processors, letter wording, the register's review date, shadow stages, the per-engagement switch), recorded in `docs/ops/pilot/ai-optin-briefing.md` by pilot code and date, and the opt-in is the firm's own act in the product, read by `make go-live-check` as `ai.client_data_opt_in`.
- **AC-36 Pilot 0 retros and PW1 success metrics (F-09-T126).** By Fri May 28, 2027, `docs/ops/pilot/retros/README.md` indexes, by pilot code, each Pilot 0 partner's retro (held on, note in the vault) and its champion's signed-off PW1 success metrics (the PW1 exit, W2b, W6 and W8 with their `thresholds.md` bands); notes and sign-offs stay in the vault, and new capability requests go to F-09-T128's triage, never promised in a retro.
- **AC-35 M8 tax go/no-go, criteria (b) and (c) (F-09-T125).** On Fri May 28, 2027, `docs/ops/gates/M8-tax-go-no-go.md` records criterion (b) (a tax partner signed for 5–15 extended returns; its CCH admin's written sign-off on the file format) and criterion (c) (counsel-approved §7216 text naming AWS Bedrock; the DocuSign ID Verification contract signed) each as met or not met with its evidence by vault reference, and the GO/NO-GO is a DEC row the same day.
- **AC-34 Contract Monday (F-09-T124; F-09 A4).** Each sprint's note (`docs/ops/programme/contract-monday/`, made by `abacus_tools.contract_monday` from the tracker and the risk register) lists every open application, contract and partner with its status and flags those past their Needed-by date; each named trigger (S15: RK-01, RK-04, RK-05, RK-47, RK-50) carries its early-warning signal and contingency, and a fired one has its pre-agreed action written that day; the note holds no price, contract term, partner name or counsel advice.

## 6. Behaviour and flows
**Happy path**
1. Week 1 (Oct 19): once F-01-T01 makes the repo private, create the tracker and the vault; file the company foundation record by Oct 23.
2. Submit each vendor application by hand from the SU-26 checklist and write its submitted date into the tracker (AC-8).
3. Engage counsel and contract the compliance tool by Oct 30; book 6 conversations (AC-18, AC-22, AC-26).
4. Write the thresholds and the guide, then take calls (AC-25, AC-28).
5. At M1, run the builder's own check and record it (AC-33).

**Alternate paths**
- Repo still public: do not open issues or commit; record in the vault until F-01-T01 lands (AC-3).
- Vendor late: invoke the fallback (AC-16). Counsel late: re-date, never default (AC-24).

**State transitions:** N/A (no entity changes state).

## 7. Domain and data changes
- **Entities affected:** none. Documents only: `docs/ops/vendors/README.md`, `docs/product/discovery/thresholds.md`, `docs/product/discovery/interviews/`, `docs/product/decision-log.md` entries, and the vault (outside git).
- **Invariants:** git never holds a price, contract text, partner firm name or counsel advice (AC-2). Thresholds are tightened, never loosened (AC-25).
- **Migrations:** none.
- **Versioning and immutability:** thresholds only tighten; decision-log entries are append-only.
- **Retention:** vault records kept per counsel's retention advice; discovery notes carry firm codes only.

## 8. Interfaces
N/A: no API or event. The outputs are documents and GitHub issues labelled `vendor`.

## 9. Authorisation and tenancy
N/A: no product data and no tenant. Access to the vault is the builder's alone.

## 10. AI behaviour
N/A: no model calls. No document may claim an agent decides, attribute a human decision to an agent, or cite an unverified number (INV-1, INV-2, INV-5).

## 11. Integrations
- **External systems:** vendor consoles and portals; the AWS account for SES and Bedrock requests (the account exists only after Q-01-T01).
- **Rate limits and quotas:** vendor review times, tracked as typical lead time [verify].
- **Retries and backoff:** follow up within 3 business days (AC-17).
- **Idempotency:** one tracker row and one issue per application.
- **Failure behaviour:** fallbacks per AC-16.

## 12. Edge cases and failure modes
- Repo still public when work starts: hold issues and commits (AC-3).
- DEC-59 changes after the domain is bought: the cost of an unused domain is trivial; buy per the recommended answer.
- A candidate auditor or pen tester is a target-list firm: excluded (AC-19).
- Counsel misses a date: re-date to counsel's committed date (AC-24).
- A questionnaire or LOI claim is ahead of the plan: remove the claim (AC-13, AC-30).

## 13. Security and privacy
- **Data classification:** confidential (vendor terms, counsel advice, partner identities).
- **PII involved:** interviewees' names stay in the vault; notes carry firm codes only.
- **Secrets used and where they live:** vendor account credentials in the builder's password manager; never in git.
- **Threats considered:** the repo is public until F-01-T01; privilege loss by committing counsel advice.
- **Mitigations:** vault outside git; tracker holds status, dates and a vault reference only; `docs/ops` is committed only after the repo is private.

## 14. Audit trail and evidence integrity
- **Actions logged:** tracker status, submitted dates, `decision-log.md` entries (M1 record, DEC records).
- **Provenance captured:** each tracker row links its decision and vault reference.
- **What must be immutable:** decision-log entries once recorded; thresholds can only tighten.

## 15. Observability
N/A: no runtime. The Contract Monday note is the review loop (AC-7).

## 16. Performance and scale
N/A. Volumes: about a dozen applications in S0; at least 8 interviews in wave 1.

## 17. UX
N/A: F-09 builds no screen. Its outputs fix copy and availability for screens owned elsewhere (DF-11 and DF-16 wording, AC-23).

## 18. Test plan
Verification is by document check: `cd backend && uv run python -m abacus_tools.quality.validate_docs` for the files in git, and a vault and tracker review for the rest.

| AC | Test type | Description |
|---|---|---|
| AC-1 | doc check | Tracker has a row per section 7.6 application with the six fields and a `vendor` issue |
| AC-2 | doc check | Repo search finds no price, contract text, partner firm name or counsel advice |
| AC-3 | doc check | No tracker file or vendor issue is dated before F-01-T01 |
| AC-4 | doc check | Vault holds the formation record; note beside DEC-03 |
| AC-5, AC-6 | doc check | Vault ledger lines present; the 25% and two-month triggers written in the ledger header |
| AC-7 | doc check | Contract Monday note lists all open items |
| AC-8 to AC-12 | doc check | Each application row has a submitted date, read-only scopes, a portal domain without "accrued", no IRS filing |
| AC-13, AC-14 | review | Builder's own claim-by-claim check recorded against ADRs and the register |
| AC-15, AC-16, AC-17 | doc check | Optional vendors absent; fallbacks named; reply dates within 3 business days |
| AC-18 to AC-21 | doc check | Dates, exclusion rule, quotes and policy drafts present |
| AC-22 to AC-24 | doc check | Engagement letter scope list; answers or re-dated rows |
| AC-25 to AC-29 | doc check | thresholds.md merged first; guide; named lists; notes tagged with firm codes only |
| AC-30 to AC-32 | review | LOI text against its prohibited-promise list; instrument identical across calls |
| AC-33 | doc check | M1 record in decision-log.md |

## 19. Rollout
- **Feature flag:** none.
- **Migration and backfill plan:** none.
- **Rollback plan:** a wrong tracker entry is corrected by a new dated entry.

## 20. Open questions
None open. The plan's proposed option was taken for each:
- [x] Who funds the second founder's support rows (plan Q-1)? Moot under the solo amendment: there is no second founder; the builder's own checks replace them.
- [x] Owner of the compliance tool, auditor and pen tester (Q-2)? The builder runs selection and commercial terms and is the tool admin and controls owner.
- [x] Xero, NetSuite SDN and Google CASA timing (Q-3)? File no-fee enquiries on Nov 2, commit no spend before DEC-70 at M3, CASA only if a partner runs Google Workspace.
- [x] DEC-17 decide-by (Q-4)? Chapter 01's date (Oct 30) stands for the record; applications are filed in week 1 regardless.
- [x] Resource Pack timing (Q-5)? v1 by Dec 11, 2026 (a later sprint's row).
- [x] DEC-59 decided Nov 13 but domains bought by Oct 30 (Q-6)? Buy per the recommended answer, a neutral portal domain.
- [x] Prior-year replay before the gate (Q-7)? Before M7 only anonymised request lists.
- [x] Pricing at M4 on six weeks of discovery (Q-8)? Decide the founding price and packaging at M4; revisit list prices with season-1 data (later rows).
- [x] How Accrued invoices its own customers (Q-9)? An off-product invoicing tool; the product takes no payments.
- [x] Hires starting Oct 4 inside the busy-season window (Q-10)? Allowed; onboarding touches no live path.

## 21. Task map
The plan keys in scope are the sprint 0 and sprint 1 rows of `F-09.tasks.csv`. Task files exist only for the rows marked with a TASK id; the others are submitted by hand from the SU-26 checklist or kicked off later.

| Plan key | Row | AC ids | Task |
|---|---|---|---|
| F-09-T01 | Programme set-up: tracker, vault, RK issues | AC-1, AC-2, AC-3 | TASK-136 |
| F-09-T02 | Company and legal foundation (RK-59) | AC-4 | TASK-137 |
| F-09-T03 | DEC-03 year-one spend plan | AC-5, AC-6 | none: SU-26 checklist |
| F-09-T04 | Counsel engagement with dated scope | AC-22 | none: SU-26 checklist |
| F-09-T05 | Intuit developer account and app assessment | AC-8, AC-10, AC-12, AC-17 | none: SU-26 checklist |
| F-09-T06 | Wolters Kluwer CCH partner application | AC-8, AC-10 | none: SU-26 checklist |
| F-09-T07 | Microsoft partner enrolment and publisher verification | AC-8 | none: SU-26 checklist |
| F-09-T08 | DocuSign developer account and Go-Live plan | AC-8 | none: SU-26 checklist |
| F-09-T09 | Domains | AC-8, AC-11 | none: SU-26 checklist |
| F-09-T10 | Commercial terms for WorkOS, Temporal Cloud, Sentry, Better Stack | AC-8 | none: SU-26 checklist |
| F-09-T11 | SES production access and Bedrock quota requests | AC-8, AC-13 | none: SU-26 checklist |
| F-09-T12 | Builder's own check of questionnaire answers | AC-13 | TASK-138 |
| F-09-T13 | SOC 2 compliance tool contracted | AC-18, AC-19 | none: SU-26 checklist |
| F-09-T14 | Discovery thresholds, interview guide, anonymisation | AC-25, AC-27 | TASK-139 |
| F-09-T15 | Partner profile and named target lists | AC-26 | TASK-140 |
| F-09-T16 | Non-binding LOI template | AC-30 | none: SU-26 checklist |
| F-09-T17 | Builder's own M1 check | AC-33, AC-8, AC-18, AC-22, AC-26 | TASK-141 |
| F-09-T18 | Xero and NetSuite no-fee enquiries | AC-9, AC-15 | none: SU-26 checklist |
| F-09-T19 | S1 programme cadence | AC-7 | none: later kickoff |
| F-09-T20 | Discovery interviews wave 1 | AC-28 | none: later kickoff |
| F-09-T21 | Wave-1 notes anonymised | AC-29, AC-27 | none: later kickoff |
| F-09-T22 | Counsel early answers due Nov 13 | AC-23, AC-24 | none: later kickoff |
| F-09-T23 | Builder's check of technical facts in counsel briefs | AC-14 | none: later kickoff |
| F-09-T24 | SOC 2 auditor RFP | AC-20, AC-19 | none: later kickoff |
| F-09-T25 | SOC 2 policy set | AC-21 | none: later kickoff |
| F-09-T26 | Pricing hypothesis instrument | AC-32 | none: later kickoff |
| F-09-T27 | LOI outreach wave 1 | AC-31, AC-30 | none: later kickoff |
| F-09-T28 | Application follow-ups | AC-17 | none: SU-26 checklist |

## 22. Future / explicitly deferred
- Sprint 2 onward rows: M3 read and LOIs, Google CASA, auditor selection, pen-test RFP, counsel Nov 27 answers, insurance, Pilot 0, Resource Pack, pricing decision, season 2, hiring.
- Writing the vendor applications' text (the SU-26 checklist).
