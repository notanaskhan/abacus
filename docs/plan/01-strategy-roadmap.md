> **Solo edition (2026-10-20).** One builder, repo public, no approvals, reviews, rulesets, release-train windows or worktree cadence. `AMENDMENT-solo.md` and chapter 08 win over any other chapter on process. Ten governance-only F-01 tasks are removed from `backlog.csv`; its `lead` column is gone and a `status` column is added.

# 1 · Strategy, roadmap and epic catalogue

> Chapter of the Accrued engineering and build plan. Written Saturday 2026-10-17; Sprint 0 starts Monday 2026-10-19.
>
> **Readers.** Both founders and their Claude Code sessions. This chapter is the plan of record for *order, dates, owners and scope*. Chapters 02–06 hold the architecture and the detail. Where a date in chapters 02–06 differs from this chapter, this chapter wins; their designs and decisions stand, and their work moves to the epic windows below.
>
> **Founders.** **N** = notanaskhan, the technical co-founder who built the repo and owns the red-zone backend. **AY** = ayushkbhatia, the product and design founder, who codes through Claude Code.
>
> **Units.**
> - A **task** is a repo-calibrated task of about 1,130 hand-written lines (backend 682, frontend 205, tests 245).
> - An **FW** (founder-week) is one founder's focused coding output in one 5-day week at plan velocity: **14 tasks**, with ADR-078 independent tests and cross-founder review restored.
> - **Sn** is a 2-week sprint. S0 = Mon 2026-10-19 – Fri 2026-10-30. Sn starts on Oct 19 + 14n days.
>
> **Reading the IDs.** Several registers in this plan reuse the same letters, so the forms below are fixed:
> - **Epics** use a letter, a dash and two digits, always in bold or in an Epic column: **F-01**, **P-04**, **A-07**, **T-02**, **C-01**, **X-01**, **Q-02**.
> - **Proposed ADRs** are written with the word ADR: "ADR P-04", "ADR P-29". Chapter 09 holds the one ADR backlog (P-01…P-63) and settled the overlapping P-34+ numbers minted in chapters 03 and 06 (its §9.2, row X-1). This chapter cites chapter-minted proposals by name.
> - **Decisions** use chapter 09's canonical register, DEC-01…DEC-99 (§1.9 lists the ones this roadmap depends on and the two it adds). Founder questions are "question Q-04"; compliance requirements and conflicts are "requirement R-04" and "conflict C-05"; scope exclusions are "exclusion X-01".
> - Templates are T1–T22 (no dash); contracts are C1–C21 (no dash); write classes are W1–W9 (no dash); engagement gates are G1–G9 (no dash).
> - Phases are **PH0–PH7**; dated milestones and gates are **M0–M24**; tracks are **Track 0–4**; pilot windows are **PW0–PW5** and **PWT**.

---

## 1.0 The plan on one page

### Thesis

Build first the slice that already half-exists, is legal under the repo's accepted ADRs, and has a real season waiting for it: the **audit-evidence spine** (clients and engagements with gates G1–G3, binders and requests, the white-labelled portal, evidence and screening, trial-balance import and sampling) rebuilt on the Accrued design. It runs on the repo's strongest primitives (forced RLS, authorise/visible, unit of work with audit events, write-once evidence, screening and matching) and needs none of the blocking decisions: no ledger writes (ADR-040), no model text to clients (ADR-111), no e-signature with KBA, no tax return information.

Put it in front of real firms in the first window that is both **open** (not the Jan 15 – Apr 15 peak) and **gated** (SOC 2 Type I and an external pen test done, no exceptions): internal shadow from **Tue Jun 1, 2027**, client-facing from **Tue Jul 13, 2027**, for EBP 401(k) plan audits and June-30 year-end audits.

Use the calm TY2026 extension season for a **capped, conditional tax pilot** on the coordination layer: portal and organizer on the binder spine, a return record, the CCH Axcess file bridge with a human "Mark transmitted", Form 8879 through DocuSign with provider-hosted identity verification, and K-1 release. It goes live **Aug 17 / Aug 31, 2027** if the **May 28** go/no-go passes. Notices follow as the first year-round tax-adjacent module (**Dec 10, 2027**).

Run December 2027 year-end audits and TY2027 returns on Accrued through the 2028 season under a written freeze contract. Then widen one line at a time: the full tax workspace for the 2028 extension season, CAS in Q4 2028, SAS 149 group audit for December 2028 year-ends, and in 2029 the configurable engine, Workbench agents, attest, internal audit and insights.

### Pacing, stated honestly

| Assumption | Value |
|---|---|
| Velocity of record | 14 tasks per founder-week, 5-day weeks, independent tests and cross-review restored. That is about 0.4× the measured peak of 5.1 tasks a day, which came from 17-hour, 7-day weeks with tests and reviews skipped. |
| Two founders | 1.7× one founder for coordination; AY codes 60% of the time to Jan 22, 2027 and 75% after (vendors, counsel, SOC 2 paperwork, design partners, sales) |
| Reserves | 22.5% of every sprint for hardening and test back-fill; 10–30% pilot support once firms are live |
| Scope | 303 catalogue rows ≈ 1,180 screen tasks + ≈ 940 tasks of engines, integrations, infra, compliance, seed and harness ≈ **2,120 tasks ≈ 150 FW** |
| Central outcome | Feature-complete (all 28 journeys walkable in production) **Fri Aug 17, 2029**; GA **Fri Aug 31, 2029** |
| Range | Jun 2029 (15 tasks/FW) to mid-2030 (12 tasks/FW, no learning gains); **Dec 2028** if the conversion gate on Aug 20, 2027 adds two engineers |

### What we build first, and why

1. **The delivery system and the decisions (S0–S1).** Scan the git history for secrets and rotate, then go private; enforce CI and the other founder's review; fix the protected-path hook so either founder can approve but never the author; isolate worktrees; freeze the contract register; hold Decision Day on **Fri Oct 23** with an owner per decision.
2. **The model, migrated once, before any data (S0–S4).** Work items for all five kinds (assurance, tax return, close, notice, advisory project) with a per-type gate policy; the request status enum; client access grants; the role catalogue; the review-grammar and citation-v2 schemas.
3. **Production and compliance on one dated chain.** Staging **Nov 13**; production with a canary **Dec 11** (controls operate 11 weeks before the Type I as-of date); pen test **Feb 15 – Mar 5**; SOC 2 Type I as of **Mar 1**; real-data gate **Apr 16**.
4. **The audit-evidence MVP:** 45 product screens (33 P0, 12 P1) plus 21 design-system boards. It reuses the repo's strongest code and touches no contested ADR.
5. **Design partners as the critical path.** Named target lists by **Nov 20**; Pilot 0 synthetic sessions from **Jan 11**; first internal shadow **Jun 1**; client-facing **Jul 13**. Agents (screener, upload reviewer, matcher) run in shadow stage from Jun 1 and go live on Jul 13 once their Bedrock evals clear, so the first pilot shows cited AI output while no model text reaches a client.
6. **The tax extension pilot** (go/no-go **May 28**) and **notices** (**Dec 10**), so 2027 is not an audit-only year.

### What we defer, and why

| Deferred | Lands | Why |
|---|---|---|
| Group audit (SAS 149) | Behind a flag Sep 29, 2028 for Dec-2028 year-ends (**A-09**) | Dec-2026 is infeasible. Dec-2027 readiness would need the same S16–S26 capacity that carries the client-facing pilot and the tax pilot; it is the alternative to the tax pilot at M8 |
| CAS close and ledger posting | Read-only live on Oct 2028 closes; posting by Dec 2028 (**C-01**, **C-02**) | Needs the W1 write ADR, Intuit production keys and the attest-client lock; one service line at a time |
| Full tax workspace (1040 review, entity returns, trusts) | 2028 extension season (**T-04**, **T-05**, **T-07**) | Built dark during the 2028 freeze, shadowed in March–April, live from May 2, 2028 |
| Configurable engine, Workbench agents, attest, internal audit, insights, add-ins, developer platform | 2028–2029 (**K-03**…**K-05**, **W-02**…**W-04**, **X-01**…**X-03**, **I-03**, **G-03**) | Leaf modules on proven spines; D3 means designed workpapers never need the engine |
| Model-drafted text to clients | ADR P-25 accepted on Decision Day but **off** per firm until each drafter's evals pass (**N-03**) | Professional-liability exposure; ADR-111 |
| Native KBA ceremony, CRDT co-editing, WebSockets, policy principal | Not planned (native KBA, CRDT, WebSockets) or dormant (policy principal) | Provider-hosted KBA carries less Pub 1345 burden; the router refuses WebSockets; ADR-005 |

### Key dates

| Date | Milestone |
|---|---|
| Fri Oct 23, 2026 | **M0** Decision Day |
| Fri Nov 13, 2026 | **M2** Staging live (R0) |
| Fri Nov 20, 2026 | **M3** ≥2 design-partner LOIs, first live ledger chosen, group-audit decision |
| Fri Dec 11, 2026 | **M4** Production with canary (R1); SOC 2 controls operating; flag renewals in the Dec 14–18 bundle |
| Fri Jan 22, 2027 | **M5** Platform spine walkable on staging; Pilot 0 running since Jan 11 |
| Fri Apr 16, 2027 | **M7** Real-data gate (R2): Type I report, pen-test highs closed, Bedrock clearance |
| Fri May 28, 2027 | **M8** MVP code-complete; tax-pilot go/no-go |
| Tue Jun 1, 2027 | **M9** First firm in internal shadow |
| Tue Jul 13, 2027 | **M10** Client-facing audit pilot (R3) |
| Tue Aug 17 / Aug 31, 2027 | **M11 / M13** Tax extension pilot live (coordination, then 8879 and K-1 release) |
| Fri Aug 20, 2027 | **M12** Paid-conversion and hiring gate |
| Fri Dec 10, 2027 | **M15** Season-ready for 2028 (R4); notices live |
| Tue Mar 21, 2028 | **M16** Release and archive on; first report released and archived on Accrued by Apr 14 |
| Tue May 2, 2028 | **M17** 2028 extension-season release (1040 review workspace) |
| Tue Oct 31, 2028 | **M20** CAS live on October closes |
| Fri Aug 17, 2029 | **M23** All 28 journeys walkable in production |
| Fri Aug 31, 2029 | **M24** GA |

### What changed from the base proposal (A, wedge-first)

The order is A's. The dates are not: A's own sizing left out about 150 tasks of foundations, and an honest per-founder ledger (§1.8) puts its Jan 22 MVP at more than twice the capacity of S0–S6. So:
- First real data moves from **Mar 1** to **Jun 1, 2027** (internal shadow), and client-facing use to **Jul 13**. No firm goes live with client-facing surfaces between Jan 15 and Apr 15.
- Production now exists 11 weeks before the Type I as-of date, and every new real-data surface gets a delta pen test.
- Grafted from C: the contract register, Decision Day, Pilot 0, the extension-season tax pilot, notices as the first year-round tax module, the hot-file controls and the critical-path table.
- Grafted from B: the freeze contract and P-29 in-season rules, the 25–30% in-season support reserve, the paid-conversion and hiring gate, effective-dated rules tables as database content, and the SQMS 1 Technology Resource Pack.
- Every must-fix from the three reviews is closed; §1.8 and §1.9 trace them.
- Full catalogue: Sep 2028 in A, **Aug 2029** here, or **Dec 2028** with two hires.

---

## 1.1 Alternatives considered

Three proposals were written and judged through three lenses: market value and timing, technical integrity, and executability for two Claude Code founders. All three assigned all 303 catalogue rows, so coverage did not separate them.

| | **A · Wedge-first** (base) | **B · Season-first** | **C · Parallel tracks** |
|---|---|---|---|
| Thesis | Finish the audit-evidence spine; pilot it in the audit seasons; then audit depth, tax, CAS, engine | Ship a tax "Season Kit" live on Jan 25, 2027; extension-season workspace; CAS; audit depth in 2028 | Shared spine split by layer, then two vertical tracks owned end to end (N assurance, AY tax and client operations) |
| First real data | Mar 1, 2027 shadow | Jan 25, 2027 live, with a "recorded exception" to the Type I rule | May 3, 2027 |
| Velocity basis | 15 tasks per 6-day FW | 12 tasks/FW, 30% in-season support | Measured 5.1 tasks/day (Model M) |
| Full catalogue | Sep 2028 (range Apr 2028 – Jun 2029) | Aug 2029 (Q4 2028 with hires) | Dec 10, 2027 |
| Scores (market / technical / executability) | **7 / 7 / 7.5** | 4.5 / 4.5 / 4 | 5 / 6 / 6 |
| Decisive strength | Believable real-data gate; MVP rides code that is 40–45% built; ADR-compliant scope; model migrations before data | Sharpest calendar reasoning; freeze contract; honest capacity; commercial gate | Cleanest dependency layering; contract register; Decision Day; best adoption windows (extension season, EBP, notices) |
| Disqualifying weakness | No revenue for 18 months; audit-only 2027; review grammar built inside the freeze; foundations missing from its capacity sum | Bets the company on real TRI 14 weeks out; breaks the SOC 2 rule; Season Kit over capacity; N overloaded | Velocity about 2× the others; production after its own Type I date; TRI-bearing tax and formula engines on the design founder |

**Why the final blends them.** A wins on risk ordering and foundation integrity, so it is the spine of this plan. Its market gaps (no revenue, no tax in 2027, an AI-invisible first pilot) are closed with grafts that do not change its risk order: C's extension-season tax pilot and notices, B's commercial gate, and per-agent clearance before the first shadow. Its executability gaps are closed with C's contract protocol and hot-file controls and B's freeze mechanics. All three plans under-counted foundations and the design founder's non-code load, so every date here comes from one per-founder capacity ledger (§1.8) rather than from any proposal's calendar.

**Rejected outright:** any exception to the SOC 2 Type I and pen-test rule (B); planning on the measured 5.1 tasks a day (C); single-owner CODEOWNERS directories, which deadlock code-owner review because GitHub does not let an author approve their own PR (C); a native KBA ceremony (A's EP-42); a mid-season client-facing go-live (A's Mar 1 and B's Jan 25).

---

## 1.2 Phases, gates and exit criteria

**Definitions.**
- *Walkable* means the journey's Playwright scenario (journeys digest §0.3) passes with real auth, fakes only for third parties, every gate enforced on the server, the five invariants asserted (INV-1 the agent never decides, INV-2 citations verified, INV-3 walls hold, INV-4 portal scopes isolated, INV-5 attribution correct) and axe AA clean.
- *Walkable in production* means that scenario passes on the released build against the production canary tenant.
- *Live* adds at least one real design-partner instance of the journey.

### 1.2.1 The eight phases

| Phase | Sprints and dates | Goal | Exit criteria |
|---|---|---|---|
| **PH0 Unblock, govern and decide** | S0 · Mon Oct 19 – Fri Oct 30, 2026 | Make two-founder work safe, take the blocking decisions, start every long-lead clock | **M1 (Oct 30):** history scanned for secrets and anything exposed rotated; repo private; ruleset with the other founder's code-owner review and stages 1+2 required; `_protected.py` fix merged; `main` green and the nightly e2e repaired; the Decision Day agenda in §1.9 (chapter 09's ★ items and the roadmap's DEC rows) recorded on Oct 23; ADR drafts for work items, request enum, scopes, roles, e-signature, P-29 and the write-capability framework; DS-S1 tokens merged; protected bundle #1 (fonts, table, virtualisation, WorkOS) merged; every vendor, assurance and counsel application filed with a dated ticket; AWS organisation and Terraform state exist; a named design-partner target list per pilot window and ≥6 conversations booked |
| **PH1 Foundations and platform spine on staging** | S1–S6 · Nov 2, 2026 – Jan 22, 2027 | Migrate the model, stand up staging and production, ship the design-system core and the first spine slice | **M5 (Jan 22):** R0 staging (Nov 13) and R1 production with canary (Dec 11) live with SLO alarms, status page, on-call and a passed restore drill; work-item, request-enum, client-grant, role, review-grammar and citation-v2 schemas migrated; contracts C1–C6, C13, C16 frozen; DS tiers 0–1 at parity tier A (tokens, primitives, chrome strips) with template frames at tier B, and axe AA; on staging with real WorkOS, SES and scanner, the **J02-audit-core skeleton** (client → engagement → G1–G3 recorded → binder → request) and the **J12-core skeleton** (portal sign-in → home → documents → upload) are walkable; 9 expiring flags renewed and P-29 accepted in the Dec 14–18 bundle; Pilot 0 running since Jan 11; capacity re-baselined from S1–S5 measurements |
| **PH2 Audit-evidence MVP and the real-data gate** | S7–S15 · Jan 25 – May 28, 2027 | Finish MVP-1, pass the real-data gate with no exceptions, prepare onboarding | **M8 (May 28):** pen test #1 (Feb 15 – Mar 5) with criticals and highs retested closed by Apr 9; SOC 2 Type I report (as of Mar 1); **real-data gate passed Apr 16 (M7)**; the 55 deferred AC-test suites back-filled, red zone first; screener, upload reviewer and matcher cleared on Bedrock; MVP-1 code-complete with **J01-core, J02-audit-core, J04-PBC slice and J12-core walkable in production** on the canary; onboarding kit ready (bulk client and contact import, PBC and email templates as database content); tax-pilot go/no-go taken |
| **PH3 Pilot season 1: audit live, extension-season tax pilot, audit execution** | S16–S30 · May 31 – Dec 24, 2027 | Real firms on real data; review-grammar UI, planning, EBP, findings and adjustments; completion schema; notices; 2028 readiness | **M15 (Dec 10):** ≥2 firms live client-facing on EBP and June-YE engagements, with Accrued as the PBC and evidence system of record; the tax pilot (if GO) carried 5–15 extended returns through Sep 15, Sep 30 and Oct 15 with zero invariant violations; **J09 (notices) P0 live**; J03 fieldwork P0 (EBP-01…06; the EBP-07 5500 tie-out follows by Jan 7, 2028) and J04 planning walkable in production; SOC 2 Type II report (≈Sep); pen test #2 done (Nov); R4 checklist met (TY2027 rules and organizers in the database; December load test; flags renewed; completion, release, archive and runtime-v2 schemas migrated by Dec 24, before the Jan 1 window); conversion gate decided Aug 20 |
| **PH4 Busy season 2028 and the full tax workspace** | S31–S38 · Dec 27, 2027 – Apr 14, 2028 | Operate the 2028 season under the freeze contract; flip completion, release and archive per firm; build the 1040 workspace, runtime v2, dock and trace dark | Dec-YE 2027 audits run from planning to release on Accrued at ≥1 firm; **first report released (G8) and archived (G9) on Accrued (M16)**; **J03 P0 and J12 P0 walkable in production**; TY2027 returns live on the coordination kit for the tax-pilot firms; 1040 review workspace in shadow from Mar 20 |
| **PH5 Extension season 2028, CAS, group audit and audit depth** | S39–S51 · Apr 17 – Oct 13, 2028 | Tax workspace live for the 2028 extension season; Workbench sessions and Today; fieldwork depth; group audit for Dec-2028 year-ends; CAS read-only; integrations catalogue; tenant console | **M20 (Oct 31):** J06 and J19 P0 (May 2), J08 P0 (Aug 1) and J07 (Aug 22) live; **J20 P0 behind `ff.group_audit` (Sep 29)**; J04 core and J05 core live; J10 read-only path live on October closes; J14 P0 walkable; J11 read-only sessions walkable on staging |
| **PH6 Season-3 readiness, engine and depth** | S52–S65 · Oct 16, 2028 – Apr 27, 2029 | CAS posting (W1), TY2028 season tools, entity-return depth, QM for the Dec 15, 2028 SQMS evaluation, mailbox and messages, DS tier 5, templates v2 and Sheets, Board and triggers, statements studio, portal depth; operate the 2029 season | **M22 (Apr 27, 2029):** J05, J06, J10, J18 and J28 full live; posting live for non-attest CAS clients; J13, J21 P0 and the engine-based P0 paths of J04, J22–J26 walkable on staging |
| **PH7 Expansion lines and GA** | S66–S74 · Apr 30 – Aug 31, 2029 | Attest, internal audit, agentic audit, Workbench agent library, insights, learning layer, advisory, add-ins, developer platform, practice economics; GA hardening | **M23 (Aug 17):** all 28 journeys walkable in production and ≥12 live at partner firms; **M24 (Aug 31):** 30 days within SLO, runbooks rehearsed, GA |

### 1.2.2 Gates (dated, with fallbacks)

| M | Date | Gate | Criteria (all required) | If missed |
|---|---|---|---|---|
| **M0** | Fri Oct 23, 2026 | Decision Day | The §1.9 agenda recorded with owners in chapter 09's register, after drafts exist | Undecided items block their first epic; nothing else moves |
| **M3** | Fri Nov 20, 2026 | Partners, ledger, group audit, calibration #1 | ≥2 signed LOIs and a named target list per window (audit/EBP, extension-season tax, CAS); first live ledger chosen from discovery (ADR-045); group-audit record: Jun-2027 and Dec-2027 year-ends **NO-GO** at plan velocity, Dec-2028 the target, upload-TB and manual-elimination fallback documented; S1–S2 throughput measured | <2 LOIs: Pilot 0 continues on synthetic data and prior-year replay; PW1 slides to Jun 15. Throughput <85% of plan: PH1 cut tier 1 |
| **M4** | Fri Dec 11, 2026 | Production stood up (R1) | Production account with canary, SLO alarms, status page, paging, first restore drill; SOC 2 controls operating; auditor engaged (not a design-partner firm); pen test booked | Each week of slip moves the Type I as-of date one week |
| **M5** | Fri Jan 22, 2027 | Spine on staging; re-baseline #2 | PH1 exit above; measured planned-epic throughput for S1–S5 | ≥90%: hold. 80–90%: MVP cut tiers 1–2. <80%: tier 3 (shadow Jun 15, R3 Jul 27) |
| **M7** | Fri Apr 16, 2027 | **Real-data gate (R2)** | SOC 2 Type I report in hand; pen-test criticals and highs closed and retested; provider-terms Bedrock entry current with counsel as second approver; per-agent Bedrock evals passed for every agent that will touch real data, **including shadow-stage runs**; firm opt-in (TASK-076) recorded per firm before its first agent run; MSA and DPA with the sub-processor list generated from `provider-terms.yaml`; cyber and tech E&O insurance bound; WISP approved; MFA enforced for staff and for portal owners and signers; restore drill within the quarter; compliance kernel complete (hash chain, access events, actor kinds, retention floors, legal holds, dual-approval export, incident register with the FTC clock); vendor-diligence pack ready (SOC 2 report, pen-test letter, DPA/MSA, sub-processor list, WISP, insurance certificate, BAA posture, SQMS 1 Technology Resource Pack). **No exception path.** | Type I report late: gate moves to Fri May 14; shadow Jun 15; R3 Jul 27 |
| **M8** | Fri May 28, 2027 | MVP code-complete; **tax-pilot go/no-go**; calibration #3 | MVP-1 walkable in production on the canary. Tax **GO** only if (a) S7–S14 throughput ≥95% of plan; (b) ≥1 tax partner signed for 5–15 extended returns and its CCH Axcess admin validated the file format in Pilot 0; (c) counsel-approved §7216 consent text naming AWS Bedrock, and the DocuSign ID Verification contract signed; (d) M10 on track | Tax **NO-GO**: S16–S21 capacity goes to EBP workpapers (usable for late-2027 EBP audits) and audit completion by Oct 15; or, if an audit partner commits a Dec-2027 group audit and throughput ≥110%, to **A-09** for Dec-2027 year-ends. Tax then targets the 2028 extension season |
| **M9** | Tue Jun 1, 2027 | First internal shadow | M7 passed; firm MSA, DPA and founding-partner agreement signed; tenant provisioned through the workflow; SSO and MFA enforced; walls configured; agents in scope cleared and opted in, at stage *shadow*; no client-facing email; P-29 on for that firm | Shadow moves in two-week steps; R3 keeps ≥4 weeks of shadow |
| **M10** | Tue Jul 13, 2027 | **Client-facing audit pilot (R3)** | Shadow exit (≥2 engagements, no open SEV1/2, champion confirms); portal on the white-label host with the firm's SES sender domain (DKIM); email templates published from the database; portal MFA mandatory for owners and signers; letters at least in record mode; autonomy level 1 for cleared agents; **pen-test delta #1** (portal client flows, live ledger OAuth connector, inbox, third-party rooms) closed | Jul 27, then Aug 10; EBP pilots shift to Oct-15 filers |
| **M11** | Tue Aug 17, 2027 | Tax pilot live: coordination | TRI class and gateway condition 6 live (fail closed); MFA for TRI scopes; sealed TIN with logged reveal; CCH file bridge validated on the partner's returns; **pen-test delta #2** (TRI, consent gate, signing, CCH bridge, K-1 room) closed; "never ERO or transmitter" tests green | Pilot narrows to Sep 30 (1041) and Oct 15 (1040) filers |
| **M12** | Fri Aug 20, 2027 | **Paid-conversion and hiring gate** | ≥2 of 3 design partners sign paid season-2 agreements (Dec-2027 YE audits and/or TY2027 returns) → open two engineering hires, backend first | Stay at two founders; apply the PH6–PH7 spill list (§1.8.6) |
| **M13** | Tue Aug 31, 2027 | Tax pilot live: 8879, delivery, K-1 release; season-ready for the Sep 1 window | 8879 envelopes with provider-hosted KBA, handwritten fallback after 3 failures, amount-hash re-lock at Pub 1345 tolerances; delivery and e-file record; K-1 release only after the signer's final approval | 8879 falls back to record mode (import the provider's evidence) |
| **M14** | Fri Oct 15, 2027 | Extension season closes; re-baseline #4 | Retros with every partner; Type II report received; PH4–PH5 re-plan | — |
| **M15** | Fri Dec 10, 2027 | **Season-ready for 2028 (R4)** | Notices live; TY2027 rules and organizers loaded; pen test #2 closed; December load test passed; the remaining Jan 1 rows of the freeze-contract table (§1.2.4), including the completion, release, archive and runtime-v2 schemas, land by Dec 24 | Late items stay dark until after Apr 20, 2028 |
| **M16** | Tue Mar 21, 2028 | Release and archive flipped per firm | A-07 code-complete dark, shadowed on one engagement, both founders approve the Tuesday flip | Dec-YE reports are issued from the firm's tool through the binder export |
| **M17** | Tue May 2, 2028 | 2028 extension-season release | 1040 review workspace (J06 P0) after 6 weeks of shadow; notices depth; runtime v2 live for cleared agents | — |
| **M18** | Tue Aug 1, 2028 | Entity returns live (J08 P0); 1041 Tue Aug 22 (J07) | CPA review of the golden figures signed off; CCH reconciliation on every pilot return | 1065 depth stays in shadow; coordination kit carries the season |
| **M19** | Fri Sep 29, 2028 | Group audit behind flag (J20 P0); fieldwork depth live | Consolidation golden tests; component-auditor room isolation pen-tested | Upload-TB and manual eliminations only |
| **M20** | Tue Oct 31, 2028 | CAS live on October closes (J10 read-only) | QBO production keys; reconciliation golden tests; shadow on the September close | Shadow continues one more close |
| **M21** | Fri Dec 8, 2028 | Season-ready for 2029 | Posting (W1) for non-attest clients with delta pen test; TY2028 season tools; QM for the Dec 15 SQMS evaluation | Posting waits for Tue Apr 24, 2029 |
| **M22** | Fri Apr 27, 2029 | Engine core | Templates v2, Sheets, Board, triggers, review package, statements studio walkable on staging | Spill list applies |
| **M23 / M24** | Fri Aug 17 / Fri Aug 31, 2029 | Feature-complete / GA | All 28 journeys walkable in production; SLOs held 30 days | Spill list applies; GA keeps its date with P2 depth after it |

### 1.2.3 Production readiness and assurance schedule

The readiness ladder matches chapter 06 §8.1, with this chapter's dates.

| Level | Meaning | Date |
|---|---|---|
| R0 | Production-shaped staging, synthetic data only, CI enforced | Fri Nov 13, 2026 |
| R1 | Production account with only the canary tenant; DR, alarms, status page, on-call, first restore drill | Fri Dec 11, 2026 |
| R2 | Real-data ready (M7); internal shadow allowed (autonomy 0, nothing client-facing) | review Fri Apr 16, 2027; first firm Tue Jun 1, 2027 |
| R3 | Client-facing live pilot (M10) | Tue Jul 13, 2027 |
| R4 | Season-ready before each window | Aug 31, 2027 · Dec 10, 2027 · Aug 25, 2028 · Dec 8, 2028 |

| Assurance item | When | Scope or note |
|---|---|---|
| SOC 2 tool and auditor | Tool chosen by Oct 30; auditor engaged by Dec 11 (not a design-partner firm, and booked early because SOC auditors are CPA firms in their own Jan–Apr season) | Security, Availability, Confidentiality |
| SOC 2 Type I | Controls operating from Dec 11; as-of date **Mar 1, 2027**; report ≈ Apr 2 [verify auditor timing] | Fallback date in M7 |
| SOC 2 Type II | Observation **May 1 – Jul 31, 2027**; report ≈ Sep 2027; then 12-month windows | Ready for firms' 2028 vendor diligence |
| Pen test #1 | **Feb 15 – Mar 5, 2027**, on the production-equivalent build | Firm app, portal (with a custom-domain host), API, auth flows, upload pipeline, tenant isolation, role union, AWS config review, source-assisted review of authz, crypto and the AI gateway |
| Delta #1 | Jun 21 – Jul 2, 2027 | Client-facing portal flows, live ledger OAuth connector, inbox, third-party rooms |
| Delta #2 | Aug 2 – Aug 11, 2027 | TRI class and consent gate, DocuSign hand-off, CCH file bridge, K-1 recipient room |
| Pen test #2 (annual) | Nov 2027 | Release and archive, runtime v2 and SSE, notices |
| Later deltas | Before W1 posting (Nov 2028), W6 send-as (Feb 2029), API and MCP (Jul 2029) | Every new real-data surface is tested before it touches real data |

### 1.2.4 The freeze contract

ADR P-29 is accepted in the Dec 14–18, 2026 bundle. The busy-season window applies **per firm, from the date that firm first holds real data**: Jan 1 – Apr 20 for every live firm, and Sep 1 – Oct 20 for firms live on tax or EBP work. There are mini-freezes on Sep 8–15, Sep 23–30 and Oct 8–15, and no production promotion in a deadline week (Mar 15, Apr 15, Sep 15, Sep 30, Oct 15).

**Inside a window:**
1. Code on live paths changes only to fix defects.
2. New modules merge dark behind default-off flags, and only if they touch no live-path code. Migrations are expand-only and run by the pipeline after 8 pm CT.
3. Flags flip per firm only in the Tuesday 7 pm CT window. Each flip needs the journey e2e passing on staging, a shadow run, a written rollback and both founders' approval.
4. No model or prompt upgrade ships without the full eval suite and a shadow run.
5. Production promotes weekly on the release train. Hotfixes follow the documented hotfix lane.
6. **There is no year-one exception.**

**What must be in production before each window:**

| Before | Schema | Contracts and integrations | Database content | Ops and assurance |
|---|---|---|---|---|
| **Sep 1, 2027** | `tax_return` subtype, consents and signers, TRI class, envelopes and evidence, filings and acks, K-1 packages, review-grammar tables | CCH file bridge (W2 file mode), DocuSign embedded with ID Verification (W7), first live ledger read | TY2026 due dates and holidays, 8879 form set and Pub 1345 tolerances, organizer, letter and email templates | Deltas #1–#2 closed; on-call per firm; restore drill this quarter; flags renewed with expiries after Oct 20 |
| **Jan 1, 2028** | Completion, release and archive (A-07), runtime v2 (P-10), notices, adjustments, workpapers, sampling | Renderer (C11), deliverables (C10), approvals (C18) | TY2027 rules tables, organizers, PBC templates, firm standards | ADR-075 December load test; pen test #2; flags renewed with expiries after Apr 20; extended on-call; runbooks RB-16/18/19 rehearsed |
| **Sep 1, 2028** | Entity returns, trusts, closes, group consolidation (flagged) | QBO live read | TY2027 extension rules, fiduciary tables | Delta pen test for SSE sessions and the catalogue |
| **Jan 1, 2029** | Posting batches and write log (C-02), TY2028 season | W1 posting (non-attest only) | TY2028 rules, 1099 thresholds | Delta pen test (W1); load test |

**Flags.** The 9 flags expiring Jan 5–13, 2027 are renewed in the Dec 14–18, 2026 bundle. Module enablement moves to database entitlements (ADR P-28), so flags carry rollout only. Each later renewal is calendared to expire outside a window (≤90 days, ADR-089). Flag-off states are designed, never blank.

---

## 1.3 Tracks, lanes and the contract-first handshake

### 1.3.1 Tracks and leads

| Track | Epics | Lead | The other founder's role |
|---|---|---|---|
| **Track 0 · Foundations and delivery system** | F-01…F-09, Q-01…Q-04 | Split: **N** for governance, CI, infra and the compliance kernel; **AY** for the design system, seed content, vendors, counsel, design partners and the commercial programme | Each reviews the other and writes the other's AC tests (ADR-078) |
| **Track 1 · Platform spine and governance** | P-01…P-08, P-11, G-01…G-04, I-01 | **N** (identity, requests and evidence red paths, portal identity, review grammar, renderer) | **AY** owns the design-system frontend and the home and portal read models. **N** builds the frontend of admin and settings screens on the T12 and T1 kits, with AY's design-fidelity review |
| **Track 2 · Assurance** | A-01…A-11, X-01…X-03, Q-05 | **N** for red-zone evidence, ledger, adjustments, release, archive and consolidation | **AY** owns the compute libraries (sampler, materiality and RMM, SUM, EBP, JE scoring, flux and UDL) and the frontend. From PH3, AY leads EBP, planning, fieldwork depth, statements studio, attest, internal audit and QM end to end |
| **Track 3 · Tax and client operations** | T-01…T-09, N-01…N-04, R-01…R-03, C-01, C-02, K-02 | **AY** (product, frontend, the amber `tax`, `notices` and `closes` modules, rules content) | **N** leads the red epics (T-01, N-01, N-02, C-02) and delivers red-zone services by contract ticket: consent gate and TRI, envelopes and KBA hand-off, CCH adapter, QBO read and W1 posting, OCR and regions, mailbox |
| **Track 4 · Agents, knowledge, engine and insights** | P-09, P-10, K-01, K-03…K-05, W-01…W-04, I-02…I-04 | **N** (runtime, gateway, engine backend) | **AY** owns the kits (T4, T18, T19, T20, T21), the frontend, and the library agents and knowledge content as database rows |

**Lane rules.**
- **PH0–PH2 split by layer.** N takes the red backend and infra. AY takes the design system, frontend, amber read models, compute libraries and the non-code programme. **From PH3,** AY owns selected amber verticals end to end (EBP compute, the tax pilot kit, notices, rules tables, QM), which removes frontend-to-backend hand-offs through N.
- **Amber backend assigned to AY by name, about 330 tasks:** sampler, materiality and RMM, SUM, EBP compute, JE scorer, flux and UDL, CAS reconciliation and flux, the tax compute engines (pure functions, golden tests, CPA review), read models (home, portal, insights), admin import endpoints, seed and clock fixtures, status codegen, and the `notices`, `quality`, `attest` and `practice` modules. N reviews.
- **Red stays with N:** identity and authz, kernel, evidence, connections, ledger, ai_gateway, agents, audit_trail, the new red modules (`review`, `signatures`, `adjustments`, `integrations`, consents, the tax red paths `approval`, `export` and `filing`), infra and migration control.
- **Red-zone service tickets.** When Track 3 needs red-zone work, AY files a ticket with the spec and the AC tests, written in a separate Claude session. N's ticket load is capped at about 25% of each sprint, and AY reviews the result. This restores ADR-078's separate test author.
- **On-call.** N holds SEV1/2 on-call for every live window. AY is the partner-facing owner and holds SEV3 and support triage. Each window names a backup, and from PH3 both founders are trained on every red runbook.

### 1.3.2 The contract-first handshake

1. **Request (consumer).** Open an issue `contract: <name> vN` that lists the screen IDs and artboard states it must serve, the seed figures that must foot and the human-only gates. The consumer writes the contract tests: pytest against the stub, plus TypeScript fixture assertions.
2. **Stub PR (provider, within 3 working days).** Pydantic models and route stubs returning seed-derived fixtures, permission-matrix actions, a flag, `make generate`, and `docs/contracts/<name>.md` (who may call it, status words, human-only actions, audit events). There is **one stub PR per screen family**, never one PR for a whole release. The consumer reviews it, and it merges in the next batch ahead of any feature PR that uses it.
3. **Parallel build.** The consumer builds in fixture mode on the existing fetch-swap harness (no MSW, no Storybook). The provider implements behind the same schema. The consumer's contract tests run in the **provider's** CI and must stay green.
4. **Swap and done.** The consumer flips from fixture to live. The journey's Playwright scenario passes with INV-1…5 and axe.
5. **Versioning.** Additive changes go in place. A breaking change ships as vN+1 with one sprint of overlap, and both founders approve it. `docs/contracts/` is code-owned by both.

**Contract register**

| C | Contract | Provider (epic) | Main consumers | Freeze |
|---|---|---|---|---|
| C1 | Work item and engagement lifecycle (8 states, G1–G3 facts, per-type gate policy) | N (F-03) | every module | S1 |
| C2 | Status registry: YAML → StrEnum, OpenAPI enums, `status.ts` | AY owns the YAML, N the codegen (F-03) | all | S1 |
| C3 | Review grammar: suggestion and change set, decision, sign_off (content hash, staleness, segregation), issue, checkpoint, field_value_version, human_gate | N (P-04) | A-*, T-*, C-*, I-01 | schema S3, services S12 |
| C4 | Citation v2, viewer manifest, regions, masked PII and logged reveal | N (P-03) | every trace surface | S5 |
| C5 | Requests and binders; portal scopes (`client_access_grant`, role union) | N (P-06, P-08), AY portal read models | A-01, R-01, T-02, C-01 | S3 |
| C6 | Agent runs: v1 read API; v2 run and step events over SSE | N (P-09, P-10) | dock, trace, Workbench, Today | v1 S12 · v2 S30 |
| C7 | Envelope service: record mode, then DocuSign embedded with provider ID Verification; evidence package; gate events | N (N-02) | ENG-04, SIG-*, POR-06, TAX-12, AUD-21, NOT-03 | record S14 · DocuSign S17 |
| C8 | Adjustments: proposed entries (8 states), threshold-policy versions, named-human batch approval | N (A-06) | EBP-06, T-05, C-02, A-09 eliminations | S24 |
| C9 | Ledger: TB layers, groupings and FS-line taxonomy, account mapping | N (A-02, A-03) | A-04, A-06, T-05, C-01, A-10 | layers S10 · taxonomy S20 |
| C10 | Deliverables and release registry with download audit | AY (R-02) | A-07, T-02 (K-1), C-02, X-01 | S29 |
| C11 | Deterministic PDF/DOCX renderer; templates in the database | N (P-11) | ENG-04, AUD-20…23, TAX-12, NOT-03, CLS-08, FSP-06 | S18 |
| C12 | TB hand-off into tax | AY (T-06) | AUD-38, CLS-12 | S50 |
| C13 | Human-gate projection registration slot (Home) | AY (I-01) with N (P-04) | every module | S10 |
| C14 | Board and program-status read model | N (K-04) | AUD-01/02, TAX-01, CLS-01/02, ATT-04 | S59 |
| C15 | Search registration | N (P-02); slot reserved by F-03 | all modules | slot S1 · index S39 |
| C16 | Notification kinds and transactional email templates (database) | N and AY (P-01, R-01) | all | S5 |
| C17 | Workbench tool registry (per-module read and compute tools, ADR-049) | N (P-10) | W-02, W-03, I-02 | S32 |
| C18 | Portal approvals (FS packages, client AJE approval) | AY (R-02) | A-06, A-07, C-02 | S30 |
| C19 | §7216 consent gate and TRI data class (gateway condition 6) | N (T-01) | T-*, N-04, W-02, I-02 | S17 |
| C20 | Integration framework and write-capability registry (firm, personal and client connections; W entries) | N (A-02, W-01) | POR-16, TAX-09, CLS-11, ATT-09, ADM-08 | framework S10 · catalogue S45 |
| C21 | Effective-dated rules tables (due dates, holidays, form sets and tolerances, thresholds, retention floors) | AY (K-02) | T-01, T-02, T-03, T-08, C-02, Q-05 | S17 |

**Cadence.**
- *Contract Monday*, day 1 of each sprint, 60 minutes: freeze what this sprint and the next need, review the decision log, name the sprint's protected bundle.
- *Thursday of week 1*, 30 minutes: blockers.
- *Friday of week 2*: sprint review with journeys on staging; velocity log and capacity ledger updated.
- *Review SLAs:* contract PRs the same day; red PRs within 1 working day; amber within 2.

### 1.3.3 Collision controls and working agreements

- **Protected-path hook (F-01).** `.claude/hooks/_protected.py` currently freezes `docs/adr/ADR-*.md` and `backend/migrations/versions/*` as soon as a file exists on disk. That blocks renumber-on-rebase and the editing of draft ADRs. It changes so that a path is immutable only if it exists on `origin/main` (checked with `git cat-file -e`, failing closed), and `approved_by:` accepts either founder's handle but never the PR author's.
- **CODEOWNERS.** Both handles stay on every path, with `*` plus the protected lines; area ownership is recorded through issue assignees instead. Single-owner directories are rejected because they deadlock code-owner review. Remove the stale `/backend/quality/`; add `/evals/`, `docs/operations/provider-terms.yaml` and `**/package.json`.
- **Number blocks.** ADR-116–199 N, ADR-200–299 AY; SPEC-037–099 N, SPEC-100–199 AY; TASK-077–499 N, TASK-500–999 AY.
- **Migrations.** The Alembic chain stays linear, with one migration per PR, renumber on rebase and a single-head CI check. Until Jun 1, 2027 a breaking change may land as one reversible migration (chapter 03's pre-launch policy); after that, strict expand/contract.
- **Regenerate, never hand-merge:** `openapi.json`, the api-client, `_matrix.py`, `_flags.py`, `_provider_terms.py`, replay histories and `durations.json`. A hook blocks hand edits.
- **Hot files.** In S1, `router.tsx` splits into lazy area subtrees, and the permission matrix and flags file get one section per module. `app.py` registration is sorted one per line, and AY owns `theme.css`. One module pre-registration PR lands in S1, and one protected bundle per sprint merges first.
- **Worktree isolation.** Each worktree gets its own `COMPOSE_PROJECT_NAME` and a port offset, and fixture mode runs without Docker. Each environment has its own database, and CI uses testcontainers. A `make` guard refuses a local production build or a manual migration while a hosted build or deploy is using the same database.
- **PR size.** Target about 600 hand-written lines; today the median is 865 and p90 is 4,091.
- **Earned autonomy.** An escaped-defect log runs from S0. Flagged, UI-only PRs earn ADR-086 green-zone auto-merge from about S10 once the log shows four clean sprints. This is the largest throughput lever for the frontend-heavy middle of the plan.
- **Release train (batch merges).** Approved PRs are held, and each says "holding for the batch". They merge in Tue and Thu windows at 17:00 CT, through a merge queue if the GitHub plan allows it, otherwise as one batch release-manifest PR (chapter 06, D-OPS-15). Staging deploys once per batch. Production promotes weekly (Thursday) from M9 and in the Tuesday 19:00 CT slot inside windows. The only exceptions are production broken, a security fix, or an explicit request. Preview builds are opt-in, fixture-mode static builds.
- **Content belongs in the database.** PBC templates, programs, organizers, letter, email and report templates, firm standards, rules tables, the integration catalogue and library agents are loaded through admin screens or import endpoints. The seed loader writes only the synthetic Brightwater Hale tenant.
- **Done means:** `make check` green; AC tests written in the other founder's session; journey e2e plus axe for the journeys touched; tier-B parity for templates (tier A for tokens, primitives and chrome strips); INV-1…5 asserted; the task log updated with an Owner and a hand-off note; the capacity ledger updated.

---

## 1.4 Canonical epic catalogue

**74 epics in 13 prefix groups.** Every one of the 303 `catalog.tsv` rows sits in exactly one epic: 256 product screens (142 P0, 84 P1, 30 P2), including CLI-03 and WB-05, which have no design board and carry a design task inside their epics (**T-06** and **W-03**), plus the 47 foundation rows (templates T1–T22, the O1–O6 overlay set and specimens TPL-01–24), which all sit in the design-system epics **F-05**…**F-08**. A script checked the assignment against `catalog.tsv`: 0 missing, 0 duplicates. No catalogue screen is excluded. D1–D10 and X-01…X-08 constrain states and data, not screens (§1.7). These IDs supersede the draft epic keys EP-01…EP-28 used in chapter 09's "Blocks" columns; map those through their screen IDs.

**How to read the table.**
- **Phase** is where the epic's work falls (PH0–PH7, §1.2.1).
- **Track** is 0–4 (§1.3.1).
- **Lead** is the accountable founder. N + AY marks an epic that both founders decide jointly. Both founders write code in most epics; the per-founder split sits in the capacity ledger (§1.8.3).
- **Sprints** are the build window. Go-lives and flag flips follow the gates in §1.2.2, which can fall after the window closes.
- **Size** is in FW of 14 tasks. It counts screen tasks from catalogue complexity with repo-coverage discounts, plus an explicit allowance for engines, integrations, infra, compliance and seed (§1.8.2).
- **Screens** shows the count, then P0/P1/P2/F, where F counts the foundation rows.
- **F-09**, **Q-03** and **Q-04** are funded outside planned coding capacity: F-09 from AY's non-coding time, Q-03 from the 22.5% reserve, Q-04 from the pilot-support reserve.
- **F-01** and 20 tasks of **Q-01** are also reserve-funded, because in S0–S5 the reserve pays for CI and infrastructure.

### 1.4.1 Catalogue


**F · Foundations and unblock**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **F-01** | Two-founder governance, CI enforcement & repo safety | PH0–PH1 | 0 | N | S0–S1 · Oct 19, 2026 – Nov 13, 2026 | 0.9 (reserve) | — | — |
| **F-02** | Decision Day, ADR programme & glossary | PH0–PH1 | 0 | N + AY | S0–S2 · Oct 19, 2026 – Nov 27, 2026 | 0.4 | — | F-01 |
| **F-03** | Domain model migrations & contract register | PH0–PH1 | 0 | N | S0–S4 · Oct 19, 2026 – Dec 25, 2026 | 2.1 | — | F-01, F-02 |
| **F-04** | Seed universe, demo clock, fakes & journey harness | PH1–PH2 | 0 | AY | S1–S9 · Nov 2, 2026 – Mar 5, 2027 | 2.0 | — | F-03 |
| **F-05** | Design system core & MVP templates (DS tiers 0-2) | PH0–PH2 | 0 | AY | S0–S10 · Oct 19, 2026 – Mar 19, 2027 | 4.2 | 21 (0/0/0/21) | F-01, F-02 |
| **F-06** | Design system tier 3: workbook, document, signing & tax surfaces | PH2–PH3 | 0 | AY | S14–S24 · May 3, 2027 – Oct 1, 2027 | 1.4 | 8 (0/0/0/8) | F-05 |
| **F-07** | Design system tier 4: agent chat, calendar, graph & form surfaces | PH4–PH5 | 0 | AY | S38–S43 · Apr 3, 2028 – Jun 23, 2028 | 1.5 | 8 (0/0/0/8) | F-06 |
| **F-08** | Design system tier 5: Sheet, Board, editor, analytics & add-in surfaces | PH5–PH6 | 0 | AY | S50–S55 · Sep 18, 2028 – Dec 8, 2028 | 2.6 | 10 (0/0/0/10) | F-07 |
| **F-09** | Vendor, design-partner & commercial programme (non-code) | PH0–PH3 | 0 | AY | S0–S30 · Oct 19, 2026 – Dec 24, 2027 | 16 (non-code) | — | — |

**P · Platform engines**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **P-01** | Firm shell, sign-in & notifications | PH1–PH2 | 1 | AY | S2–S7 · Nov 16, 2026 – Feb 5, 2027 | 0.8 | 4 (4/0/0/0) | F-03, F-05, Q-01 |
| **P-02** | Search & command palette | PH5 | 1 | N | S39–S41 · Apr 17, 2028 – May 26, 2028 | 0.7 | 1 (1/0/0/0) | P-01, F-03 |
| **P-03** | Trust kit v1: citations v2 & source viewer | PH1–PH2 | 1 | N | S5–S12 · Dec 28, 2026 – Apr 16, 2027 | 1.7 | 2 (2/0/0/0) | F-03, F-05, Q-02 |
| **P-04** | Review grammar & sign-off engine | PH1–PH3 | 1 | N | S3–S26 · Nov 30, 2026 – Oct 29, 2027 | 3.6 | 6 (6/0/0/0) | F-03, P-03 |
| **P-05** | Collaboration: comments v2, to-dos & activity log | PH4 | 1 | AY | S33–S37 · Jan 24, 2028 – Mar 31, 2028 | 0.8 | 3 (2/1/0/0) | P-01, P-04 |
| **P-06** | Requests & binders engine | PH1–PH2 | 1 | N | S3–S10 · Nov 30, 2026 – Mar 19, 2027 | 1.5 | 4 (4/0/0/0) | F-03, P-03 |
| **P-07** | Clients, engagements & gates G1-G3 | PH1–PH2 | 1 | N | S4–S15 · Dec 14, 2026 – May 28, 2027 | 3.5 | 11 (6/5/0/0) | F-03, P-01 |
| **P-08** | Portal shell & client identity | PH1–PH2 | 1 | N | S4–S11 · Dec 14, 2026 – Apr 2, 2027 | 1.3 | 2 (2/0/0/0) | F-03, Q-01 |
| **P-09** | Agent transparency v1: run dock & trace | PH4 | 4 | N | S31–S34 · Dec 27, 2027 – Feb 18, 2028 | 1.1 | 2 (2/0/0/0) | P-04 |
| **P-10** | Agent runtime v2 & real-time (SSE) | PH3–PH4 | 4 | N | S29–S38 · Nov 29, 2027 – Apr 14, 2028 | 3.9 | — | P-04, Q-02 |
| **P-11** | Document services: renderer, OCR & regions | PH3–PH4 | 1 | N | S17–S34 · Jun 14, 2027 – Feb 18, 2028 | 2.0 | — | Q-01, P-03 |

**K · Knowledge and configurable engine**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **K-01** | Knowledge library & methodology v1 | PH2–PH3 | 4 | AY | S10–S26 · Mar 8, 2027 – Oct 29, 2027 | 1.4 | 3 (3/0/0/0) | P-06, F-03 |
| **K-02** | Firm standards, rules tables & content import | PH3 | 3 | AY | S16–S19 · May 31, 2027 – Jul 23, 2027 | 1.1 | 1 (0/1/0/0) | F-03, G-01 |
| **K-03** | Templates v2 & Sheets engine | PH6 | 4 | N | S52–S60 · Oct 16, 2028 – Feb 16, 2029 | 4.4 | 7 (6/1/0/0) | P-04, P-10, F-08, K-01 |
| **K-04** | Board, triggers, review package & set up with AI | PH6 | 4 | N | S59–S65 · Jan 22, 2029 – Apr 27, 2029 | 3.6 | 6 (3/3/0/0) | K-03, P-10 |
| **K-05** | Learning layer & content: skills, learned context, packs, notes | PH7 | 4 | AY | S67–S72 · May 14, 2029 – Aug 3, 2029 | 2.2 | 4 (0/3/1/0) | K-03, P-10 |

**A · Assurance and audit**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **A-01** | Audit evidence spine & binder export | PH2 | 2 | N | S7–S13 · Jan 25, 2027 – Apr 30, 2027 | 1.3 | 3 (3/0/0/0) | P-06, P-03, P-07 |
| **A-02** | Trial balance & ledger connections | PH2–PH3 | 2 | N | S8–S17 · Feb 8, 2027 – Jun 25, 2027 | 1.9 | 2 (1/1/0/0) | A-01, Q-01, F-09 |
| **A-03** | Sampling & TB mapping | PH3 | 2 | AY | S20–S23 · Jul 26, 2027 – Sep 17, 2027 | 1.0 | 2 (2/0/0/0) | A-02, P-06 |
| **A-04** | Audit planning & risk (G4) | PH3 | 2 | AY | S22–S28 · Aug 23, 2027 – Nov 26, 2027 | 2.6 | 6 (5/1/0/0) | P-04, K-01, F-06, A-02 |
| **A-05** | EBP plan audits | PH3–PH4 | 2 | AY | S23–S31 · Sep 6, 2027 – Jan 7, 2028 | 3.7 | 10 (6/4/0/0) | A-04, A-03, A-06, P-03 |
| **A-06** | Findings, adjustments, review notes & FS draft | PH3 | 2 | N | S24–S30 · Sep 20, 2027 – Dec 24, 2027 | 2.0 | 4 (4/0/0/0) | P-04, A-04 |
| **A-07** | EQR, completion, letters, report, release & archive (G6-G9) | PH3–PH4 | 2 | N | S27–S36 · Nov 1, 2027 – Mar 17, 2028 | 3.4 | 7 (7/0/0/0) | A-06, N-02, P-11, R-02 |
| **A-08** | Audit fieldwork depth | PH5 | 2 | AY | S45–S50 · Jul 10, 2028 – Sep 29, 2028 | 2.3 | 5 (0/5/0/0) | A-03, A-04, P-04 |
| **A-09** | Group audit (SAS 149) | PH5 | 2 | N | S45–S50 · Jul 10, 2028 – Sep 29, 2028 | 2.3 | 5 (5/0/0/0) | A-03, A-04, P-04 |
| **A-10** | Statements studio | PH6 | 2 | AY | S58–S64 · Jan 8, 2029 – Apr 13, 2029 | 2.8 | 6 (3/2/1/0) | A-07, F-08, A-03 |
| **A-11** | Agentic audit: procedure session & pre-review | PH6–PH7 | 2 | N | S65–S68 · Apr 16, 2029 – Jun 8, 2029 | 1.1 | 2 (0/2/0/0) | K-03, K-04, P-10 |

**X · Attest and internal audit**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **X-01** | Attest core (SOC 1/2, AUP, readiness) & frameworks | PH6–PH7 | 2 | AY | S62–S69 · Mar 5, 2029 – Jun 22, 2029 | 4.0 | 10 (0/10/0/0) | K-03, K-04, A-07, A-10 |
| **X-02** | Attest depth: ISO readiness & GRC sync | PH7 | 2 | N | S68–S72 · May 28, 2029 – Aug 3, 2029 | 1.0 | 2 (0/0/2/0) | X-01, W-01 |
| **X-03** | Co-sourced internal audit | PH7 | 2 | AY | S68–S73 · May 28, 2029 – Aug 17, 2029 | 1.5 | 5 (0/0/5/0) | X-01, K-03 |

**T · Tax**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **T-01** | Tax compliance rails: §7216 gate, CCH file bridge, e-file record | PH3 | 3 | N | S16–S21 · May 31, 2027 – Aug 20, 2027 | 3.9 | 5 (2/3/0/0) | P-08, Q-02, N-02, K-02 |
| **T-02** | Tax extension-season pilot kit | PH3 | 3 | AY | S16–S21 · May 31, 2027 – Aug 20, 2027 | 2.0 | 6 (6/0/0/0) | T-01, P-06, R-01 |
| **T-03** | TY2027 season readiness: organizer editor, extensions & rules tables | PH3 | 3 | AY | S26–S29 · Oct 18, 2027 – Dec 10, 2027 | 1.0 | 2 (0/2/0/0) | T-02, K-02 |
| **T-04** | Return workspace & individual returns | PH4–PH5 | 3 | AY | S32–S39 · Jan 10, 2028 – Apr 28, 2028 | 3.5 | 8 (6/2/0/0) | T-02, P-04, P-10, P-11 |
| **T-05** | Entity return workspace & K-1 engines (P0) | PH4–PH5 | 3 | AY | S35–S44 · Feb 21, 2028 – Jul 7, 2028 | 5.1 | 8 (8/0/0/0) | T-04, A-03, A-06 |
| **T-06** | Entity return depth, relationships & hand-offs (P1) | PH5–PH6 | 3 | AY | S49–S55 · Sep 4, 2028 – Dec 8, 2028 | 4.1 | 8 (0/8/0/0) | T-05, F-07, A-07 |
| **T-07** | Trusts & estates (1041 / 706 / 709) | PH5 | 3 | AY | S44–S47 · Jun 26, 2028 – Aug 18, 2028 | 1.6 | 4 (2/1/1/0) | T-05, P-11 |
| **T-08** | Tax season & practice tools (TY2028) | PH5–PH6 | 3 | AY | S50–S55 · Sep 18, 2028 – Dec 8, 2028 | 2.4 | 6 (0/5/1/0) | T-03, F-07 |
| **T-09** | Advisory projects & research | PH7 | 3 | AY | S66–S70 · Apr 30, 2029 – Jul 6, 2029 | 1.4 | 3 (0/1/2/0) | P-11, T-06 |

**C · CAS and closes**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **C-01** | Close engine (read-only QBO) | PH5 | 3 | AY | S44–S51 · Jun 26, 2028 – Oct 13, 2028 | 3.9 | 9 (8/1/0/0) | A-02, P-04, P-11 |
| **C-02** | Ledger posting, deliverables & hand-offs | PH5–PH6 | 3 | N | S49–S55 · Sep 4, 2028 – Dec 8, 2028 | 3.2 | 5 (2/3/0/0) | C-01, A-06, W-01 |

**N · Intake, delivery, notices, signatures, files**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **N-01** | Firm inbox, triage & files | PH2–PH3 | 3 | N | S13–S18 · Apr 19, 2027 – Jul 9, 2027 | 1.7 | 3 (3/0/0/0) | P-06, P-08 |
| **N-02** | Signatures & engagement letters | PH2–PH3 | 3 | N | S13–S21 · Apr 19, 2027 – Aug 20, 2027 | 3.6 | 4 (4/0/0/0) | P-11, F-06, F-09 |
| **N-03** | Firm mailbox, compose & client messages | PH6 | 3 | AY | S56–S62 · Dec 11, 2028 – Mar 16, 2029 | 2.3 | 5 (0/5/0/0) | N-01, F-09, P-10 |
| **N-04** | Notices | PH3 | 3 | AY | S25–S29 · Oct 4, 2027 – Dec 10, 2027 | 1.6 | 3 (3/0/0/0) | T-01, P-11, N-02 |

**R · Client portal**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **R-01** | Portal PBC core & white-label | PH2–PH3 | 3 | AY | S7–S18 · Jan 25, 2027 – Jul 9, 2027 | 1.6 | 5 (3/2/0/0) | P-08, P-06 |
| **R-02** | Portal approvals, deliverables & governance room | PH3–PH4 | 3 | AY | S29–S35 · Nov 29, 2027 – Mar 3, 2028 | 1.2 | 3 (2/1/0/0) | R-01 |
| **R-03** | Portal mobile capture, payments link-outs & prospect intake | PH6 | 3 | AY | S59–S63 · Jan 22, 2029 – Mar 30, 2029 | 1.0 | 3 (0/1/2/0) | R-01, P-11 |

**W · Workbench and Office**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **W-01** | Integration catalogue & Connect | PH5 | 4 | N | S45–S48 · Jul 10, 2028 – Sep 1, 2028 | 1.1 | 2 (2/0/0/0) | A-02 |
| **W-02** | Workbench sessions | PH5 | 4 | N | S40–S45 · May 1, 2028 – Jul 21, 2028 | 1.8 | 3 (3/0/0/0) | P-10, F-07 |
| **W-03** | Agent library, my agents, schedules & saved prompts | PH6–PH7 | 4 | N | S63–S69 · Mar 19, 2029 – Jun 22, 2029 | 1.8 | 6 (5/1/0/0) | W-02, P-10 |
| **W-04** | Office add-ins | PH7 | 4 | AY | S69–S73 · Jun 11, 2029 – Aug 17, 2029 | 1.4 | 2 (0/1/1/0) | K-03, A-10 |

**G · Governance, admin and platform console**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **G-01** | Firm settings, users, roles, offices & walls | PH1–PH2 | 1 | N | S6–S13 · Jan 11, 2027 – Apr 30, 2027 | 1.0 | 3 (2/1/0/0) | F-03, P-01 |
| **G-02** | AI policy, security center & audit log | PH2 | 1 | N | S9–S14 · Feb 22, 2027 – May 14, 2027 | 1.6 | 3 (0/3/0/0) | Q-02, G-01 |
| **G-03** | Developer platform & data model | PH7 | 1 | N | S69–S73 · Jun 11, 2029 – Aug 17, 2029 | 1.9 | 2 (0/0/2/0) | P-10, W-01 |
| **G-04** | Platform console, plan & usage, support panel | PH5 | 1 | N | S47–S51 · Aug 7, 2028 – Oct 13, 2028 | 1.1 | 3 (0/0/3/0) | F-03, Q-04 |

**I · Home and insights**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **I-01** | Home & approvals queue | PH2–PH4 | 1 | AY | S10–S35 · Mar 8, 2027 – Mar 3, 2028 | 1.4 | 2 (2/0/0/0) | P-04, P-01 |
| **I-02** | Today brief | PH5 | 4 | N | S40–S43 · May 1, 2028 – Jun 23, 2028 | 1.0 | 2 (2/0/0/0) | P-10, I-01 |
| **I-03** | Insights | PH6–PH7 | 4 | AY | S61–S67 · Feb 19, 2029 – May 25, 2029 | 2.2 | 5 (0/4/1/0) | Q-04, F-08 |
| **I-04** | Practice economics & capacity | PH7 | 4 | AY | S70–S73 · Jun 25, 2029 – Aug 17, 2029 | 1.5 | 3 (0/0/3/0) | I-03, W-01 |

**Q · Quality, operations, compliance and infrastructure**

| Epic | Name | Phase | Track | Lead | Sprints (dates) | Size FW | Screens (P0/P1/P2/F) | Key dependencies |
|---|---|---|---|---|---|---|---|---|
| **Q-01** | Infrastructure, environments & platform services | PH0–PH1 | 0 | N | S0–S5 · Oct 19, 2026 – Jan 8, 2027 | 3.6 (1.4 reserve) | — | F-01 |
| **Q-02** | Real-data readiness & compliance programme | PH0–PH2 | 0 | N | S0–S13 · Oct 19, 2026 – Apr 30, 2027 | 2.9 | — | Q-01 |
| **Q-03** | Hardening & test back-fill (reserve-funded) | PH1–PH7 | 0 | N + AY | S6–S73 · Jan 11, 2027 – Aug 17, 2029 | 47 (reserve) | — | F-01 |
| **Q-04** | Pilot operations, release train & freeze contract | PH2–PH7 | 0 | N + AY | S12–S74 · Apr 5, 2027 – Aug 31, 2029 | 0.6 + 30 (support) | — | Q-02 |
| **Q-05** | Quality management & records governance | PH5–PH6 | 2 | AY | S50–S54 · Sep 18, 2028 – Nov 24, 2028 | 1.6 | 5 (0/0/5/0) | A-07, Q-02 |

**Totals.** The 71 build epics come to about 2,120 tasks, or **151 FW**. Of that, about 32 tasks are reserve-funded (all of F-01 and part of Q-01), which leaves about 2,090 planned tasks against 2,093 of planned capacity over S0–S73. In addition: Q-03 is about 47 FW of reserve, Q-04 is about 30 FW of pilot support, and AY's non-code time is about 37 FW over the horizon, 16 FW of it in F-09 up to Dec 2027.


### 1.4.2 Screen and board assignment (all 303 rows)

| Epic | Screens and boards (catalogue IDs) |
|---|---|
| **F-05** | O1-O6, T1, T2, T3, T5, T7, T8, T9, T11, T12, T15, TPL-02, TPL-03, TPL-05, TPL-07, TPL-08, TPL-09, TPL-11, TPL-12, TPL-15, TPL-18 |
| **F-06** | T6, T10, T16, TPL-01, TPL-06, TPL-10, TPL-16, TPL-19 |
| **F-07** | T4, T13, T14, T17, TPL-04, TPL-13, TPL-14, TPL-17 |
| **F-08** | T18, T19, T20, T21, T22, TPL-20, TPL-21, TPL-22, TPL-23, TPL-24 |
| **P-01** | SHL-01, SHL-03, SHL-04, SHL-06 |
| **P-02** | SHL-02 |
| **P-03** | SHL-07, SHL-08 |
| **P-04** | SHL-09, SHL-10, SHL-11, SHL-12, SHL-15, SHL-16 |
| **P-05** | SHL-17, SHL-18, AUD-29 |
| **P-06** | BND-01, BND-02, SHL-14, SHL-20 |
| **P-07** | CLI-01, CLI-02, CLI-04, CLI-06, CLI-07, CLI-08, ENG-01, ENG-02, ENG-03, ENG-05, ENG-13 |
| **P-08** | POR-01, POR-02 |
| **P-09** | SHL-13, WB-09 |
| **K-01** | KNW-01, KNW-02, KNW-03 |
| **K-02** | KNW-04 |
| **K-03** | SHT-01, SHT-02, SHT-03, SHT-04, KNW-06, KNW-07, SHL-22 |
| **K-04** | ENG-10, ENG-11, ENG-12, ENG-14, SHL-19, SHL-21 |
| **K-05** | KNW-08, KNW-11, KNW-12, WB-13 |
| **A-01** | AUD-01, AUD-02, AUD-03 |
| **A-02** | AUD-06, POR-16 |
| **A-03** | AUD-11, AUD-31 |
| **A-04** | AUD-04, AUD-05, AUD-07, AUD-08, AUD-09, AUD-10 |
| **A-05** | EBP-01, EBP-02, EBP-03, EBP-04, EBP-05, EBP-06, EBP-07, EBP-08, EBP-09, AUD-27 |
| **A-06** | AUD-15, AUD-16, AUD-17, AUD-20 |
| **A-07** | AUD-18, AUD-19, AUD-21, AUD-22, AUD-23, AUD-24, AUD-25 |
| **A-08** | AUD-12, AUD-13, AUD-14, AUD-26, POR-17 |
| **A-09** | AUD-32, AUD-33, AUD-34, AUD-35, POR-23 |
| **A-10** | FSP-01, FSP-02, FSP-03, FSP-04, FSP-05, FSP-06 |
| **A-11** | AUD-36, AUD-37 |
| **X-01** | KNW-09, KNW-10, ATT-01, ATT-02, ATT-03, ATT-04, ATT-05, ATT-06, ATT-07, POR-21 |
| **X-02** | ATT-08, ATT-09 |
| **X-03** | IAU-01, IAU-02, IAU-03, IAU-04, POR-22 |
| **T-01** | CLI-05, ADM-05, ADM-08, TAX-09, TAX-12 |
| **T-02** | TAX-01, TAX-02, TAX-03, TXP-12, POR-05, POR-13 |
| **T-03** | BND-03, TAX-13 |
| **T-04** | TAX-04, TAX-05, TAX-06, TAX-07, TAX-08, TXI-01, TXI-02, TXI-03 |
| **T-05** | TXP-00, TXP-01, TXP-02, TXP-05, TXP-06, TXP-07, TXP-10, TXP-11 |
| **T-06** | TXP-03, TXP-04, TXP-08, TXP-09, TXP-13, TAX-11, CLI-03, AUD-38 |
| **T-07** | TXT-01, TXT-02, TXT-03, TXT-04 |
| **T-08** | ENG-07, HOME-03, TAX-10, TAX-14, TAX-15, TAX-16 |
| **T-09** | ENG-09, PRJ-01, KNW-05 |
| **C-01** | CLS-01, CLS-02, CLS-03, CLS-04, CLS-05, CLS-06, CLS-09, CLS-10, POR-11 |
| **C-02** | CLS-07, CLS-08, CLS-11, CLS-12, CLS-13 |
| **N-01** | INB-01, INB-02, FIL-01 |
| **N-02** | SIG-01, SIG-02, POR-06, ENG-04 |
| **N-03** | BND-04, INB-03, INB-04, POR-07, POR-12 |
| **N-04** | NOT-01, NOT-02, NOT-03 |
| **R-01** | POR-03, POR-04, POR-14, POR-20, ADM-10 |
| **R-02** | POR-08, POR-09, POR-15 |
| **R-03** | POR-10, POR-18, POR-19 |
| **W-01** | WB-10, WB-11 |
| **W-02** | WB-01, WB-02, WB-03 |
| **W-03** | WB-04, WB-05, WB-06, WB-07, WB-08, WB-12 |
| **W-04** | XLA-01, XLA-02 |
| **G-01** | ADM-01, ADM-02, ADM-03 |
| **G-02** | ADM-04, ADM-06, ADM-07 |
| **G-03** | ADM-09, ADM-13 |
| **G-04** | PLT-01, ADM-14, SHL-05 |
| **I-01** | HOME-01, HOME-02 |
| **I-02** | SHL-23, HOME-05 |
| **I-03** | INS-01, INS-02, INS-03, INS-04, INS-05 |
| **I-04** | ENG-06, ENG-08, HOME-04 |
| **Q-05** | AUD-28, AUD-30, ADM-11, ADM-12, FIL-02 |

Epics with no screens: F-01, F-02, F-03, F-04, F-09, P-10, P-11, Q-01, Q-02, Q-03, Q-04.


### 1.4.3 Epic scope notes

Each note gives the goal, the backend modules, and the ADRs and decisions the epic depends on. Proposed ADRs are written "ADR P-nn"; decisions minted in chapters 03, 05 and 06 are cited by name.


#### F · Foundations and unblock

- **F-01 · Two-founder governance, CI enforcement & repo safety** (S0–S1 · N · 0.9 FW, reserve-funded). Make two-founder work safe on day 1: scan the full git history for secrets and rotate anything exposed, then make the repo private (logged in the SOC 2 risk assessment); ruleset with the other founder's code-owner review and stages 1+2 required; fix _protected.py (a path is immutable only if it exists on origin/main, fail closed; approved_by accepts either founder's handle, never the PR author); both handles on every CODEOWNERS path; rebuild CI (green main, nightly e2e, stage 2 on main and merge_group, shard timings, single-head Alembic check, vite build for both entries, backend shards skipped on frontend-only diffs); per-worktree Docker isolation (COMPOSE_PROJECT_NAME + port offset, fixture mode without Docker); a make guard that refuses a local production build or migration while a hosted build uses the same database; number blocks; a regenerate-never-hand-merge hook; Tue/Thu batch merge windows; ~600-line PR target; review SLAs; escaped-defect log. Reserve-funded. *Modules:* .github, .claude/hooks, abacus_tools/quality, docker-compose.yml, Makefile. *Decisions:* ADR P-02 two-founder governance; ch.06 release-train ADR (amends ADR-088); ADR-083/084/086 applied to two founders. *Journeys:* all (precondition).
- **F-02 · Decision Day, ADR programme & glossary** (S0–S2 · N + AY · 0.4 FW). Hold Decision Day on Fri Oct 23, 2026 once drafts exist and record the §1.9 agenda in chapter 09's DEC register with owners; adopt chapter 09's ADR backlog (P-01..P-63) and reserve real numbers from ADR-116 in needed-by order, each with an owner, a draft sprint and an acceptance sprint one phase before the line that needs it; land the single glossary PR and the must-not-build guards for D1-D10 and X-01..X-08 (13-item nav test, persona lint, Single Audit card fixed at Coming soon, no excluded framework rows). *Modules:* docs/adr, docs/product/glossary.md, docs/product/decision-log.md. *Decisions:* ADR P-01 naming; ADR P-02; ADR P-03 design system (supersedes SPEC-016); ADR P-29 busy-season policy; Q-01/Q-02/Q-04/Q-07/Q-08. *Journeys:* all (precondition).
- **F-03 · Domain model migrations & contract register** (S0–S4 · N · 2.1 FW). Migrate the model once, before any real data: work_items supertype for all five kinds (assurance, tax_return, close, notice, advisory_project) with the 8-state engagement lifecycle and a per-type gate policy; request status enum migration; contacts, client_access_grant and scope_only; role catalogue and matrix conditions; offices and teams; status registry codegen from blueprint 3.3.1 + addendum 3.2; /v1/me/capabilities and the list envelope; DB entitlements so flags stay rollout-only; one module pre-registration PR (ROUTERS, TABLE_OWNERS, MODULE_DEPENDENCIES, importlinter, per-module matrix and flag sections, new red modules declared in _protected.py, protected-paths.md and CODEOWNERS); router.tsx split into lazy area subtrees; the contract register C1-C21 with consumer-written contract tests in the provider's CI. *Modules:* engagements, identity, organisations, requests, platform, kernel, apps/web router. *Decisions:* ADR P-04 work items & gates; ADR P-05 module map; ADR P-06 visible(); ADR P-09 client scopes; ADR P-10 role catalogue; ADR P-28 entitlements; ch.03 status-registry, request-enum and pre-launch migration ADRs. *Journeys:* all (precondition), J01, J02, J13.
- **F-04 · Seed universe, demo clock, fakes & journey harness** (S1–S9 · AY · 2.0 FW). Brightwater Hale synthetic tenant loaded by epoch through service APIs (E0 audit subset first, E1/E2 for tax and CAS later); injectable clock replacing ~51 now() call sites; fakes for WorkOS mail, SES and the scanner (CCH, QBO, NetSuite, DocuSign/KBA, M365 and Drata added in the phases that need them); golden-figure tests; route registry generated from handoff-link-graph.json; jNN Playwright journeys asserting INV-1..5 plus axe; local parity report. The firm, not the names, is flagged synthetic. *Modules:* scenarios/brightwater_hale, kernel.clock, apps/web/e2e. *Decisions:* ch.03 clock and synthetic-firm ADR. *Journeys:* all (harness).
- **F-05 · Design system core & MVP templates (DS tiers 0-2)** (S0–S10 · AY · 4.2 FW). Replace the Atelier look with the Accrued design system: tokens and Tailwind v4 theme, self-hosted Geist/Geist Mono/Arimo/Gelasio, the AA text ladder, format.ts (bigint decimals), generated status.ts, icon registry, primitives, overlays O1-O6, toasts with deferred-commit Undo, DataTable grammars, SourceViewer shell, MatchProvider, the MVP layout templates and their specimens in an in-app /components gallery with tiered Playwright parity and axe; retire or re-skin the 51 Atelier screens. *Modules:* packages/ui, apps/web. *Decisions:* ADR P-03 (supersedes SPEC-016); D-DS-1..12 incl. AA ink ladder; allowlist bundle #1. *Journeys:* chrome of every journey.
- **F-06 · Design system tier 3: workbook, document, signing & tax surfaces** (S14–S24 · AY · 1.4 FW). Tier-3 kits ahead of their consumers: T16 signing ceremony first (for N-02), then T6 workbook grid and T10 document-on-well (for planning, EBP and completion), the tax index specimen and the 390-px portal mobile specimen. *Modules:* packages/ui. *Decisions:* ADR P-03. *Journeys:* J03, J06, J12.
- **F-07 · Design system tier 4: agent chat, calendar, graph & form surfaces** (S38–S43 · AY · 1.5 FW). Tier-4 kits: T4 Workbench chat (for W-02), T13 calendar (HOME-03), T14 graph canvas (CLI-03) and T17 form renderer (TAX-11), with specimens. *Modules:* packages/ui. *Decisions:* ADR P-03. *Journeys:* J06, J08, J11.
- **F-08 · Design system tier 5: Sheet, Board, editor, analytics & add-in surfaces** (S50–S55 · AY · 2.6 FW). Tier-5 kits: T18 Sheet (virtualised grid), T19 Board, T20 Document editor (TipTap, no CRDT), T21 analytics dashboard and T22 Office add-in pane, with specimens. *Modules:* packages/ui. *Decisions:* editor-framework ADR; ADR P-15 SSE presence. *Journeys:* J21, J22, J24, J25, J27.
- **F-09 · Vendor, design-partner & commercial programme (non-code)** (S0–S30 · AY · 16 (non-code)). Non-code programme run by ayushkbhatia from the non-coding share of their time: file every long-lead application in S0 (Intuit, Xero, NetSuite SDN, Wolters Kluwer, DocuSign Go-Live and ID Verification, Microsoft publisher verification, SES, Google CASA if needed); SOC 2 tool, auditor and pen-test vendor; counsel (MSA/DPA, Sec. 7216 consent text naming AWS Bedrock, ERSD, Pub 1345, offshore question, BAA posture); cyber and tech E&O insurance; named design-partner target lists per window and LOIs by Nov 20; Pilot 0 sessions; the SQMS 1 Technology Resource Pack by Dec 15, 2026; pricing hypothesis, founding-partner agreement, external-spend plan and the M12 conversion gate (Aug 20, 2027). *Modules:* docs/product/discovery, docs/ops/vendors. *Decisions:* DEC-03 AWS spend and region; DEC-17 vendor applications; proposed DEC-100 pricing; proposed DEC-101 hiring trigger. *Journeys:* all.

#### P · Platform engines

- **P-01 · Firm shell, sign-in & notifications** (S2–S7 · AY · 0.8 FW). Firm shell on the Accrued design: 13-item toolbar with measured overflow, firm switcher and profile, notifications v2 (catalogue with read-time facts, email via SES), sign-in on hosted WorkOS (custom T15 card waits for the ADR-030 amendment). *Modules:* identity, notifications. *Decisions:* ADR P-06; ADR-030 amendment (later). *Journeys:* J01, J13, J16, J11.
- **P-02 · Search & command palette** (S39–S41 · N · 0.7 FW). Go... command palette over Postgres full-text search with wall-safe counts and the search-registration slot (C15). *Modules:* platform (search_documents). *Decisions:* ADR P-33 Postgres search; ADR P-06. *Journeys:* J13, J16.
- **P-03 · Trust kit v1: citations v2 & source viewer** (S5–S12 · N · 1.7 FW). Citation popover and source viewer v1 over server-rendered pages: first-class citation v2 table (C4), viewer manifest, word boxes and regions, masked PII renditions with logged reveal, password unlock without breaking immutability. No pdf.js. *Modules:* evidence (red), review. *Decisions:* ADR-066 extension; AG-07 citation v2. *Journeys:* J03, J04, J06, J08, J16.
- **P-04 · Review grammar & sign-off engine** (S3–S26 · N · 3.6 FW). The review grammar, red module 'review': schema and migration in S3-S4 before any real data (suggestion and change sets, decision, sign_off L1-L5 with content hash, staleness and segregation, issue, checkpoint, field_value_version, human_gate projection), every human gate on the repo's four-way pattern plus an INV-1 test; decision and sign-off services in S10-S16; UI in S16-S26: SHL-10 approve agent output first (live-stage agents on Jul 13, 2027), SHL-16 checkpoint diff for the tax pilot's import diff, then decision card, sign-off, issue composer and field provenance. *Modules:* review (new, red), agents (suggestions), evidence. *Decisions:* ADR P-07 sign-offs; ch.03 generic-suggestions ADR; AG-08 Undo as compensating event. *Journeys:* J03, J04, J06, J13, J23.
- **P-05 · Collaboration: comments v2, to-dos & activity log** (S33–S37 · AY · 0.8 FW). Comments v2 on polymorphic anchors (resolve and reopen as events, no edit or delete under ADR-109), to-dos, and the engagement activity log over the audit_trail read API. *Modules:* collaboration (new), audit_trail (red). *Decisions:* ch.03 generalised-comments ADR (amends ADR-109); R6 to-do never task. *Journeys:* J16, J23, J03, J18.
- **P-06 · Requests & binders engine** (S3–S10 · N · 1.5 FW). Requests and binders for every service line: binder = many request_lists per work item, Draft/publish, Not applicable/Ignored with reason, wrong_document reason, staff accept, Linked (n), screening aggregate, human-sent follow-up drafts, client withdrawal of unaccepted uploads. *Modules:* requests, evidence (red), agents. *Decisions:* Q-04 enum (F-03); ADR P-31 withdrawal; ADR-005/SPEC-033 kept: a person assigns. *Journeys:* J03, J06, J10, J16, J22.
- **P-07 · Clients, engagements & gates G1-G3** (S4–S15 · N · 3.5 FW). Clients and engagements with server-enforced gates G1-G3: client index and record, contacts and portal access (14-day invites), bulk client and contact import for pilot onboarding, acceptance and independence performed in-app by humans (AI pre-screen later), data-driven engagement-type wizard (Single Audit stays Coming soon), team and roles with G2, roll-forward re-skin. *Modules:* organisations (red), engagements, identity. *Decisions:* ADR P-04 gate service; SPEC-025 non-goals superseded (DEC-64); ADR P-13 independence. *Journeys:* J02, J03, J19, J25.
- **P-08 · Portal shell & client identity** (S4–S11 · N · 1.3 FW). White-label portal shell and client identity: WorkOS email-code sign-in with lockout, role-union home, client_access_grant enforcement with scope_only, MFA mandatory for owners and signers, host-resolved branding route. *Modules:* portal (new), identity (red), communications. *Decisions:* ADR P-09; ADR P-11; ADR-030 amendment (MFA). *Journeys:* J02, J12.
- **P-09 · Agent transparency v1: run dock & trace** (S31–S34 · N · 1.1 FW). Run dock and run trace v1 over existing agent runs (read-only, polling until SSE lands), with structured AgentBlocks rendering. *Modules:* agents (red), ai_gateway. *Decisions:* ADR P-24 structured output; AG-05. *Journeys:* J03, J10, J11, J18.
- **P-10 · Agent runtime v2 & real-time (SSE)** (S29–S38 · N · 3.9 FW). Agent runtime v2 as an additive path: gateway converse() with tools and structured output (the live call() path used by the screener and matcher is untouched), loop harness and tool registry (C17), run/step model and run_events, SSE transport with polling fallback, plans, questions, proposals and approval grants, engagement run workflow, persisted decision-relevant run records, agent-minute ledger. Schema lands by Dec 24, 2027, before the Jan 1 window; code merges dark. *Modules:* ai_gateway (red), agents (red), workbench (new), notifications (SSE). *Decisions:* ADR P-15 SSE; ADR P-22 agent model; ADR P-23 sessions; AG-01..AG-06, AG-15. *Journeys:* J11, J13, J22, J23.
- **P-11 · Document services: renderer, OCR & regions** (S17–S34 · N · 2.0 FW). Document services: deterministic PDF/DOCX renderer with templates held in the database (S17-S20, for letters and reports), then OCR and tax-form box extraction inside the AWS boundary (S28-S34, for notices, tax forms and bank statements). *Modules:* reporting (new), evidence (red). *Decisions:* ADR P-19 deterministic rendering; ADR P-32 OCR sub-processor. *Journeys:* J02, J03, J06, J09, J10.

#### K · Knowledge and configurable engine

- **K-01 · Knowledge library & methodology v1** (S10–S26 · AY · 1.4 FW). Knowledge catalog over the existing methodology and knowledge records; admin import of each firm's PBC templates and programs as database content; program editor with stable step anchors; methodology versions and import review. *Modules:* methodology (new), engagements. *Decisions:* content in the database, not commits. *Journeys:* J01, J03, J24.
- **K-02 · Firm standards, rules tables & content import** (S16–S19 · AY · 1.1 FW). Firm standards and thresholds (materiality ranges, review levels, AJE thresholds) plus an effective-dated rules-table service (TY due dates and holidays, the 8879 form set with Pub 1345 tolerances, 1099 thresholds, retention floors) edited through admin import, never commits. *Modules:* methodology, practice. *Decisions:* CMP-10 rules tables. *Journeys:* J01, J05, J06, J10.
- **K-03 · Templates v2 & Sheets engine** (S52–S60 · N · 4.4 FW). Templates v2 and the Sheets engine: re-pinning with gated in-place upgrades that never touch signed-off rows, resumable Temporal rollout, typed sheets with row sign-offs, column configurator, code-evaluated scoping rules, agent columns producing cited suggestions. D3 hybrid: no designed workpaper is converted. *Modules:* methodology, workpapers, agents. *Decisions:* ch.03 templates-v2 ADR (supersedes SPEC-008 pin-once); agent columns vs ADR-047 (AG-13). *Journeys:* J24, J22, J01, J26.
- **K-04 · Board, triggers, review package & set up with AI** (S59–S65 · N · 3.6 FW). Board as a view over program status (drops onto sign-off columns open SHL-12, never sign), engagement settings and triggers that only draft or propose, engagement dashboard, agent review package, same-client link requests, Set up with AI. *Modules:* engagements (protected agent workflow), agents, collaboration. *Decisions:* AG-12 triggers; ch.03 cross-engagement fulfilment ADR; Board naming (SPEC-022 board renamed Evidence board). *Journeys:* J22, J23, J25, J20, J04.
- **K-05 · Learning layer & content: skills, learned context, packs, notes** (S67–S72 · AY · 2.2 FW). Learning layer and content: skills with an 18/20 eval publish gate, learned context (capture, approve, reuse), content packs with fictional publishers only (D8), notes library. *Modules:* agents (memory), methodology. *Decisions:* AG-13; AG-14; D8 licence gating (ADR-056). *Journeys:* J24, J27, J21, J01.

#### A · Assurance and audit

- **A-01 · Audit evidence spine & binder export** (S7–S13 · N · 1.3 FW). Audit index and cockpit on work items (rail and Source Documents), PBC with viewer and screening, and the binder export package (ADR-036 manifest, fresh MFA) so the firm's own workpaper tool stays authoritative and every pilot can roll back. *Modules:* assurance (new), requests, evidence (red). *Decisions:* ADR-036 export manifest. *Journeys:* J03, J04, J20.
- **A-02 · Trial balance & ledger connections** (S8–S17 · N · 1.9 FW). Trial balance and leadsheets from the existing file imports (Unadjusted layer, ties), POR-16 client connections with 'Export instead', the integration framework v1 and write-capability registry skeleton (C20), then the first live ledger read connector chosen from discovery (ADR-045). *Modules:* ledger (red), connections (red), integrations (new, red). *Decisions:* ADR-045 first ledger; ADR P-17 firm-side integrations; ch.06 write-capability framework (registry only). *Journeys:* J02, J03, J04, J28.
- **A-03 · Sampling & TB mapping** (S20–S23 · AY · 1.0 FW). Seeded, versioned sampler compute library with golden tests (population from upload, fan-out to requests) and single-entity TB mapping with the grouping and FS-line taxonomy (C9), which also de-risks group audit. *Modules:* sampling, ledger (red). *Decisions:* ADR-050 code computes; Q-15 mappings and consolidation live in ledger. *Journeys:* J04, J03, J22, J20.
- **A-04 · Audit planning & risk (G4)** (S22–S28 · AY · 2.6 FW). Audit planning (G4): cited program workpaper, risk narrative, materiality decision computed in code (252,200 / 189,150 / 12,610 golden), RMM register and linkage, internal control and exceptions, SOC 1 reliance. Built for Dec-YE 2027 planning (Oct-Dec 2027). *Modules:* workpapers (new), review, methodology, assurance. *Decisions:* SPEC-008 non-goals superseded (materiality, risk); ADR-050. *Journeys:* J03, J04, J23.
- **A-05 · EBP plan audits** (S23–S31 · AY · 3.7 FW). EBP 401(k) plan audits in dependency order: plan profile, provisions with region citations, eligibility grid, contributions and remittance timeliness (one late_remittance object shared with AUD-27), then distributions/loans, participant accounts and admin expenses (EBP-05/08/09), then investments and trust tie-out after AUD-16 adjustment layers (with a TB-from-trust-report ADR), and finally the 5500 tie-out (EBP-07) after AUD-20. *Modules:* assurance (ebp), sampling, evidence (red), workpapers. *Decisions:* TB-from-trust-report ADR; census PII masking and logged reveal. *Journeys:* J03, J04, J18.
- **A-06 · Findings, adjustments, review notes & FS draft** (S24–S30 · N · 2.0 FW). Findings with the partner's severity decision, misstatements, AJEs and SUM (adjustments module, red, no posting; SUM compute library), review notes and the sign-off matrix (G5), and the FS draft with disclosure checklist (AUD-20) that EBP-07 needs. *Modules:* adjustments (new, red), review, assurance, reporting. *Decisions:* ADR P-07; no posting under ADR-040. *Journeys:* J03, J22, J04, J05.
- **A-07 · EQR, completion, letters, report, release & archive (G6-G9)** (S27–S36 · N · 3.4 FW). EQR (G6), completion checklist, representation letter (G7 via envelopes), governance letters, report builder, release transaction (G8) into the deliverables registry, assembly and archive (G9: 60-day clock, sealed manifest in Object Lock COMPLIANCE mode, DB immutability triggers, enumerated archived_write exception, packaged run records). Schema migrated before Dec 10, 2027; code merges dark; flipped per firm in a Tuesday window before Dec-YE 2027 reports. *Modules:* assurance (release/archive red paths), evidence (archive), reporting, signatures. *Decisions:* ch.03 archive-seal and hash-chain ADR; ADR P-14 retention; C-09/C-12/C-13. *Journeys:* J03, J04, J05, J18, J21.
- **A-08 · Audit fieldwork depth** (S45–S50 · AY · 2.3 FW). Testing workspace (details, controls, JE testing with a protected GL extension for posting user, timestamp and source), analytics, confirmations with a tokenised public respondent page (security-reviewed), and the SSARS review, compilation and preparation workspace. *Modules:* sampling, ledger (red), assurance, identity (public token). *Decisions:* public respondent access ADR; GL model extension approval. *Journeys:* J04, J05, J12.
- **A-09 · Group audit (SAS 149)** (S45–S50 · N · 2.3 FW). SAS 149 group audit: multi-entity engagements, consolidation in ledger with one connection serving many subsidiaries, upload-TB path and manual eliminations first, group scoping and component materiality decision, component auditors with a reduced portal room. Ready behind ff.group_audit for Dec-2028 year-ends. *Modules:* ledger (consolidation, red), assurance, portal. *Decisions:* Q-15; connection-index change; POR-23 external role; X-06 no fund semantics. *Journeys:* J20, J23.
- **A-10 · Statements studio** (S58–S64 · AY · 2.8 FW). Statements studio: statement_document with line items and lineage, tie-out engine, editor with tracked changes and presence (one editor at a time, no CRDT), disclosure assistant, report templates in the database. *Modules:* reporting, ledger. *Decisions:* editor-framework ADR; ADR P-19. *Journeys:* J21, J04.
- **A-11 · Agentic audit: procedure session & pre-review** (S65–S68 · N · 1.1 FW). Procedure session and pre-review: agentic audit procedures on runtime v2, Sheets and agent columns, every conclusion left to a named human. *Modules:* agents, workpapers, sampling. *Decisions:* AG-12; ADR-005 human-only. *Journeys:* J22, J23, J04.

#### X · Attest and internal audit

- **X-01 · Attest core (SOC 1/2, AUP, readiness) & frameworks** (S62–S69 · AY · 4.0 FW). Attest service line (D1): framework library with licence gating and fictional publishers (D8), control sets and cross-maps, attest cockpit, scoping, system description on the T20 editor, control matrix on Sheets, control testing, exceptions with the opinion decision, report and release, client SOC requests room. *Modules:* attest (new), methodology, workpapers, portal. *Decisions:* D1 engagement types soc/aup/readiness; ADR P-25 for client-facing description drafts; X-01/X-02/X-04/X-05 not shipped. *Journeys:* J25.
- **X-02 · Attest depth: ISO readiness & GRC sync** (S68–S72 · N · 1.0 FW). ISO 27001 (and CMMC L2 as a template, X-04) readiness and Drata GRC request sync under its own write-adapter ADR (W5). *Modules:* attest, integrations (W5, red), connections. *Decisions:* W5 GRC write ADR. *Journeys:* J25.
- **X-03 · Co-sourced internal audit** (S68–S73 · AY · 1.5 FW). Co-sourced internal audit (D2): IA plan, RCM and walkthroughs on Sheets, issues and action plans, committee pack, client IA room. BSA/AML only as an IA template (X-01b); no in-house workspace (X-08). *Modules:* attest (ia), workpapers, reporting. *Decisions:* D2; X-01b; X-08. *Journeys:* J26.

#### T · Tax

- **T-01 · Tax compliance rails: §7216 gate, CCH file bridge, e-file record** (S16–S21 · N · 3.9 FW). Tax compliance rails, red: TRI data class, gateway condition 6 fail-closed (no model call on TRI without both Sec. 7216 consents, both spouses), consent registry and capture, offshore SSN masking server-side, MFA for TRI scopes, logged TIN reveal; CCH Axcess file bridge (W2 file mode: export workbook, import diff to checkpoint, manual 'Mark transmitted', ack import); 8879 gate with Pub 1345 amount-hash re-lock (tolerances as DB rows); integration settings; 'never ERO or transmitter' enforced by tests. *Modules:* organisations (consents, red), integrations (W2, red), tax (red paths), ai_gateway. *Decisions:* ADR P-12 Sec. 7216 & TIN; ADR P-18 tax engine (file bridge); AG-16; R-04 never ERO/transmitter; C-01/C-03. *Journeys:* J06, J07, J08, J14, J28.
- **T-02 · Tax extension-season pilot kit** (S16–S21 · AY · 2.0 FW). Extension-season tax pilot kit (conditional on the M8 go/no-go, May 28, 2027): tax_return record and status machine, practice board, return overview, intake on binders (binder per return, duplicate-upload policy), organizer questions with templates imported as DB content, K-1 package and release gate (K-1 PDFs from CCH; release only after the signer's final approval), K-1 recipient room. *Modules:* tax (new), requests, portal. *Decisions:* computation-boundary ADR (CCH stays engine of record); BH-TAX-02 K-1 release gate. *Journeys:* J06, J07, J08, J13.
- **T-03 · TY2027 season readiness: organizer editor, extensions & rules tables** (S26–S29 · AY · 1.0 FW). TY2027 readiness for the tax-pilot firms: organizer (questionnaire) editor, extensions and estimates tracking, TY2027 rules tables loaded through admin import before the freeze cut. *Modules:* tax, requests, practice. *Decisions:* CMP-10. *Journeys:* J06, J09.
- **T-04 · Return workspace & individual returns** (S32–S39 · AY · 3.5 FW). Return workspace and individual returns, built dark in the 2028 busy season and live for the 2028 extension season: Prepare and Review presets with region lighting, issues, activity and checkpoints, assistant (consent-gated, Bedrock-cleared), NY worksheets, K-1 treatment resolver, residency. *Modules:* tax, evidence (box extraction), review, agents. *Decisions:* computation-boundary ADR; AG-16. *Journeys:* J06, J13, J19.
- **T-05 · Entity return workspace & K-1 engines (P0)** (S35–S44 · AY · 5.1 FW). Entity return workspace (P0) for the 2028 extension season: agent tab and workbook-run DAG (Temporal), TB to TTB with form-line mapping (C9) and AJE/TJE layers (C8), Schedule K, allocation (Sec. 706(d), waterfall back-solve), capital accounts, issues, preparer memo, cell-addressable workbook with a formula engine. Compute engines are pure functions with blueprint 9.8 golden tests and CPA review. *Modules:* tax, ledger (consumer), adjustments (consumer), workpapers (formula DAG). *Decisions:* ADR-052 exception for tax workbooks; CPA review of golden figures. *Journeys:* J08, J13, J15.
- **T-06 · Entity return depth, relationships & hand-offs (P1)** (S49–S55 · AY · 4.1 FW). Entity return depth (P1): fixed assets and MACRS, M-1/M-3/M-2, Sec. 752 basis, states and PTET (largest remainder), other entity workpapers (1120-S/1120/990), form preview with K-1s, relationships graph (CLI-03 needs a design board first, by S44), audited-TB hand-off to tax. *Modules:* tax, organisations (relationships), ledger. *Decisions:* form-renderer vs engine-PDF decision; CLI-03 design task. *Journeys:* J08, J15, J28, J05.
- **T-07 · Trusts & estates (1041 / 706 / 709)** (S44–S47 · AY · 1.6 FW). Trusts and estates: instrument reader with clause citations, DNI calc tree in code, beneficiaries and K-1s with the 65-day election, 706/709 workpapers. *Modules:* tax (fiduciary engine), evidence (OCR). *Decisions:* clause citation kind; ADR P-32. *Journeys:* J07, J19.
- **T-08 · Tax season & practice tools (TY2028)** (S50–S55 · AY · 2.4 FW). TY2028 season tools: season setup and roll-forward cohorts, deadlines calendar on the rules engine, two-year comparison, firm standards run, planning opportunities (consent-filtered), amendments and AARs. *Modules:* tax, engagements (seasons), practice. *Decisions:* R-03 Sec. 7216 filter on planning. *Journeys:* J06, J15, J16, J19.
- **T-09 · Advisory projects & research** (S66–S70 · AY · 1.4 FW). Advisory projects: proposals and scope builder (no invoices, P-27), project workspace with milestones and code-computed modelling, templates and research memos on the shared document-template engine. *Modules:* engagements (advisory_project), methodology, reporting. *Decisions:* ADR P-27 payments boundary. *Journeys:* J15, J08.

#### C · CAS and closes

- **C-01 · Close engine (read-only QBO)** (S44–S51 · AY · 3.9 FW). Read-only CAS close engine: close work items (12 per annual engagement), QBO live read with hourly sync (Intuit metering), close plan and intake, code-first run engine and review, bank reconciliation with statement OCR and regions, flux, client close requests. *Modules:* closes (new), connections (QBO, red), ledger, requests. *Decisions:* ADR-045 QBO first for CAS; close work-item model. *Journeys:* J10, J02, J16.
- **C-02 · Ledger posting, deliverables & hand-offs** (S49–S55 · N · 3.2 FW). Adjustments posting and hand-offs: threshold batches approved by a named human (policy principal stays off), QBO posting under the W1 write-adapter ADR (declared scope, idempotent, dry run, closing date, client-visible write log, hard-off for attest clients), FS package release, GL sync console, close-to-tax hand-off (C12), 1099/W-9 tracker with IRIS file export (never a transmitter). *Modules:* adjustments (red), integrations (W1, red), reporting, tax. *Decisions:* ADR P-16 / W1 posting; ADR P-08 policy principal (default off); ET 1.295 attest-client lock. *Journeys:* J10, J05.

#### N · Intake, delivery, notices, signatures, files

- **N-01 · Firm inbox, triage & files** (S13–S18 · N · 1.7 FW). Firm inbox from portal 'upload something else' and manual intake, triage to a request, supersede as version n+1, Files browser read-only with client-level files. *Modules:* communications, evidence (red), requests. *Decisions:* ch.03 client-scoped files ADR (Q-08). *Journeys:* J06, J09, J16.
- **N-02 · Signatures & engagement letters** (S13–S21 · N · 3.6 FW). Signatures module (red): record mode first (import the firm's existing evidence), then DocuSign embedded signing with provider-hosted ID Verification, Connect webhooks, the 5-item IRS evidence package (3-year floor, COMPLIANCE-mode storage), ERSD, handwritten fallback after 3 KBA failures (C-05); engagement-letter composer with clause library in the database (G3). W7 is the first write-capability entry. *Modules:* signatures (new, red), reporting, communications. *Decisions:* ADR P-26 e-signature (provider-hosted KBA); W7 DocuSign registry entry; C-05/C-06. *Journeys:* J02, J06, J03, J15, J16.
- **N-03 · Firm mailbox, compose & client messages** (S56–S62 · AY · 2.3 FW). Firm mailbox (Microsoft Graph docs@ ingest and send-as, W6), compose and reply, portal message threads, client account and delegation with TOTP, firm-wide request tracker with human-sent follow-ups. Model-drafted text reaches clients only under ADR P-25 conditions, off by default. *Modules:* communications, portal, identity. *Decisions:* W6 Graph send-as; ADR P-25 (amends ADR-111); ADR-030 client TOTP. *Journeys:* J12, J16, J10, J02.
- **N-04 · Notices** (S25–S29 · AY · 1.6 FW). Notices as the first year-round tax-adjacent module once the Sec. 7216 gate exists: intake by upload, inbox or portal with OCR extraction, code comparison against the return as filed, partner decision, response letter with provenance and signature, follow-up timer; payments as link-outs only. *Modules:* notices (new), tax, signatures, evidence. *Decisions:* ADR P-27; AG-16. *Journeys:* J09, J13.

#### R · Client portal

- **R-01 · Portal PBC core & white-label** (S7–S18 · AY · 1.6 FW). Portal PBC core: documents with ignore-with-reason and mark done, request sheet, request-scoped third-party room (TPAs, recordkeepers, banks), transactional email templates versioned in the database, branding slots and per-firm sender domain (custom domains later). *Modules:* portal, communications, evidence. *Decisions:* ADR P-11. *Journeys:* J12, J03, J15, J16.
- **R-02 · Portal approvals, deliverables & governance room** (S29–S35 · AY · 1.2 FW). Portal approvals (C18: FS packages, client AJE approval), deliverables registry with download audit (C10), governance room (TCWG answers private even from a member who is also management). *Modules:* portal, assurance, reporting. *Decisions:* C10/C18 contracts. *Journeys:* J04, J05, J10, J12.
- **R-03 · Portal mobile capture, payments link-outs & prospect intake** (S59–S63 · AY · 1.0 FW). Portal depth: mobile capture (input capture and server-side stitching first; QR hand-off auth ADR later), payments as link-outs only, prospect intake (security-reviewed public form). *Modules:* portal, evidence. *Decisions:* ADR P-27; QR hand-off auth ADR. *Journeys:* J12, J09, J19.

#### W · Workbench and Office

- **W-01 · Integration catalogue & Connect** (S45–S48 · N · 1.1 FW). Workbench Connect: data-driven integration catalogue (only built connectors show as Available), integration detail and connect drawer, firm and personal connection health on the C20 framework. *Modules:* integrations (red), connections. *Decisions:* ADR P-17. *Journeys:* J01, J14.
- **W-02 · Workbench sessions** (S40–S45 · N · 1.8 FW). Workbench sessions: grounded read-only answers first, then plan, execute and approve with proposed writes and artifacts. *Modules:* workbench, agents, ai_gateway. *Decisions:* ADR P-23; AG-04. *Journeys:* J11.
- **W-03 · Agent library, my agents, schedules & saved prompts** (S63–S69 · N · 1.8 FW). Agent library (28 templates as DB rows), agent details (WB-05 composed from the C-11 Details dialog plus T4f; design task S8-S12), my agents, edit agent, run history and Temporal schedules, saved prompts that never run, schedule or approve. *Modules:* workbench, agents. *Decisions:* ADR P-22 (firm agents are configuration over declared capabilities); AG-11; WB-05 design task. *Journeys:* J11, J01, J20.
- **W-04 · Office add-ins** (S69–S73 · AY · 1.4 FW). Office add-ins: Excel (evidence links, tickmarks, P/R sign-off, offline replay) and Word, with Office NAA/SSO. *Modules:* apps/office-addin (new), api. *Decisions:* ADR P-20. *Journeys:* J21, J22.

#### G · Governance, admin and platform console

- **G-01 · Firm settings, users, roles, offices & walls** (S6–S13 · N · 1.0 FW). Firm settings frame, firm profile, users and roles (role templates generated from the matrix), offices, teams, walls v2 and consent-gated offshore groups. *Modules:* identity (red), platform. *Decisions:* ADR P-10; Q-07 client_service role (ADR-024). *Journeys:* J01, J14, J16.
- **G-02 · AI policy, security center & audit log** (S9–S14 · N · 1.6 FW). AI policy v1 (autonomy, data-boundary opt-in TASK-076, kill switch; Auto mode per engagement type later), security center v1 (SSO/MFA enforcement, sessions, support access), audit-log explorer v1 with 'via Agent' attribution and dual-approval export. *Modules:* identity, ai_gateway, audit_trail (red). *Decisions:* SPEC-036 part 2 (TASK-076); ADR P-08 stays off; C-08 MFA. *Journeys:* J01, J14, J03, J06.
- **G-03 · Developer platform & data model** (S69–S73 · N · 1.9 FW). Developer platform: API keys, webhooks from the outbox through an SSRF-safe egress proxy (W8), read-only MCP with Sec. 7216 withholding; data model settings (custom fields, tags, TB labels). *Modules:* identity, integrations, platform. *Decisions:* ADR P-21; W8 webhooks. *Journeys:* J14, J11, J01, J20.
- **G-04 · Platform console, plan & usage, support panel** (S47–S51 · N · 1.1 FW). Tenant console replacing CLI provisioning, plan and usage with agent-minute metering (no billing), support panel and status page. *Modules:* platform, ai_gateway (metering), identity (support). *Decisions:* ADR P-28; SPEC-012 amendment (no emergency second-staff approval). *Journeys:* J01, J14, J27.

#### I · Home and insights

- **I-01 · Home & approvals queue** (S10–S35 · AY · 1.4 FW). Home and the 'Waiting on you' queue on the cross-module human-gate projection (C13), so counts such as 11 = 3 + 6 + 2 match everywhere. HOME-01 lite for the MVP; HOME-02 once the review grammar UI lands. *Modules:* practice (home read model), review, notifications. *Decisions:* C13 registration slot. *Journeys:* J13, J16, J19.
- **I-02 · Today brief** (S40–S43 · N · 1.0 FW). Today brief per engagement: counts from code, narrative from a registered prompt with verified citations. *Modules:* agents, practice. *Decisions:* AG-01. *Journeys:* J13, J23, J20.
- **I-03 · Insights** (S61–S67 · AY · 2.2 FW). Insights read models: performance, AI adoption and override monitoring (8% tolerance, shared with ADM-11), efficiency with firm-history comparisons only (D6), My week time suggestions pushed to practice management (D5, W4), client responsiveness. *Modules:* practice (insights), integrations (W4). *Decisions:* D5; D6 (P-30 deferred); ADR-024 counts only. *Journeys:* J27, J17.
- **I-04 · Practice economics & capacity** (S70–S73 · AY · 1.5 FW). Practice economics: budget, time and AI effort; billing and WIP read-through from CCH Axcess Practice (no invoices); capacity planner. *Modules:* practice, integrations. *Decisions:* ADR P-27; D5 integrate-first. *Journeys:* J17.

#### Q · Quality, operations, compliance and infrastructure

- **Q-01 · Infrastructure, environments & platform services** (S0–S5 · N · 3.6 FW). Infrastructure and platform services (TASK-014): AWS landing zone and accounts, Terraform staging and production, ECS Fargate, RDS with forced-RLS roles, S3 Object Lock buckets, per-tenant KMS keys, Temporal Cloud, WorkOS, SES with per-firm DKIM, ClamAV scanning, CloudFront and WAF, observability and SLOs, backups/PITR and restore drills, runbooks and kill switches, tenant provisioning workflow, build-once-promote with the release-manifest PR. R0 staging Nov 13; R1 production with canary Dec 11, 2026. 20 tasks reserve-funded. *Modules:* infra (new), kernel, identity, communications, evidence (scanner). *Decisions:* ch.06 region, tenant-key, malware-scanning, kill-switch and observability ADRs; ADR-088 build-once-promote. *Journeys:* all.
- **Q-02 · Real-data readiness & compliance programme** (S0–S13 · N · 2.9 FW). Real-data readiness: compliance kernel (TRI/PHI tags, access_events, ADR-007 hash chain, actor kinds human / via Agent / policy / system), retention floors, legal holds and dual-approval export, incident register with the FTC clock, MFA enforcement, Bedrock provider-terms entry with counsel as second approver, route parity, per-agent Bedrock evals (screener, upload reviewer, matcher), TASK-076 opt-in with shadow and live stages, security test suite, SOC 2 controls operating from Dec 11, Type I as of Mar 1, pen test Feb 15-Mar 5 with highs closed by Apr 9, WISP, vendor-diligence pack. *Modules:* ai_gateway, agents, identity, kernel, audit_trail, evidence. *Decisions:* ADR-113/114/115 register; C-08 MFA; C-09 Object Lock; C-12 run records; C-13 hash chain. *Journeys:* all real-data journeys.
- **Q-03 · Hardening & test back-fill (reserve-funded)** (S6–S73 · N + AY · 47 (reserve)). Reserve-funded hardening and continuous assurance (22.5% of capacity): ADR-078 independent AC tests back-filled for the 55 deferred tasks (identity/authz, evidence, connections/ledger, agents first) before real data, mutation testing on red modules, load tests, quarterly restore drills, pen-test remediation and delta retests before each new real-data surface (Jun 2027 client-facing, Aug 2027 TRI and signing, Nov 2027 annual, then before W1 posting and W6 send-as), SOC 2 Type II, conflict resolution and contract-test upkeep. *Modules:* all red modules, .github. *Decisions:* ADR-078 separate test author; ADR-086 earned auto-merge. *Journeys:* all.
- **Q-04 · Pilot operations, release train & freeze contract** (S12–S74 · N + AY · 0.6 + 30 (support)). Pilot operations and the freeze contract: onboarding kit (bulk import, PBC templates, organizers and email templates as DB content), per-firm entitlements and flags, go-live checklists, P-29 in-season rules, flag renewal calendar, weekly production promotion, named on-call per live window, support at 25-30% in season, pilot metrics, retros and the rollback path (binder export; the firm's tool stays authoritative until system-of-record criteria are met). *Modules:* platform, audit_trail (metrics), ops runbooks. *Decisions:* ADR P-29 busy-season policy; ADR-089 flag renewal. *Journeys:* all live journeys.
- **Q-05 · Quality management & records governance** (S50–S54 · AY · 1.6 FW). Quality management and records governance: consultations log, post-issuance and subsequent discovery, QM dashboard and monitoring/inspections for the Dec 15, 2028 SQMS 1 evaluation, retention and legal hold UI, destruction batches with dual approval, crypto-shred and certificate. *Modules:* practice (quality), evidence (holds, destruction, red), audit_trail. *Decisions:* ADR P-14 (supersedes ADR-034 for destruction); C-10 legal-hold roles. *Journeys:* J14, J18, J01.
---

## 1.5 Milestone calendar

| M | Date | Deliverables | Journeys unlocked |
|---|---|---|---|
| **M0** | Fri Oct 23, 2026 | Decision Day: the §1.9 agenda recorded in chapter 09's register | — |
| **M1** | Fri Oct 30, 2026 | S0 exit: repo private after the history secret scan; ruleset and hook fix; CI green; every long-lead application filed | — |
| **M2** | Fri Nov 13, 2026 | **R0 staging**: Terraform staging, WorkOS, SES and ClamAV live; work-item and request-enum migrations; C1 and C2 frozen | — |
| **M3** | Fri Nov 20, 2026 | ≥2 LOIs and named targets per window; first live ledger chosen (ADR-045); group-audit record; calibration #1 | — |
| **M4** | Fri Dec 11, 2026 | **R1 production** with canary; SOC 2 controls operating; first restore drill; Dec 14–18 protected bundle (9 flag renewals, P-29 accepted); SQMS 1 Technology Resource Pack sent to prospects by Dec 15 | — |
| **M5** | Fri Jan 22, 2027 | Platform spine on staging: DS tiers 0–1, shell and sign-in, clients and engagements, binders and requests, portal sign-in and documents; Pilot 0 sessions running since Jan 11 | J02-audit-core and J12-core skeletons (staging) |
| **M6** | Fri Mar 5, 2027 | Pen test #1 complete; SOC 2 Type I as-of date Mar 1; audit cockpit, PBC, viewer and TB import on staging | J04 PBC slice (staging) |
| **M7** | Fri Apr 16, 2027 | **Real-data gate (R2)** passed | — |
| **M8** | Fri May 28, 2027 | MVP-1 code-complete; tax-pilot go/no-go; calibration #3 | **J01-core, J02-audit-core, J04-PBC slice, J12-core walkable in production** |
| **M9** | Tue Jun 1, 2027 | First firm in internal shadow (real data, agents in shadow stage, nothing client-facing) | The M8 set, live internally at 1–3 firms |
| **M10** | Tue Jul 13, 2027 | **Client-facing audit pilot (R3)**: portal invites, firm sender domain, screener, upload reviewer and matcher in live stage | J02-audit-core, J12-core and J04-PBC **live** |
| **M11** | Tue Aug 17, 2027 | Tax pilot live, coordination layer (if GO at M8) | J06 coordination slice (organizer → documents → CCH export record) |
| **M12** | Fri Aug 20, 2027 | Paid-conversion and hiring gate | — |
| **M13** | Tue Aug 31, 2027 | 8879 signing with provider KBA, delivery and e-file record, K-1 release; Sep 1 window opens | J06 record-mode spine through "Mark transmitted" and delivery; J08 K-1 distribution slice; J12 signing |
| **M14** | Fri Oct 15, 2027 | Extension season closes; SOC 2 Type II report in hand; re-baseline #4 | — |
| **M15** | Fri Dec 10, 2027 | **Season-ready 2028 (R4)**: notices live; EBP P0 modules (EBP-07 by Jan 7) and planning in production; TY2027 rules and organizers loaded; pen test #2 closed; completion, release, archive and runtime schemas migrated by Dec 24 | **J09 P0 live**; J03 fieldwork P0 (EBP-01…06, then EBP-07); J04 planning slice |
| **M16** | Tue Mar 21, 2028 | Release and archive flipped per firm; first report released (G8) and archived (G9) on Accrued by Apr 14 | **J03 P0** (Mar 17), J12 P0 (Mar 3), J18 P0 (Mar 17), J27 P0 (Mar 31) |
| **M17** | Tue May 2, 2028 | 2028 extension-season release: 1040 review workspace, runtime v2 for cleared agents, Today brief (Jun) | **J06 P0**, J19 P0 |
| **M18** | Tue Aug 1 and Tue Aug 22, 2028 | 1065 entity workspace live; 1041 live | **J08 P0**, J15 P0, **J07** |
| **M19** | Fri Sep 29, 2028 | Group audit behind `ff.group_audit`; fieldwork depth live; integrations catalogue and tenant console | **J20 P0**, J14 P0 (Sep 1), J04 core, J05 core |
| **M20** | Tue Oct 31, 2028 | CAS live on October closes (read-only) | **J10 read-only path**, J02 P0, J16 P0 |
| **M21** | Fri Dec 8, 2028 | Season-ready 2029: W1 posting (non-attest), TY2028 season tools, entity depth, QM for the Dec 15 SQMS evaluation | J05, J06 full, J10 P0, J18 full, J28 full |
| **M22** | Fri Apr 27, 2029 | Engine core (templates v2, Sheets, Board, triggers, review package); statements studio; mailbox and portal depth | J13; J21 P0; engine-based P0 paths of J04, J22, J23, J24, J25, J26; J02, J10, J12, J16, J19 full |
| **M23** | Fri Aug 17, 2029 | Attest, internal audit, agentic audit, agent library, insights, learning layer, add-ins, developer platform, practice economics | **All 28 journeys walkable in production** |
| **M24** | Fri Aug 31, 2029 | GA | — |

### 1.5.1 When each journey becomes walkable

The dates below come from the epic windows in §1.4. Each journey's screens are parsed from its step tables in the journeys digest, and templates are excluded. *P0 core* uses only the journey's P0 screens. *Full* includes P1, P2 and amendment screens.

For J25 and J26, the service-line screens are P1 or P2, so their "P0 core" date only reflects the shared Board. The attest and internal-audit paths land with **X-01** (Jun 22, 2029) and **X-03** (Aug 17, 2029). For J28, the meaningful hand-off (AUD-38) is P1 and lands Dec 8, 2028.

| J | Journey | P0 core walkable | Gated by | Full journey walkable | Last to land |
|---|---|---|---|---|---|
| J01 | Firm onboarding + methodology upload | S69 · Jun 22, 2029 | WB-07 (W-03) | S73 · Aug 17, 2029 | ADM-13 (G-03) |
| J02 | Client onboarding + portal invite | S51 · Oct 13, 2028 | CLS-09 (C-01) | S65 · Apr 27, 2029 | ENG-14 (K-04) |
| J03 | EBP 401(k) audit | S36 · Mar 17, 2028 | AUD-25 (A-07) | S37 · Mar 31, 2028 | AUD-29 (P-05) |
| J04 | General FS audit | S65 · Apr 27, 2029 | ENG-10 (K-04) | S68 · Jun 8, 2029 | AUD-36 (A-11) |
| J05 | Review, compilation, preparation | S55 · Dec 8, 2028 | CLS-08 (C-02) | S55 · Dec 8, 2028 | TXP-13 (T-06) |
| J06 | Individual 1040 season | S39 · Apr 28, 2028 | TXI-01 (T-04) | S55 · Dec 8, 2028 | TAX-10 (T-08) |
| J07 | Trust 1041 | S47 · Aug 18, 2028 | TXT-02 (T-07) | S47 · Aug 18, 2028 | TXT-03 (T-07) |
| J08 | Partnership 1065 | S44 · Jul 7, 2028 | TXP-11 (T-05) | S70 · Jul 6, 2029 | PRJ-01 (T-09) |
| J09 | IRS notice response | S29 · Dec 10, 2027 | NOT-03 (N-04) | S63 · Mar 30, 2029 | POR-19 (R-03) |
| J10 | CAS month-end close | S55 · Dec 8, 2028 | CLS-08 (C-02) | S62 · Mar 16, 2029 | INB-04 (N-03) |
| J11 | Workbench: ad-hoc → saved agent → scheduled run | S69 · Jun 22, 2029 | WB-08 (W-03) | S73 · Aug 17, 2029 | ADM-09 (G-03) |
| J12 | Client-side: respond, upload, sign, message | S35 · Mar 3, 2028 | POR-09 (R-02) | S63 · Mar 30, 2029 | POR-19 (R-03) |
| J13 | Partner review and sign-off | S65 · Apr 27, 2029 | SHL-19 (K-04) | S65 · Apr 27, 2029 | SHL-19 (K-04) |
| J14 | Firm admin and integrations | S48 · Sep 1, 2028 | WB-11 (W-01) | S73 · Aug 17, 2029 | ADM-09 (G-03) |
| J15 | Advisory project | S44 · Jul 7, 2028 | TXP-01 (T-05) | S70 · Jul 6, 2029 | PRJ-01 (T-09) |
| J16 | Daily practice operations | S51 · Oct 13, 2028 | CLS-01 (C-01) | S62 · Mar 16, 2029 | INB-03 (N-03) |
| J17 | Practice economics | S35 · Mar 3, 2028 | HOME-01 (I-01) | S73 · Aug 17, 2029 | HOME-04 (I-04) |
| J18 | Audit quality management | S36 · Mar 17, 2028 | AUD-25 (A-07) | S54 · Nov 24, 2028 | AUD-30 (Q-05) |
| J19 | Estate and amended returns | S39 · Apr 28, 2028 | TAX-07 (T-04) | S63 · Mar 30, 2029 | POR-18 (R-03) |
| J20 | Group audit (SAS 149) | S50 · Sep 29, 2028 | POR-23 (A-09) | S73 · Aug 17, 2029 | ADM-13 (G-03) |
| J21 | Statements studio | S64 · Apr 13, 2029 | FSP-03 (A-10) | S73 · Aug 17, 2029 | XLA-02 (W-04) |
| J22 | Search for unrecorded liabilities on the Board | S65 · Apr 27, 2029 | SHL-19 (K-04) | S73 · Aug 17, 2029 | XLA-01 (W-04) |
| J23 | Audit partner's morning | S65 · Apr 27, 2029 | ENG-10 (K-04) | S68 · Jun 8, 2029 | AUD-37 (A-11) |
| J24 | Methodology template rollout | S65 · Apr 27, 2029 | ENG-11 (K-04) | S72 · Aug 3, 2029 | KNW-11 (K-05) |
| J25 | SOC 2 Type 2 examination | S65 · Apr 27, 2029 | ENG-10 (K-04) | S72 · Aug 3, 2029 | ATT-09 (X-02) |
| J26 | Co-sourced internal audit | S65 · Apr 27, 2029 | ENG-10 (K-04) | S73 · Aug 17, 2029 | POR-22 (X-03) |
| J27 | Managing partner's insights review | S37 · Mar 31, 2028 | SHL-17 (P-05) | S72 · Aug 3, 2029 | WB-13 (K-05) |
| J28 | Audit to tax | S21 · Aug 20, 2027 | TAX-09 (T-01) | S55 · Dec 8, 2028 | TXP-13 (T-06) |

---

## 1.6 MVP and the design-partner pilot plan

### 1.6.1 MVP-1: the audit-evidence pilot kit

Internal shadow from Jun 1, 2027; client-facing from Jul 13, 2027. It has **45 product screens (33 P0, 12 P1)** plus the 21 design-system boards of **F-05**.

| Area | Screens | Epic |
|---|---|---|
| Shell and trust | SHL-01, SHL-03, SHL-04, SHL-06, SHL-07, SHL-08, SHL-10 | P-01, P-03, P-04 |
| Requests and screening | BND-01, BND-02, SHL-14, SHL-20 | P-06 |
| Clients and engagements | CLI-01, CLI-02, CLI-04, CLI-06 (bulk import), CLI-07, CLI-08 (record-first), ENG-01, ENG-02, ENG-03, ENG-05, ENG-13 | P-07 |
| Audit | AUD-01, AUD-02, AUD-03, AUD-06, POR-16 (import and "Export instead", then the first live ledger read) | A-01, A-02 |
| Portal | POR-01, POR-02, POR-03, POR-04, POR-14, POR-20, ADM-10 | P-08, R-01 |
| Inbox and files | INB-01, INB-02, FIL-01 (read-only) | N-01 |
| Settings, security, AI policy | ADM-01, ADM-02, ADM-03, ADM-04, ADM-06, ADM-07 | G-01, G-02 |
| Knowledge and home | KNW-01 (with PBC-template import), HOME-01 (lite) | K-01, I-01 |

**What MVP-1 does *not* do:**
- It does not write to client systems.
- It sends no model-written text to clients; follow-ups are template-based and sent by a person.
- It does not e-sign; letters are recorded, with DocuSign arriving in **N-02** by Jul 2027.
- It touches no tax return information.
- It lets no agent take a final verb.

The binder export package keeps the firm's own workpaper tool authoritative, so any pilot can roll back on the day.

### 1.6.2 The tax extension pilot kit (conditional on M8)

It has **17 screens (13 P0, 4 P1)** plus T16, TPL-16, TPL-01 and TPL-19 from **F-06**.

| Area | Screens | Epic |
|---|---|---|
| Return record | TAX-01, TAX-02, TAX-03 | T-02 |
| Organizer and K-1s | POR-05 (questions, with templates imported as database content), TXP-12 (K-1 package and release gate), POR-13 (K-1 recipients) | T-02 |
| Compliance rails | CLI-05 and ADM-05 (§7216 consents, both spouses), ADM-08, TAX-09 (CCH file bridge, manual "Mark transmitted"), TAX-12 (delivery, e-file record, 8879 gate) | T-01 |
| Signing | SIG-01, SIG-02, POR-06, ENG-04 (DocuSign embedded with provider-hosted ID Verification; handwritten fallback after 3 failures) | N-02 |
| Rules and review | KNW-04 and the rules tables (due dates, 8879 tolerances), SHL-16 (checkpoint diff for the import diff) | K-02, P-04 |

**Tax posture.**
- CCH Axcess stays the engine of record. Accrued never transmits and never acts as ERO; a test enforces this.
- No model call touches TRI without both §7216 consents, so tax agents stay **off** in the pilot unless a taxpayer has consented and the agent has cleared.
- MFA is mandatory for TRI scopes, and TIN reveals are logged.
- Before go-live: counsel approves the consent text, which names AWS Bedrock; the CCH format is validated on the partner's own Axcess in Pilot 0; the C-05 handwritten fallback and the Pub 1345 amount-drift re-lock are tested.

### 1.6.3 Pilot windows: shadow first, then live

Pilot windows are labelled PW0–PW5 and PWT, so that they cannot be confused with the write classes W1–W9.

| Window | Dates | Mode | Scope | Entry | Exit and success |
|---|---|---|---|---|---|
| **PW0 · Pilot 0** | Jan 11 – May 28, 2027 | Synthetic, on staging | Biweekly 60-minute sessions per partner on the Brightwater Hale tenant with the demo clock, plus each firm's own non-confidential PBC template imported through KNW-01. Order: J02 and J12 in January; J04-PBC in February and March; the tax coordination slice in April and May. Validate the CCH Axcess import/export format with the tax partner's CCH admin on synthetic returns | M5 | Top-10 usability issues fixed before M9; CCH format signed off; ledger choice confirmed; letter, consent and DocuSign templates approved by counsel |
| **PW1 · Internal shadow** | Jun 1 – Jul 12, 2027 | Real data, staff only | 1–3 engagements per audit partner (EBP plans with Oct-15 filings, June-30 year-ends). Staff load the firm's PBC list, file documents received through existing channels, and use screening and matching. Agents in *shadow* stage, scored against human decisions. The firm's tools remain the system of record | M7, M9 checklist | ≥2 engagements; no open SEV1/2; champion confirms |
| **PW2 · Client-facing audit** | Jul 13 – Oct 15, 2027 (live paths frozen Sep 1 – Oct 20) | Live | Portal invites to real clients and to third parties (TPAs, recordkeepers, banks); Accrued is the PBC and evidence system of record per engagement. Sign-offs and planning roll out from Sep; reports are issued from the firm's tool through the binder export until **A-07** lands | M10 | ≥70% of PBC items delivered through the portal; ≥80% portal activation; median request → accepted beats the firm's baseline; zero wall or scope leaks (INV-3/4); zero final-verb violations (INV-1); screener override rate within the 8% tolerance on Bedrock |
| **PWT · Tax extension pilot** | Shadow Jul 27 – Aug 13; live Aug 17 – Oct 15, 2027 | Live, capped | 5–15 extended 1065 and 1040 returns per tax partner: invites, organizer, documents, return tracking, CCH export record, 8879 (from Aug 31), delivery, K-1 release to partners | M8 GO, M11, M13 | Every return reconciles to CCH; median 8879 sent → signed under 48 h; KBA fallbacks handled in product; zero INV violations; partner sign-off |
| **PW3 · Season 2** | Jan 1 – Apr 20, 2028 (freeze) | Live | Dec-YE 2027 audits from planning to release on Accrued, with release and archive flipped per firm on Mar 21; TY2027 returns on the coordination kit; notices | M15 | First report released and archived on Accrued; ≥70% of source documents via portal for tax-pilot households; zero SEV1 data incidents |
| **PW4 · Extension season 2028, EBP 2028, CAS** | Apr 18 – Oct 15, 2028, then monthly closes | Shadow 2–6 weeks before each flip, then live | 1040 review workspace (May 2), 1065 (Aug 1), 1041 (Aug 22); EBP and June-YE audits with full workpapers; CAS shadow on the September close, live on the October close | M17–M20 | Conversion of all design partners to paid plans; 8–12 firms contracted for the 2029 season |
| **PW5 · Season 3** | Jan – Apr 2029 | Live | Dec-2028 YE audits including group audits behind `ff.group_audit`; full tax; CAS posting (non-attest) | M21 | GA readiness |

### 1.6.4 Design partners

**Design partners are the critical path, and none is signed today.**

| Window | Target | Profile |
|---|---|---|
| Audit / EBP (PW1–PW2) | 2–3 firms | US CPA firms with 20–150 people and a private-company A&A practice; at least one with calendar-year 401(k) plan audits; at least one with June-30 year-end clients |
| Extension-season tax (PWT) | 1–2 firms (may overlap) | On CCH Axcess Tax, with 5–15 extended 1065 and 1040 returns and a CCH admin willing to join Pilot 0 |
| CAS (PW4) | 1 firm (discovery now) | QuickBooks Online–centric monthly closes |

**Timeline:**
- **Oct 19 – Nov 20:** AY runs outreach to ≥6 firms and builds a named target list per window; ≥2 LOIs by M3.
- **December:** discovery interviews (ledger, tax-engine and e-sign distribution) recorded in `docs/product/discovery/`; ADR-045 is settled from that data.
- **Fallback** if LOIs slip: prior-year replay of anonymised PBC lists and synthetic-only previews, while Pilot 0 continues and PW1 slides to Jun 15.

**Founding-partner agreement, dated and priced.** It names:
- the shadow period;
- the SOC 2 status (Type I report, with the Type II window May–Jul 2027);
- the support SLA: first response within 2 business hours in season, SEV1 24×7;
- a named partner champion and the success metrics in §1.6.3;
- the exit terms: data return and deletion;
- the DPA, plus a BAA where plan PHI is possible.

It is free through Pilot 0 and internal shadow, then priced at the founding price from the first client-facing month, with the right to cancel in the first 60 days of client-facing use.

### 1.6.5 Support model and rollback

**Who does what.**
- AY is the partner-facing owner: shared inbox, Tuesday and Thursday office hours, weekly feedback.
- N holds SEV1/2 on-call with runbooks; each live window names a backup.
- Support capacity is reserved: 10% in shadow, 15–25% in live months, 25–30% in deadline and busy-season months.

**Every SEV1/2** goes into the escaped-defect log with a written postmortem.

**Rollback.**
- Turn the firm's flag off.
- The binder export package returns the evidence to the firm's tool.
- The firm's existing tools stay authoritative until each engagement meets the system-of-record criteria.

### 1.6.6 AI value in the first pilot

**Readiness at the real-data gate.** Before Apr 16, 2027 the screener, upload reviewer and matcher must each have:
- the Bedrock route;
- a current register entry;
- passing per-agent evals, including the first committed real-model pass for the screener.

**Before any agent runs on a firm's data**, that firm's opt-in (TASK-076) is recorded. This applies to shadow-stage runs too.

**Stages.**
- **Jun 1:** shadow stage, scored against human decisions.
- **Jul 13:** live stage for cleared agents. Firm staff see cited screening flags, match proposals and upload-review findings, and accept them through SHL-10.

**ADR-111 still holds:** no model text reaches a client, and follow-up drafts stay template-based and are sent by a person.

### 1.6.7 Commercial model

**Packaging hypothesis**, to test in discovery and decide at M4 (proposed DEC-100):
- A per-firm platform subscription: white-label portal with unlimited client users, SSO, audit log, Accrued Agent.
- Per-seat pricing for firm staff by service-line bundle (Assurance, Tax, CAS; attest and internal audit as later add-ons).
- An included agent-minute pool per seat, with metered overage (ADR P-28). Agent time is never billed to clients.
- Accrued never takes payments or creates invoices (ADR P-27).

**Starting price ranges** (hypotheses, not decisions): platform fee $500–1,000 a month; Assurance seat $120–180 a month; Tax or CAS seat $60–100 a month. The founding-partner price is 50% of list for 24 months, price-locked, in exchange for references and feedback.

**Conversion and hiring (M12, Fri Aug 20, 2027).**
- If ≥2 of 3 design partners sign paid season-2 agreements (Dec-2027 YE audits and/or TY2027 returns), open two engineering hires.
- Hire a backend engineer first, to take amber and red-adjacent work off N, then a frontend engineer on the kits.
- Start about Oct 4, 2027, with a 6-week ramp, at about 0.55 founder-equivalents each.
- **Effect:** feature-complete moves from Aug 2029 to about **Dec 2028**; CAS moves to about May 2028 and group audit to June-2028 year-ends.
- If fewer than 2 sign, stay at two founders and apply the spill list (§1.8.6).

**Year-one external spend envelope** (Oct 2026 – Oct 2027; inferred, verify every quote). The AWS budget is decided on Decision Day (DEC-03), unblocking TASK-014.

| Item | Estimate |
|---|---|
| AWS staging and production, pre-scale (chapter 06 §1.18) | $20k–34k |
| Temporal Cloud, WorkOS, Sentry, Better Stack | $4k–11k |
| GitHub Team, Secret Protection, Code Security, Actions | $3k–6k |
| Compliance tool, SOC 2 Type I and Type II, pen test #1, cyber and tech E&O insurance (chapter 06) | $45k–90k |
| Pen-test deltas #1–#2 and pen test #2 | $20k–45k |
| Counsel: MSA/DPA, §7216, Pub 1345 and KBA, offshore question, state privacy | $25k–60k |
| DocuSign embedded and ID Verification (platform plus per-check fees) | $5k–15k |
| Domains, misc. | $1k–3k |
| **Total** | **≈ $125k–265k** |

---

## 1.7 Deferred and excluded

**No catalogue screen is excluded.** All 303 rows are in epics. The binding decisions constrain states, data and copy, and are enforced in code by **F-02** (13-item nav test, persona banned-terms lint, the Single Audit card fixed at "Coming soon", a data test that no excluded framework, engagement type or seed row exists).

### 1.7.1 Out of scope (binding)

| Item | Decision | Enforcement |
|---|---|---|
| Governmental audit: Yellow Book, Single Audit, fund accounting | **D10, deferred 16 Oct 2026.** ENG-03's Single audit card stays "Coming soon"; no SEFA, compliance supplement, SF-SAC or fund TBs | No `single_audit` or `yellow_book` enums, tables or seed; consolidation (**A-09**) must not grow fund semantics (exclusion X-06) |
| FFIEC, NYDFS and OFAC exam programs | Exclusion X-01 | No frameworks in KNW-09 or seed. BSA/AML runs only as an IA **template** (X-01b) on IAU-01…04 in **X-03** |
| ESG assurance | Exclusion X-02 | No ESG framework, template or seed |
| Forensics and litigation | Exclusion X-03 | No matters, chain of custody or expert reports |
| FedRAMP, CUI, eMASS | Exclusion X-04 | CMMC L2 only as a readiness template on ATT-08 (**X-02**) |
| AIUC-1 | Exclusion X-05 | No framework row |
| PCAOB issuer audits | Exclusion X-07 | Standards sets stay "GAAS nonissuer"; no ICFR integrated audit, CAMs or Form AP |
| Corporate in-house workspace | Exclusion X-08, D2 | No company-tenant model; IA is firm-delivered only |
| A 14th nav item, named agent personas, licensed publisher text | D4, D7, D8 | Nav test; banned-terms lint ("<person> via Agent" only); fictional publishers in KNW-08 and KNW-09 |
| Peer benchmarks | D6; ADR P-30 deferred | INS-02 and INS-03 ship only in their off and opt-in-disclosure states; no cross-tenant read |
| Time or billing system of record, payments, invoices | D5; ADR P-27 | INS-04 pushes suggestions to practice management; POR-10 is link-outs; ENG-08 is read-through |
| E-file transmission and IRIS 1099 transmission | Requirement R-04 | Never an ERO or transmitter. TAX-12 records "Mark transmitted"; CLS-13 exports a file; enforced by tests |

### 1.7.2 Deferred capabilities

| Capability | Lands | Why |
|---|---|---|
| Group audit for Dec-2026 and Dec-2027 year-ends | Dec-2028 year-ends (**A-09**, flag on Sep 29, 2028); Dec-2027 only as the M8 alternative to the tax pilot | AUD-31…35 need the review-grammar UI, materiality, consolidation in ledger, multi-entity engagements, the connection-index change and the POR-23 role, not Sheets. Those land Sep–Dec 2027 at plan velocity. Fallback: upload TBs, manual eliminations and component rooms on POR-14 |
| CAS ledger posting (W1) | Dec 2028 (**C-02**), non-attest clients only | ADR-040 is superseded only in part by the write-capability framework; it needs Intuit production keys, consent copy v2 and the ET 1.295 lock |
| CCH Axcess Tax API | Only if Wolters Kluwer grants access; the file bridge carries 2027–2029 | No public API; partnership timing unknown; the same sync-chip states make the swap invisible |
| Native KBA signing ceremony | Not planned (counsel may reopen) | Provider-hosted ID Verification carries less Pub 1345 burden (conflict C-06); the SIG-01 lockout copy is fixed to the handwritten fallback (conflict C-05) |
| Model-drafted text to clients | ADR P-25 accepted on Decision Day, **off** per firm until each drafter's evals pass (**N-03**, 2029) | ADR-111 and professional-liability exposure |
| Policy principal (threshold auto-acceptance) | Actor kind exists but is dormant; named-human batch approval ships instead (**C-02**) | ADR-005 and the human-only DB CHECK |
| Real-time co-editing (CRDT), WebSockets | Never in v1: SSE (ADR P-15) plus polling, one editor at a time with presence | `identity/routing.py` refuses WebSockets |
| Workbench agents, schedules, firm-built agents | **W-03**, 2029 | ADR-047/063 conflicts resolved by ADR P-22; WB-05 is designed in S8–S12 |
| Configurable engine (templates v2, Sheets, Board, triggers) | **K-03**, **K-04**, Oct 2028 – Apr 2029 | D3: designed audit, tax and close workpapers never need it; it is a prerequisite only for attest, IA and the engine-based journeys |
| Statements studio, Office add-ins | **A-10** (Q1 2029), **W-04** (Jun–Aug 2029) | XL editor with an editor-framework ADR; Office auth ADR |
| Insights, learned context, skills, content packs | **I-03**, **K-05** (2029) | Meaningless without months of real events; ADR-068 vs WB-13 conflict |
| Developer API, webhooks, MCP; tenant console | **G-03** (2029); **G-04** (Aug–Oct 2028) | A new principal model and egress proxy (ADR P-21, W8); CLI provisioning is enough for pilot scale |
| SQMS 1 screens for the Dec 15, 2026 evaluation | A Technology Resource Pack document by Dec 15, 2026 (**F-09**); ADM-11 and ADM-12 for the Dec 15, 2028 cycle (**Q-05**) | Cannot make 2026 |
| Second and third ledgers, unified accounting API | 2028+ under **A-02** and **W-01** extensions | ADR-045: one live ledger first, chosen from discovery, then a second before freezing the connector contract |
| Custom portal domains, SCIM, client TOTP, advanced mobile capture | 2028–2029 (**R-01** follow-ons, **N-03**, **R-03**) | The MVP portal uses branding slots and email code, with MFA enforced for owners and signers |
| Dark mode, firm-app mobile layout, Storybook, MSW, pdf.js, AG Grid, Yjs | Never | Out of design scope (D-DS-9/10) or rejected by the component-kit review |

---

## 1.8 Capacity model

### 1.8.1 Velocity assumptions

| Item | Value | Basis |
|---|---|---|
| Measured baseline | 73 tasks in 12 code days by one founder: 6.1 a day overall, 5.1 a day in Phase 2; ~1,130 hand-written lines per task | Repo history. Achieved at 07:00–00:00, seven days a week, with ADR-078 independent tests deferred on 55 tasks and reviewer agents dropped after TASK-019. Frontend was only ~10% of output |
| **Plan rate** | **14 tasks per founder-week**, 5-day weeks (~2.8 tasks a day) | About 0.3 tasks per hour measured, minus ~25% for restored independent tests and cross-review, over a ~55-hour week. Saturdays are not planned capacity; they are the first recovery buffer (§1.8.6) |
| Two-founder factor | 0.85 per founder (1.7× one founder) | Hot-file contention, review swaps, contract arbitration |
| AY coding share | 60% in S0–S6, then 75% | Vendors, counsel, SOC 2 policies, design partners, discovery, sales, and the design tasks for WB-05 and CLI-03. That is about 37 FW of non-code work over the horizon |
| Hardening reserve | 22.5% of every sprint (≈663 tasks over S0–S73) | Test back-fill for the 55 deferred tasks, pen-test remediation, integration, conflicts, contract-test upkeep. In S0–S5 it also funds F-01 and 20 tasks of Q-01. Never spent on features |
| Pilot support | 0% before Jun 2027; 10% in shadow; 15% in live months; 25% Aug 9 – Oct 15, 2027; 30% in each Jan–Apr season; 12–25% after (≈418 tasks) | N holds SEV1/2; AY handles partners and SEV3 |
| Holidays | Thanksgiving sprint ×0.9; Christmas and New Year sprints ×0.6 | — |
| Learning gains | +10% from S19 (kit reuse: specimen first, then its twins); +15% from S39, only if ADR-086 auto-merge is earned | Both are triggers, not promises; the pessimistic case drops them |
| Per-sprint planned capacity (normal sprint) | N ≈ 18.4 tasks, AY ≈ 13.8 tasks (11.1 in S0–S6), team ≈ 32; ≈ 25 in a busy-season sprint | 2 weeks × 14 × 0.85 × 0.775 × coding share × (1 − support) |

### 1.8.2 Sizing method and totals

**Screen tasks.** Each catalogue row is costed from its frontend and backend complexity:
- frontend S/M/L/XL = 0.5/1/2/4 tasks;
- backend S/M/L/XL = 0.5/1.5/3/6 tasks;
- repo coverage "substantial" multiplies backend by 0.4 and frontend by 0.8; "partial" multiplies backend by 0.7 and frontend by 0.9;
- templates, overlays and specimens multiply frontend by 0.7 and backend by 0.3.

This gives **≈1,180 screen tasks** (478 frontend, 702 backend), which matches the independent check of about 1,181.

**Explicit allowances: ≈940 tasks.** These cover:
- infra (50) and the compliance kernel (40);
- governance and CI (12), decisions (6), model migrations and contracts (30), seed and harness (28), the design system (30);
- the review grammar (26), runtime v2 (55), document services (28);
- the tax compliance rails and 13 deterministic engines (28 + 32 + 18);
- the integration framework and the first live ledger (20), signatures (22), the CAS engine and posting (22 + 18);
- the engine (22 + 18), and smaller allowances per epic (§1.4.3).

**Total: ≈2,120 tasks ≈ 151 FW.** The uncertainty is ±20%: frontend is under-sampled, and the tax engines may grow under golden tests and CPA review.

**Split by lane:**
- N ≈ 1,190 planned tasks: red backend, infra, and the frontend of admin and ops screens built on established kits.
- AY ≈ 900 planned tasks: the design system, most frontend, and ≈330 amber backend tasks named in §1.3.1.
- Lane capacity over S0–S73 is N ≈ 1,206 and AY ≈ 887.

### 1.8.3 Capacity ledger per founder

Planned epic tasks per phase, demand against capacity. Demand is spread across each epic's window, weighted by that founder's sprint capacity. Reserve and support are shown separately.

| Phase | N demand / capacity | AY demand / capacity | Team | Reserve | Support |
|---|---|---|---|---|---|
| PH0 · S0 | 14 / 18 (78%) | 9 / 11 (78%) | 78% | 9 | 0 |
| PH1 · S1–S6 | 93 / 94 (98%) | 64 / 56 (**114%**) | 104% | 44 | 0 |
| PH2 · S7–S15 | 177 / 162 (**109%**) | 131 / 122 (107%) | 108% | 84 | 6 |
| PH3 · S16–S30 | 248 / 238 (104%) | 192 / 178 (108%) | 106% | 136 | 89 |
| PH4 · S31–S38 | 110 / 108 (102%) | 79 / 81 (98%) | 100% | 71 | 81 |
| PH5 · S39–S51 | 201 / 226 (89%) | 165 / 169 (97%) | 92% | 122 | 87 |
| PH6 · S52–S65 | 215 / 215 (100%) | 171 / 161 (106%) | 103% | 123 | 110 |
| PH7 · S66–S74 | 129 / 160 (80%) | 91 / 120 (76%) | 78% | 84 | 54 |

**Cumulative team load:** 100% at M5 (S6), 107% at S13, 105% at M8 (S15), 109% at S21, 105% at M15 (S30), 104% at S38, 99% at S44, 101% at S51 and 100% at S73.

**The 2027 overcommit is deliberate and bounded.** It is 5–9%, about 57 tasks at its peak (S21), and it is covered task-for-task by cut tiers 1–2 (§1.8.4). The cut items are deferred into the PH5 and PH7 slack, not dropped.

**The binding lanes:**
- AY in PH1, where the design system meets the 60% coding share.
- N in PH2, where red-zone MVP work meets the compliance kernel.

Those are the two places to watch at M5 and M8.

**Per-sprint excerpt, S0–S21** (planned tasks; capacity / demand):

| Sprint | Starts | Support | N cap / demand | AY cap / demand | Cumulative team |
|---|---|---|---|---|---|
| S0 | Oct 19 | 0% | 18.4 / 14.4 | 11.1 / 8.6 | 78% |
| S1 | Nov 2 | 0% | 18.4 / 15.7 | 11.1 / 10.5 | 83% |
| S2 | Nov 16 | 0% | 16.6 / 15.0 | 10.0 / 10.7 | 88% |
| S3 | Nov 30 | 0% | 18.4 / 19.2 | 11.1 / 12.3 | 92% |
| S4 | Dec 14 | 0% | 11.1 / 14.0 | 6.6 / 8.8 | 97% |
| S5 | Dec 28 | 0% | 11.1 / 12.2 | 6.6 / 8.3 | 99% |
| S6 | Jan 11 | 0% | 18.4 / 16.5 | 11.1 / 13.6 | 100% |
| S7 | Jan 25 | 0% | 18.4 / 18.8 | 13.8 / 19.3 | 103% |
| S8 | Feb 8 | 0% | 18.4 / 20.2 | 13.8 / 18.2 | 105% |
| S9 | Feb 22 | 0% | 18.4 / 23.1 | 13.8 / 19.2 | 108% |
| S10 | Mar 8 | 0% | 18.4 / 22.6 | 13.8 / 18.1 | 110% |
| S11 | Mar 22 | 0% | 18.4 / 20.0 | 13.8 / 11.1 | 108% |
| S12 | Apr 5 | 0% | 18.4 / 18.6 | 13.8 / 10.1 | 107% |
| S13 | Apr 19 | 0% | 18.4 / 23.4 | 13.8 / 12.8 | 107% |
| S14 | May 3 | 10% | 16.6 / 16.4 | 12.5 / 11.3 | 106% |
| S15 | May 17 | 10% | 16.6 / 13.7 | 12.5 / 10.5 | 105% |
| S16 | May 31 | 15% | 15.7 / 20.8 | 11.8 / 15.4 | 106% |
| S17 | Jun 14 | 15% | 15.7 / 22.1 | 11.8 / 15.7 | 108% |
| S18 | Jun 28 | 15% | 15.7 / 20.1 | 11.8 / 15.2 | 109% |
| S19 | Jul 12 | 15% | 17.2 / 18.5 | 12.9 / 14.4 | 109% |
| S20 | Jul 26 | 15% | 17.2 / 19.0 | 12.9 / 13.6 | 109% |
| S21 | Aug 9 | 25% | 15.2 / 16.7 | 11.4 / 12.0 | 109% |

The sprint-by-sprint ledger (`docs/product/capacity-ledger.md`) is updated every Friday of week 2 from the velocity log, and it is the input to every calibration gate.

### 1.8.4 Pre-agreed cut lists

The tiers are agreed now and invoked at the gates in §1.8.7. Tier 1 and tier 2 items are **deferred, not dropped**: they land in PH5 slack.

| Tier | Cut | Saves (tasks) |
|---|---|---|
| **1** (M5 or M8) | CLI-07 and CLI-08 record-only: no questionnaire, NAS engine or AI pre-screen yet | 6 |
| 1 | ENG-13 roll-forward re-skin after S31 | 4 |
| 1 | AUD-06 v1 read-only from file import; the live ledger read slides to Sep 2027 | 6 |
| 1 | HOME-01 lite (audit tiles only); SHL-07 popover without the lineage tab | 5 |
| 1 | ADM-07 minimal explorer (filters and export, no value resolution); KNW-01 read-only catalog over imports | 6 |
| 1 | POR-20 template editor replaced by admin import; ADM-10 logo, name and sender only | 5 |
| **2** (M8 or M14) | AUD-10 SOC 1 reliance to Q2 2028 | 6 |
| 2 | AUD-18 EQR to Q2 2028 (pilot engagements without an EQR requirement); POR-15 governance room to Q2 2028 | 8 |
| 2 | EBP-08 participant accounts to Q1 2028 (EBP-07 does not read it) | 3 |
| 2 | KNW-02 methodology versions and import review to 2028 | 8 |
| 2 | BND-03 organizer editor replaced by organizer import for TY2027 | 4 |
| **3** (date moves, only after tiers 1–2) | Shadow Jun 1 → Jun 15; R3 Jul 13 → Jul 27 | — |
| 3 | 8879 in record mode (import the firm's own DocuSign evidence) | 6 |
| 3 | Tax pilot NO-GO at M8 | ≈110 in S16–S21 |

### 1.8.5 Critical path

| Chain | Path | Dates | Slack |
|---|---|---|---|
| **CP-A Production readiness** | S0 AWS, TASK-014, provider-terms entry, SOC 2 tool and auditor → R0 → R1 (controls operating) → pen test → Type I as of Mar 1 → report → highs closed → M7 → M9 | Oct 19, 2026 → Jun 1, 2027 | ≈6 weeks to Jun 1: the product chain binds, not compliance. If the Type I report slips past May 14, M9 moves |
| **CP-B Model and trust spine** | Decisions (Oct 23) → F-03 migrations (C1, C2, C5) → C3 and C4 schemas (S3–S5) → review-grammar services (S10–S16) → review UI (S16–S26) → workpapers and sign-offs for W2 → A-07 release and archive (Mar 2028) | Oct 23, 2026 → Mar 21, 2028 | 0 in PH1–PH2; N's lane runs at 105–109% |
| **CP-C Audit MVP to client-facing** | DS core (S0–S10) → audit spine (S7–S13) → TB and ledger (S8–S17) → portal (S7–S18) → inbox (S13–S18) → M8 → M9 → M10 | → Jul 13, 2027 | ≈2 weeks (tier 3) |
| **CP-D Tax extension pilot** | M8 GO → T-01, T-02, N-02 (S16–S21) → shadow Jul 27 – Aug 13 → M11 → M13 → Sep 15, Sep 30, Oct 15 | May 28 → Oct 15, 2027 | ≈2 weeks; after that, only Sep 30 and Oct 15 filers |
| **CP-E 2028 season readiness** | A-06 → A-07 schema by S30 → T-03 → N-04 → M15 | → Dec 10, 2027 | ≈1 sprint |
| **CP-F 2028 extension-season tax** | P-10 and P-11 OCR → T-04 (S32–S39) → shadow from Mar 20 → M17 → T-05 (S35–S44) → M18 | → Aug 1, 2028 | ≈2 sprints |
| **CP-G CAS** | Intuit production keys → C-01 (S44–S51) → shadow on the September close → M20 → C-02 W1 (S49–S55) → M21 | → Dec 8, 2028 | ≈3 sprints |
| **CP-H Group audit** | AUD-31 (A-03, S20–S23), AUD-07 (A-04), review UI → A-09 (S45–S50) → M19 | → Sep 29, 2028 | ≈4 weeks before Dec-YE planning |
| **CP-I Engine-based journeys** | F-08 → K-03 (S52–S60) → K-04 (S59–S65) → M22 → X-01, X-03, A-11 → M23 | → Aug 17, 2029 | ≈2 weeks before GA |

The CP-A and CP-B rows are reviewed every Contract Monday. The rest are reviewed at each gate.

### 1.8.6 Where slip is absorbed, in order

1. **Inside the sprint.** The reserve absorbs integration and conflict overruns only after that sprint's test back-fill commitment is met. It is never spent on features.
2. **Cut tiers 1–2** (§1.8.4): deferred into PH5 slack, not dropped.
3. **Unplanned Saturdays.** They are the first human buffer, time-boxed to the crunch weeks before M8 and M13 and recorded in the velocity log. They are never planned capacity.
4. **Tier 3 date moves** of two weeks.
5. **Tax pilot NO-GO at M8**, which frees about 110 tasks in S16–S21.
6. **Hires at M12**, which add about 200 tasks by S38 and about 440 by S51.
7. **The PH6–PH7 spill list.** It is ordered, and it holds only P2 and wave-7/8 depth, never a P0 spine or a pilot journey:
   1. I-04 practice economics;
   2. G-03 developer platform;
   3. X-02 ISO readiness and GRC sync;
   4. W-04 (XLA-02, then XLA-01);
   5. K-05 (KNW-08, KNW-11, KNW-12, WB-13);
   6. X-03 internal audit;
   7. T-09 advisory;
   8. R-03 (POR-10, POR-18, POR-19);
   9. I-03 (INS-03, then INS-04);
   10. Q-05 depth (AUD-28, AUD-30 after the QM dashboard).

   Together this is about 207 tasks. Applying it keeps GA at Aug 31, 2029, even with no learning gains at 14 tasks/FW.

### 1.8.7 Calibration gates

| Gate | Measured | Thresholds and actions |
|---|---|---|
| M3 (Nov 20) | Frontend tasks per day on the Accrued kits (S1–S2); red-lane throughput | <85% of plan → cut tier 1 now |
| M5 (Jan 22) | Planned-epic throughput S1–S5 per founder against the ledger | ≥90% hold; 80–90% tiers 1–2; <80% tier 3 |
| M8 (May 28) | Throughput S7–S14; red-review latency | ≥95% and partner and counsel ready → tax GO; otherwise NO-GO (§1.2.2) |
| M14 (Oct 15) | Throughput S16–S25 including support; conversion result | Re-plan PH4–PH5; add the hires' capacity if M12 passed |
| M15 (Dec 10) | Escaped-defect log; auto-merge earned? | If auto-merge is not earned, drop the +15% gain from S39 and pre-schedule spill items 1–3 |
| Every phase exit | Per-founder ledger; red-review queue age | Queue >2 working days for 2 sprints → move amber work to AY, or bring the hire forward |

### 1.8.8 Scenarios

| Scenario | Assumptions | Feature-complete | GA |
|---|---|---|---|
| **Central (plan of record)** | 14 tasks/FW, gains as in §1.8.1 | **Fri Aug 17, 2029** (S73) | **Fri Aug 31, 2029** |
| No learning gains | 14 tasks/FW, no gains | Nov 23, 2029 | Aug 31, 2029 with spill items 1–10 after GA |
| Optimistic | 15 tasks/FW | ≈Jun 22, 2029 | ≈Jul 2029 |
| Slow | 13 tasks/FW, no gains | ≈Mar 2030 | ≈Oct 26, 2029 with the spill list after GA |
| Pessimistic | 12 tasks/FW, no gains | ≈Jul 2030 (Jan 2031 with +12% scope) | ≈Feb 2030 with the spill list after GA |
| **With hires (M12 passes)** | 2 engineers from Oct 4, 2027; 6-week ramp; 0.55 founder-equivalent each | **≈Dec 8, 2028** (S55) | ≈Jan 2029; CAS ≈May 2028; group audit for Jun-2028 YE; engine Q4 2028 |

The phase order does not change across scenarios. Only PH6–PH7 move, along with whether the 2027 tax pilot runs.

### 1.8.9 Top risks

| # | Risk | Likelihood / impact | Mitigation | Owner |
|---|---|---|---|---|
| 1 | Velocity below plan; frontend on the Accrued kits unmeasured | High / high | Calibration from S1; cut tiers; contract-first fixtures; earned auto-merge; hiring gate | both |
| 2 | Real-data gate slips (Type I report, pen test, Bedrock register, vendor approvals) | Medium / high | Clocks started in S0; production from Dec 11; dated fallback (M7 → May 14; PW1 → Jun 15) | N (controls), AY (auditor, counsel) |
| 3 | N's red lane is the bottleneck | High / high | ~330 amber tasks named to AY; N builds frontend only on established kits; red tickets capped at 25%; review SLAs; first hire is backend | both |
| 4 | Design partners do not commit or churn | Medium / high | Named targets by Nov 20; Pilot 0; priced founding-partner agreement with a named champion; shadow before live; two audit windows plus the tax window | AY |
| 5 | Compliance missteps (§7216, invalid 8879s, ERO creep, independence breaches from CAS posting) | Low early, severe later | Fail-closed consent gate; counsel-approved text; provider KBA with C-05 fallback; Pub 1345 re-lock; never-ERO tests; W1 hard-off for attest clients; INV-1 in every journey | N (gates), AY (counsel) |
| 6 | In-season changes break live paths | Medium / high | Freeze contract (§1.2.4), Tuesday flips with rollback and both approvals, expand-only migrations, no year-one exception | N |
| 7 | Vendor dependencies (WK partnership, Intuit keys, DocuSign Go-Live, Microsoft verification, NetSuite SDN) | High / medium | Every application filed in S0; file bridge, JE export, record mode, portal upload and upload-TB fallbacks | AY |
| 8 | Data-model churn after real data | Low / high | Every model migration lands before Jun 1, 2027; strict expand/contract after | N |
| 9 | Tax computation errors | Medium / high | Pure-function engines, blueprint 9.8 golden tests, property tests, CPA review before M18; CCH stays authoritative | AY |
| 10 | Founder burnout | Medium / high | 5-day planning week; Saturdays only as a measured buffer; runbooks so both can operate every red area by PH3 | both |

---

## 1.9 Decision Day (Fri Oct 23, 2026) and alignment with chapter 09

Chapter 09 holds the canonical decision register (DEC-01…DEC-99) and the ADR backlog (P-01…P-63). This chapter does not mint decision IDs. The table lists the register rows the roadmap depends on, with the roadmap's position and its deadline on this calendar. Decision Day is held at the end of S0 week 1, once the drafts exist. Chapter 09's default-on-silence rule applies, except to rows that spend money, need counsel, or are red-zone ADRs.

| DEC | Decision | Roadmap position | Owner | Needed by |
|---|---|---|---|---|
| DEC-02 ★ | Two-founder governance | Either founder approves, never the author; number blocks as in §1.3.3 (ADR P-02) | N | Oct 23 |
| DEC-03 ★ | AWS foundation and budget | Approve the year-one spend envelope (§1.6.7); us-east-2 primary, us-west-2 DR (conflict C-16); Control Tower accounts | both | Oct 23 (unblocks TASK-014) |
| DEC-04 ★, DEC-15 | Design-system cut and precedence | One cut in DS-S1; `revision.md` > spec > kit (G-D01); ADR P-03 supersedes SPEC-016 Atelier | AY | S0 |
| DEC-05 ★ | Real-data posture | Real-data gate Apr 16 with no exception path; **first internal shadow Tue Jun 1, client-facing Tue Jul 13, 2027** | both | Oct 23 |
| DEC-07 ★ | Work items | `work_items` supertype for all five kinds, 8-state lifecycle, per-type gate policy, backfill in S1 (ADR P-04) | N | S1 |
| DEC-08 ★ | Status contract | Blueprint 3.3.1 + addendum 3.2 generated into one registry; `lib/status.js` is visuals only | AY | S1 |
| DEC-09 ★ | Request enum | Migrate in S1 to draft · requested · uploaded · received · returned · not_applicable | N | S1 |
| DEC-11 ★ | Contrast (D-DS-2) | AA text ladder (ink-2 .70, ink-3 .66) and a .55 outline focus ring; reference-contrast mode for parity runs only | AY | S0 |
| DEC-14 ★ | Glossary | One PR: to-do never "task"; Document only in Files; `sign_off` distinct from `review_decision`; SPEC-022 Board renamed "Evidence board" | AY | Oct 30 |
| DEC-17 ★ | Long-lead applications | Every vendor, assurance and counsel application filed in S0 (F-09) | AY | Oct 30 |
| DEC-20 | Firm-admin content rights (question Q-07) | `client_service` engagement role; admins stay metadata-only (ADR-024) | both | S2 |
| DEC-22 | Staff and client authentication | WorkOS (resolve the allowlist's "pending"); hosted sign-in first | N | Oct 23 |
| DEC-23 | Real time | SSE through AbacusRouter plus polling; no WebSockets; no CRDT in v1; never stream unverified citations (ADR P-15) | N | before P-09 |
| DEC-25 | E-signature | Record mode, then DocuSign embedded with provider-hosted ID Verification; handwritten fallback after 3 failures; Pub 1345 amount-hash re-lock; native ceremony not planned | N | Oct 30; DocuSign go/no-go Dec 4 |
| DEC-27 | Demo clock and synthetic marker | Injectable clock; the firm is flagged synthetic, with no "(Synthetic)" suffix | N | S1 |
| DEC-33 | Client-level files (question Q-08) | Nullable `engagement_id` with a client-scope read rule | N | S3 |
| DEC-46 | Integrations and writes | One write-capability framework ADR plus registry entries W7 DocuSign (first), W2 CCH file export, W6 Graph send-as and W1 QBO posting; `connections` stays read-only | N | S2 |
| DEC-49 | Tax-engine route | CCH Axcess file bridge; never ERO or transmitter (requirement R-04); API only if Wolters Kluwer grants access (ADR P-18) | AY (vendor), N (adapter) | S14 |
| DEC-53 | Policy principal | Deferred; named-human batch approval; `policy` actor kind dormant (ADR P-08) | N | — |
| DEC-55 | Flags vs entitlements | Modules and plans as database entitlements; flags rollout-only; the 9 expiring flags renewed in the Dec 14–18 bundle (ADR P-28) | N | S3 |
| DEC-64 | SPEC-025 "record, don't rebuild" | Superseded: acceptance and conflicts are performed in-app by humans; the AI pre-screen comes later | both | S2 |
| DEC-65 | SAS 149 go/no-go | Dec-2026 year-ends NO-GO now. Jun-2027 and Dec-2027 recorded at M3: NO-GO at plan velocity. Dec-2027 only as the M8 alternative to the tax pilot, or with the M12 hires. Target Dec-2028 year-ends. Fallback: upload TBs and manual eliminations | both | M3 |
| DEC-68 | Busy-season policy | ADR P-29 as in §1.2.4: per-firm windows from first real data; no year-one exception | both | Dec 14–18 bundle |
| DEC-70 | First live ledger | Chosen at M3 from discovery (ADR-045); QBO expected for CAS; NetSuite stays on file import until SDN | AY | M3 |
| DEC-79 | Model text to clients | ADR P-25 accepted, off by default per firm; human-edited and human-sent only, after per-drafter evals | both | before N-03 |
| *proposed* DEC-100 | Pricing and founding-partner terms | Packaging and price hypothesis (§1.6.7), tested in discovery | AY | M4 |
| *proposed* DEC-101 | Hiring trigger | Two engineers if ≥2 of 3 partners sign paid season-2 agreements by Aug 20, 2027; backend first | both | M12 |

**Where this roadmap amends chapter 09.** Chapter 09 owns decisions and this chapter owns dates, so these rows should be edited in chapter 09 to match:
1. **DEC-05.** The first shadow moves from Mon May 3 to **Tue Jun 1, 2027**, and client-facing use starts **Tue Jul 13**. At honest velocity, MVP-1 completes in S15 (§1.8.3). The Apr 16 gate and its criteria are unchanged. If the founders want to hold May 3, cut tiers 1–2 must be invoked at M5.
2. **DEC-65 and conflict row X-10.** At plan velocity, the first real SAS 149 season is **Dec-2028 year-ends** (A-09 ready Sep 29, 2028). AUD-31 single-entity mapping lands in A-03 (S20–S23, Jul–Sep 2027), not by Dec 18, 2026. Dec-2027 year-ends stay available as the M8 alternative, or with the M12 hires.
3. **Calendar.** This chapter uses continuous two-week sprints with holiday capacity factors (S5 = Dec 28 – Jan 8 at 60%), as the brief sets. Chapters 06 and 09 insert a holiday week, so their S5–S12 run one week later. The dates in this chapter are the ones that count.
4. **Epic keys.** Chapter 09's draft keys EP-01…EP-28 map to the canonical epics in §1.4 through screen IDs. Chapter 09 already treats screen IDs as authoritative.
5. **New rows.** DEC-100 (pricing and founding-partner terms) and DEC-101 (hiring trigger) are added.

### Review findings closed

| Finding | Where it is closed |
|---|---|
| Non-negotiable real-data gate; shadow-stage runs need register, evals and opt-in | §1.2.2 M7 and M9; Q-02; §1.6.6 |
| SOC 2 sequencing; auditor booked early; dated fallback | §1.2.3 (production Dec 11, as-of Mar 1); M7 fallback |
| Pen-test coverage follows each real-data surface | §1.2.3 deltas #1–#2, #2, W1, W6 and API |
| Velocity of record 12–15 tasks per FW, measured early | §1.8.1 (14, 5-day weeks); calibration at M3 and M5 |
| Non-coding capacity; support 25–30% in season | §1.8.1 (AY 60% → 75%; support schedule) |
| Commercial model, conversion milestone, hiring trigger, spend plan | §1.6.7; M12; proposed DEC-100 and DEC-101 |
| Vendor-diligence pack, insurance, BAA | M7; F-09; Q-02 |
| Public-repo history scan and rotation | F-01; M1 |
| 9 flags renewed before Jan 5–13, 2027 | Dec 14–18 bundle (M4); §1.2.4 |
| No client-facing go-live Jan 15 – Apr 15 | First real data Jun 1; client-facing Jul 13 |
| Pilot onboarding tooling; firm tool stays authoritative | CLI-06 bulk import; K-01 and R-01 imports; binder export (A-01) |
| Design partners as the critical path; fallback | §1.6.4; M3 |
| AI value in the first pilot without model text to clients | §1.6.6 |
| Tax correctness and posture before live tax | §1.6.2; M11, M13, M18 |
| Week-1 decisions with owners | §1.9 (DEC-02, -03, -05, -07, -09, -22, -25, -65, -68, -70) |
| Per-founder ledger; N's lane; amber work to AY by name | §1.8.3; §1.3.1 |
| Review-grammar and trust schemas before the first firm; no new red schema inside a freeze | P-04 schema S3–S4; P-03 C4 S5; A-07 and P-10 schemas by Dec 10, 2027 |
| Work-item supertype for all kinds; request enum before portal data | F-03 (S0–S4) |
| Compliance kernel before each data class; TRI gate before tax data | Q-02; T-01 before M11 |
| 55 deferred test suites back-filled before real data; mutation testing; branch protection | Q-03 (S6–S13); F-01 |
| EBP ordering (EBP-07 after EBP-05/09 and AUD-20; EBP-06 after AUD-16; one late_remittance object) | A-05 and A-06 notes |
| Write ADRs before each first external write (W7, W2, W6, W1) | DEC-46; N-02, T-01, N-03, C-02 |
| Group-audit decision on the real dependency set | DEC-65; §1.7.2; A-09 |
| SSE ADR before the first dock; poll until then | DEC-23; P-09, P-10 |
| WB-05 and CLI-03 designed a phase ahead; R2 revisions behind capability flags | W-03 (design S8–S12), T-06 (design by S44); §1.4 |
| S0 design-system decisions (AA ladder, status registry, glossary, SPEC-016) | DEC-11, DEC-08, DEC-14, DEC-04 |
| Hook fix; worktree isolation; pre-registration PR; CODEOWNERS both handles | F-01, F-03; §1.3.3 |
| CI rebuild; PR-size target | F-01; §1.3.3 |
| Admin import endpoints before onboarding; content in the database | K-01, K-02, R-01, T-03; §1.3.3 |
| Named on-call per live window; no red modules on live paths in a freeze | §1.3.1; §1.2.4 |
