# 7 · Sprint plan

> Chapter of the Accrued engineering and build plan. Written Sunday 2026-10-18; Sprint 0 starts Monday 2026-10-19.
>
> **Readers.** Both founders and their Claude Code sessions. **N** = notanaskhan (technical co-founder, red-zone backend, infra, compliance kernel). **AY** = ayushkbhatia (product and design founder; design system, frontend, amber read models and compute, vendors, counsel, design partners).
>
> **What this chapter is.** The task-level schedule. It loads every `sections/epics/*.tasks.csv` (74 files), checks them, and lays them on the calendar of chapter 01. Chapter 01 is the plan of record for order, dates, owners, scope, contracts and capacity; where a CSV disagrees with it, chapter 01 wins and §7.5.5 lists the disagreement instead of silently moving anything. Decision IDs and proposed-ADR IDs are chapter 09's (DEC-01…99, P-01…P-63); this chapter mints none.
>
> **Companion file.** `plan/backlog.csv`: all 3,704 tasks, sorted by sprint, then epic, then task number, with the original eleven columns plus `start_date` and `end_date` (the Monday and Friday of the task's sprint).
>
> **Units.** A *task* is one Claude Code session of about 1,130 hand-written lines including tests. An *FW* is 14 tasks. Sizes in this chapter are in tasks. *Sn* runs from Oct 19, 2026 + 14n days, Monday to the second Friday.

---

## 7.0 The chapter on one page

**The CSVs are clean.** 74 files, 3,704 rows, one header shape, no duplicate task IDs, every row's epic matches its file, every sprint is an integer and every size a number. All 7,012 task-to-task dependencies and all 676 contract references (C1–C21) resolve, and no task depends on a task in a later sprint. Total size is 3,647 tasks, of which F-09 (non-code, 197), Q-03 (hardening reserve, 626) and Q-04 (pilot support, 437) are funded outside planned capacity, exactly as chapter 01 §1.4 says.

**The calendar holds; the capacity does not.** Every CSV task sits inside its chapter 01 epic window except eight small, deliberate ones: six pre-window ADR drafts, one design board and one post-freeze wire-up (§7.5.5). No milestone date moves. But the task decomposition is bigger than chapter 01's sizing, and it is assigned unevenly between the founders:

| Measure (S0–S74, planned pool only) | N | AY | Team |
|---|---:|---:|---:|
| Planned capacity after the 22.5% reserve, pilot support and holidays (chapter 01 §1.8.1 formula) | 1,227 | 903 | 2,130 |
| Chapter 01 demand (§1.8.3) | 1,187 | 902 | 2,089 |
| CSV demand as sized | 957 | 1,402 | 2,359 (**111%**) |
| of which ADR-078 independent-test rows | 137 | 286 | 423 |
| CSV demand without those rows | 820 | 1,116 | 1,937 (91%) |
| Over-allocated sprints (>100% of planned capacity) | 14: S1–S8, S10, S12–S13, S31, S47, S52 | 69: S1–S12, S14–S55, S58–S72 | — |

**Three findings drive the rest of the chapter.**

1. **The lanes are inverted against chapter 01.** Chapter 01 plans N ≈ 1,190 and AY ≈ 900 tasks. The CSVs give N 957 and AY 1,402. AY is over capacity in 69 of 75 sprints; N is under capacity in most sprints after S13. Re-balancing back toward chapter 01's split (lane swaps of amber backend, data, docs and admin-screen frontend to N, and shifts inside the epic windows) moves 267 tasks, about 248 tasks of work, and unused reserve pays for 82 tasks of same-sprint tests; no date changes (§7.5.4).
2. **PH1 (S1–S6) is the acute problem.** Both founders are over in every PH1 sprint: N 137%, AY 188%, team 156%. The CSVs front-load model, infra, design-system and portal work that chapter 01's ledger spread across PH1–PH2. After every in-window move, about 67 tasks still have no capacity before M5 (Jan 22). M2, M4 and M5 are at risk on capacity, not on dependencies.
3. **A unit question decides whether the plan fits.** Chapter 01's velocity of record (14 tasks/FW) already deducts about 25% for restored ADR-078 independent tests and cross-review (§1.8.1). The CSVs also list those tests as separate rows (423 tasks). If the rows are paid by that deduction, the re-balanced plan has about 100 tasks of residual overload: cut tiers 1–2 cover the 56 in PH1–PH3, and the M12 hires or the spill list cover the 45 in PH5–PH6. If every row costs its full size, the residual is about 324 tasks and the tier-3 date moves, the tax NO-GO or the M12 hires become necessary. **The M3 calibration (Fri Nov 20) must measure test rows separately to settle this** (§7.7).

**Recommendation for Decision Day (Fri Oct 23).** Accept the CSV task lists as the S0–S2 working backlog; approve the re-balancing method of §7.5.4 for S1 Contract Monday; and add one measurement to M3: the cost of an ADR-078 test row against a feature row. Do not move any chapter 01 date now.

**Critical path.** Task-level, two chains have zero sprint-slack from S0 to S12: governance → model migrations → portal identity → portal PBC (F-01 → F-03 → P-08 → R-01), and production readiness (F-01 → Q-01 → Q-02 → Q-03 → the M7 dossier). The M5 sprint (S6) holds 22 zero-slack tasks while N is at 119% and AY at 192%; four of them (P-07-T19…T22, the ENG/CLI record cores and the J02 journey steps) fall beyond capacity in the simulation. After S12 the chains of chapter 01 §1.8.5 hold with the CSV windows, at 0–2 sprints of slack (§7.6).

---

## 7.1 Cadence and rituals

### 7.1.1 The two-week rhythm

Every sprint runs the same ten working days. Times are US Central.

| Day | Time | Ritual | Who | Length | Output |
|---|---|---|---|---|---|
| Mon wk 1 | 09:00 | **Contract Monday** (sprint planning) | both | 60 min | Sprint goal; each founder's task list taken from `backlog.csv`; contracts to freeze this sprint and next; the sprint's **protected bundle** named (it merges first in B1); decision-log review; CP-A and CP-B critical-path review (chapter 01 §1.8.5); re-balancing moves confirmed from §7.5.4 |
| Tue (both weeks) | 10:00 | **Production release PR** (from R1, Dec 11) | author + other founder approves | 15 min | `deploy/production/release.json` updated to the last staging-verified SHA (≥1 business day of soak), merged by the other founder's approval, which triggers `deploy-production` (chapter 06 §2.4) |
| Tue wk 1 | 17:00 | **Batch window B1** | both | 30 min | Protected bundle first, then contract stub PRs, then approved PRs labelled `hold:batch`; one staging deploy |
| Wed wk 1 and wk 2 | 10:00 | **Contract sync** | both | 30 min | Open `contract: <name> vN` issues; stub PRs due within 3 working days; consumer tests green in the provider's CI; blockers; red-review queue age (chapter 01 §1.8.7 trigger) |
| Thu wk 1 | 17:00 | **Batch window B2** | both | 30 min | One staging deploy |
| Fri wk 1 | — | Focus day | — | — | No merge window. AY holds design-partner office hours on Tue and Thu (chapter 01 §1.6.5) |
| Tue wk 2 | 17:00 | **Batch window B3** | both | 30 min | One staging deploy |
| Thu wk 2 | 17:00 | **Batch window B4** | both | 30 min | One staging deploy |
| Fri wk 2 | 12:00 | **Batch window B5** (sprint close) | both | 30 min | Docs, parity reports, ledger updates and flag renewals that close the sprint; one staging deploy, which is the demo build |
| Fri wk 2 | 14:00 | **Demo** on staging | both (partners invited from PW0) | 45 min | The sprint's demo script (§7.3) run on the B5 build against the Brightwater Hale tenant and the demo clock, journeys with INV-1…5 and axe |
| Fri wk 2 | 15:00 | **Exit check, velocity log, capacity ledger** | both | 30 min | Exit check signed; `docs/product/capacity-ledger.md` updated from the velocity log; escaped-defect log reviewed; 15-minute retro |

**Review SLAs** (chapter 01 §1.3.2): contract PRs the same day; red PRs within 1 working day; amber within 2. A PR approved after Thursday's window waits for B5 or the next sprint's B1; it is never merged alone.

### 7.1.2 Merge batches and staging deploys

- **Five windows a sprint, one staging deploy each.** Approved PRs carry `hold:batch` and the line "holding this until the batch". The batch is merged in one sitting by whichever founder is on batch duty that week; a red `main` stops the batch. Immediately after the last merge, that founder dispatches **Ship batch** once; the 18:30 weekday schedule of chapter 06 then finds staging already on the green SHA and does nothing. That is at most five staging deploys a sprint, instead of one per merge.
- **Protected bundle first.** The sprint's protected bundle (matrix sections, flags, allowlist, glossary, registry pre-registration) merges first in B1, so feature PRs rebase once.
- **Migrations.** One migration per PR; whoever merges second renumbers; the single-head check guards the chain. Inside a freeze window, migrations are expand-only and run after 21:00 CT (chapter 06's time, which also satisfies chapter 01's "after 8 pm").
- **Previews are opt-in** (`preview` label, fixture-mode static build); a push never builds by itself.
- **No local production build** while a hosted build or deploy uses the same database; the F-01-T09 `make` guard refuses it.
- **Exceptions that ship immediately:** production broken, a security fix, or a founder's explicit request (hotfix lane; never skips staging).
- **Holiday weeks.** S2: B4 and B5 fold into one closing window on Wed Nov 25 (Thanksgiving). S4: B4 on Wed Dec 23 closes the sprint; no window on Dec 24–25. S5: B2 moves to Wed Dec 30. The demo still runs on the last build of the sprint.
- **Before staging exists.** S0 and the first three windows of S1 merge without a staging deploy; the staging train (Q-01-T18) and R0 bring-up (Q-01-T20) make B4 of S1 (Thu Nov 12) the first staging deploy, one day before M2.

### 7.1.3 Production promotion

Production promotion follows chapter 06 §2.4: build once per SHA, promote by a release-manifest PR the other founder approves, a staging soak of at least one business day, schema changes at 21:00 CT, and a hotfix lane that never skips staging.

| Period | Cadence | Notes |
|---|---|---|
| S0 – Dec 10, 2026 | No production | Production account and canary built in S2–S3 |
| R1 (Fri Dec 11, 2026) – M9 (Tue Jun 1, 2027) | Weekly, Tuesday 10:00 CT, plus milestone releases | Canary tenant only. The Friday B5 build soaks Monday and is promoted Tuesday |
| From M9, outside freeze windows | Weekly | Chapter 01 §1.3.3 says Thursday from M9; chapter 06 says Tuesday. This chapter schedules **Thursday from M9** as chapter 01 is the plan of record for dates, and lists the difference in §7.5.5 |
| Inside a firm's freeze window (Jan 1 – Apr 20; Sep 1 – Oct 20 for tax and EBP firms; mini-freezes Sep 8–15, Sep 23–30, Oct 8–15) | Tuesday 19:00 CT slot only | Defect fixes on live paths; dark modules behind default-off flags; per-firm flag flips with both founders' approval, staging e2e, a shadow run and a written rollback (P-29) |
| Deadline weeks (Mar 15, Apr 15, Sep 15, Sep 30, Oct 15) | No promotion | Hotfix lane only |

### 7.1.4 Fixed dates inside S0–S12

| Date | Sprint | Event |
|---|---|---|
| Mon Oct 19 | S0 | Merge freeze and baseline tag; secret scan while public, then private |
| **Fri Oct 23** | S0 | **Decision Day (M0)**: the chapter 01 §1.9 agenda recorded in chapter 09's register (F-02-T05) |
| Fri Oct 30 | S0 | **M1**: S0 exit; glossary merged; every long-lead application filed |
| Fri Nov 13 | S1 | **M2**: R0 staging live; C1 and C2 frozen |
| Fri Nov 20 | S2 | **M3**: ≥2 LOIs, first live ledger chosen, group-audit record, calibration #1 |
| Fri Dec 4 | S3 | DocuSign go/no-go (DEC-25) |
| Fri Dec 11 | S3 | **M4**: R1 production with canary; SOC 2 controls operating; auditor engaged |
| Dec 14–18 | S4 | Protected bundle: the 9 flags expiring Jan 5–13, 2027 renewed; P-29 accepted |
| Mon Jan 11, 2027 | S6 | Pilot 0 (PW0) sessions begin |
| Fri Jan 22 | S6 | **M5**: platform spine walkable on staging; re-baseline #2 |
| Mon Jan 25 | S7 | AY's coding share rises from 60% to 75% |
| Feb 15 – Mar 5 | S8–S9 | Pen test #1 on the build pinned Feb 12 |
| Mon Mar 1 | S9 | SOC 2 Type I as-of date |
| Fri Mar 5 | S9 | **M6**: pen test #1 complete; J04 PBC slice on staging |
| Fri Apr 9 | S12 | Pen-test criticals and highs retested closed |
| **Fri Apr 16** | S12 | **M7**: real-data gate (R2), no exception path |

### 7.1.5 Where the cadence differs from other chapters

| Item | Chapter 01 | Chapter 02 / 06 | This chapter |
|---|---|---|---|
| Mid-sprint sync | "Thursday of week 1, 30 minutes: blockers" | — | Wednesday contract sync both weeks, carrying the blocker agenda (the brief for this chapter asks for Wednesday); Thursday keeps the B2/B4 windows |
| Merge windows | Tue and Thu at 17:00 CT | Chapter 02: at most one batch a day; chapter 06: end of session or coherent batch | Tue and Thu at 17:00 CT plus a Friday sprint-close window; one staging deploy per window |
| Production weekday | Thursday from M9; Tuesday 19:00 CT inside windows | Chapter 06: weekly Tuesday 10:00 CT | Tuesday until M9, Thursday after; Tuesday 19:00 CT inside windows |
| Length of Sprint 0 | Oct 19 – Oct 30 | Chapter 02 §2.3.2: "Mon 19 Oct – Fri 23 Oct" | Two weeks (chapter 01). Chapter 02's checklist runs in week 1, its spill-over in week 2 (§7.2) |

---

## 7.2 Sprint 0 day by day (Mon Oct 19 – Fri Oct 30, 2026)

**Goal.** Make two-founder work safe, take the blocking decisions, start every long-lead clock (PH0, chapter 01 §1.2.1). **Milestones:** M0 Decision Day (Fri Oct 23) and M1 S0 exit (Fri Oct 30).

**How the two sources fit.** Chapter 02 §2.3.2–2.3.3 orders the stabilisation checklist S0-01…S0-17 inside one week; chapter 01 gives S0 two weeks. The checklist runs in week 1 in chapter 02's order (repo settings, then CI, then process files), and its spill-over items (S0-14 worktrees, S0-15 Bedrock, S0-16 staging) start in week 2. Three chapter 02 items move to match chapter 01 and the CSVs:
- **AWS decision.** Chapter 02 shows the AWS decision on Oct 19; chapter 01 records DEC-03 on Decision Day. The landing zone (Q-01-T01) therefore starts Mon Oct 26. Both founders may sign DEC-03 earlier (it is a both-founder row), which would let Q-01-T01 start the day after.
- **Back-fill of deferred AC tests.** Chapter 02 puts tranche 1 in S0 and tranches 2–3 by Nov 20; chapter 01 and the CSVs fund the back-fill from the reserve in **Q-03 from S6**. In S0–S5 the reserve funds F-01 and 20 tasks of Q-01 instead. AY's S0 test work is the S0 tooling and adapter tests (F-01-T03, F-01-T11, Q-01-T12).
- **Staging target.** Chapter 02 infers "target Fri 13 Nov"; chapter 01 makes it M2. Same date.

### 7.2.1 Day-by-day plan

AY's day splits about 60/40 between code and the non-code programme (F-09: vendors, counsel, company, design partners). N's vendor share (F-09-T11) is the AWS-side requests and questionnaires.

| Day | N (notanaskhan) | AY (ayushkbhatia) | Joint, rituals and merges |
|---|---|---|---|
| **Mon Oct 19** (D1) | S0-01/02/03: F-01-T01 — secret scanning while the repo is still public, review and rotate; create the two-owner org on the Team plan, transfer, make private, ruleset phase 1. Then F-02-T02: ADR backlog and the ADR-116…130 reservation issues | F-01-T02: ADR-116 (P-02) two-founder governance text and the AGENTS.md governance sections. Non-code: F-09-T02 company, founder agreement and IP assignments; start F-09-T05 Intuit application | 09:00 **Contract Monday (S0)**: merge freeze announced, baseline tag `abacus-wedge-baseline`, protected bundle #1 contents agreed (fonts, table, virtualisation, WorkOS), number blocks confirmed |
| **Tue Oct 20** (D2) | S0-04/05: F-01-T04 hook fix (either founder approves, never the author; immutable only on `origin/main`) and CODEOWNERS catch-all, after AY's tests exist. Start F-01-T05 (stale assertions, coverage measured) | F-01-T03 independent AC tests for the hook, written from ADR-116 before T04 merges; F-02-T01 decision register. Non-code: F-09-T06 WK CCH application; F-09-T03 DEC-03 spend plan draft; F-09-T01 vendor tracker (repo now private) | **B1 17:00**: F-01-T01, F-01-T02, F-02-T01, F-02-T02 (merge only; no staging yet) |
| **Wed Oct 21** (D3) | S0-06/08: finish F-01-T05; F-01-T06 CI rebuild (stage 2 on `main`, shards re-recorded, caches, single Alembic head, `vite build`, ruleset phase 2 with required checks) | S0-07: F-01-T08 nightly e2e for the Setup-first flow; F-03-T03 P-34 draft (open by Thu). Non-code: F-09-T13 SOC 2 tool demos; F-09-T15 partner profile and target lists, outreach starts | 10:00 **Contract sync**: C1 stub scope; Decision Day pack outline |
| **Thu Oct 22** (D4) | Q-01-T02 TASK-014 plan plus ADR drafts P-55 (AWS topology) and P-54 (auth and sessions), open by today; F-03-T02 first five draft ADRs (P-38, P-04, P-05, P-39, P-36); F-02-T05 agenda pack | S0-17: F-02-T03 ADR-118 naming and the AGENTS.md mission paragraphs; open F-02-T04 glossary change-set PR (merge by Oct 30); start F-01-T11. Non-code: F-09-T08 DocuSign developer account; F-09-T14 discovery thresholds | **B2 17:00**: F-01-T03, F-01-T04, F-01-T05, F-01-T06, F-01-T08, F-02-T03, F-03-T03, Q-01-T02. After this batch the merge freeze lifts (S0-06 done) |
| **Fri Oct 23** (D5) | Afternoon: F-01-T07 path filters and frontend job; F-01-T09 worktree isolation and DB/deploy guard (start) | Afternoon: F-09-T03 DEC-03 recorded; F-09-T02 IP assignments filed; F-09-T05 Intuit and F-09-T06 WK submitted (both due today); continue F-01-T11 | 09:00–12:00 **Decision Day (M0)**: DEC-02, -03, -05, -22 decided; DEC-04/15 and DEC-11 (AY, S0); DEC-07, -08, -09, -27 (S1) owners and dates; DEC-14 and DEC-17 due Oct 30; DEC-25 draft. Default-on-silence except money, counsel and red-zone ADRs. Proposed additions from this chapter: the §7.5.4 re-balancing method and the M3 test-row measurement |
| **Mon Oct 26** (D6) | Q-01-T01 AWS landing zone (Control Tower, Identity Center with hardware-key MFA, member accounts, SCPs); finish F-01-T09; F-01-T10 number blocks | F-05-T01 ADR P-03 and the design-system SPEC (superseding SPEC-016 §4) before any token PR; F-03-T04 status-vocabulary YAML (start). Non-code: F-09-T04 counsel engagement letter; F-09-T10 WorkOS, Temporal, Sentry, Better Stack, GitHub Team order forms | — |
| **Tue Oct 27** (D7) | F-05-T02 allowlist bundle #1 and Q-01-T05 platform allowlist (protected bundle #1); F-03-T01 contract register C1–C21; F-02-T13 ADR-127 open today | Finish F-03-T04; F-05-T03 tokens (start). Non-code: F-09-T09 domains (neutral portal domain); F-09-T16 LOI template with counsel | **B3 17:00**: protected bundle #1 first (F-05-T02, Q-01-T05), then F-01-T07, F-01-T09, F-01-T10, F-01-T11, F-02-T05, F-03-T01, F-05-T01, Q-01-T01 |
| **Wed Oct 28** (D8) | Q-01-T03 Terraform bootstrap and infra CI; Q-01-T04 Temporal, WorkOS staging, SES production-access and Bedrock requests; F-09-T11 questionnaires; F-03-T02 remaining drafts (P-44, P-06, P-09, P-10) | F-05-T03 tokens; F-05-T05 base, motion and utilities CSS. Non-code: F-09-T12 check of N's questionnaire answers; partner calls | 10:00 **Contract sync**: C1 stub review; status YAML review |
| **Thu Oct 29** (D9) | F-03-T06 **C1 stub PR**; Q-01-T06 container image; Q-01-T07 `envs/shared`; F-02-T06 M1 orphan ADR drafts (P-26, P-17, P-29); Q-02-T01 compliance tracker | F-05-T09 `/components` gallery skeleton; Q-01-T12 independent AC tests for the KMS, SES and ClamAV adapters (written from P-55 and P-64 before the adapters land). Non-code: F-09-T13 SOC 2 tool contracted; ≥6 conversations booked | **B4 17:00**: F-02-T04 glossary (DEC-14), F-02-T06, F-02-T13, F-03-T02, F-03-T04, F-03-T06 (C1 stub), F-05-T03, F-05-T05, Q-01-T03, Q-01-T04, Q-01-T06, Q-02-T01 |
| **Fri Oct 30** (D10) | F-05-T04 fonts, F-05-T06 codemod, F-05-T07 lint rules; Q-01-T07 merge; Q-01-T10 ADR drafts P-45, P-64, P-67; Q-02-T03 Bedrock provider-terms draft for counsel; F-09-T17 **M1 check** recorded | F-05-T08 font and lint tests; Q-02-T02 AI threat model; every F-09 application filed (F-09-T07 Microsoft, F-09-T08 DocuSign, F-09-T10, F-09-T13, F-09-T16) | **B5 12:00**: F-05-T04, F-05-T06, F-05-T07, F-05-T08, F-05-T09, Q-01-T07, Q-01-T10, Q-01-T12, Q-02-T02, Q-02-T03. 14:00 **demo**; 15:00 **M1 exit check** |

**S0 demo (Fri Oct 30, local fixture mode, no staging yet).** (1) Governance drill: a self-approval, a direct push and an unreviewed protected-path change are all refused (F-01-T03). (2) A PR runs stage 1 and stages 1+2 as required checks, and a frontend-only PR finishes in ≤6 minutes (F-01-T06, T07). (3) Two worktrees run `make dev` side by side; a local production build against a shared database is refused (F-01-T09). (4) `/components/tokens` shows every token under both contrast ladders (F-05-T03, T09). (5) The C1 stub in the generated client returns 501 behind its flag (F-03-T06). (6) The decision log shows Decision Day's outcomes and owners (F-02-T05). (7) The vendor tracker shows every application filed with a date and a fallback (F-09-T01, T17).

**S0 exit check (M1).**

| M1 criterion (chapter 01 §1.2.1) | Tasks |
|---|---|
| History scanned and exposed secrets rotated; repo private in a two-owner org | F-01-T01 |
| Ruleset with the other founder's code-owner review; stages 1+2 required | F-01-T01, F-01-T06 |
| `_protected.py` fix merged; CODEOWNERS both handles | F-01-T02, F-01-T03, F-01-T04 |
| `main` green; nightly e2e repaired (three green nights from Thu Oct 22) | F-01-T05, F-01-T06, F-01-T08 |
| Decision Day recorded with owners | F-02-T01, F-02-T05 |
| ADR drafts: work items, request enum, scopes, roles, e-signature, P-29, write-capability framework | F-03-T02, F-03-T03, F-02-T06, Q-01-T02, Q-01-T10 |
| DS-S1 tokens merged | F-05-T01, F-05-T03, F-05-T05 |
| Protected bundle #1 (fonts, table, virtualisation, WorkOS) merged | F-05-T02, Q-01-T05 |
| Every vendor, assurance and counsel application filed with a dated ticket | F-09-T01, F-09-T04…T10, F-09-T11, F-09-T13, F-09-T17 |
| AWS organisation and Terraform state exist | Q-01-T01, Q-01-T03 |
| Named design-partner target list per window; ≥6 conversations booked | F-09-T15 |
| Glossary merged by Oct 30 (DEC-14) | F-02-T04 |

### 7.2.2 S0 capacity and task lists

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 13.5 | 73% | 5.4 / 10.7 | 0.0 / 0.0 | — | Q-01-T08, Q-01-T09, Q-01-T11 |
| AY (ayushkbhatia) | 11.1 | 10.5 | 95% | 3.2 / 3.5 | 0.0 / 0.0 | 11.2 / 10.8 | none |

N's planned pool looks light (73%) because most of N's S0 work is reserve-funded F-01 and the reserve-funded part of Q-01; together they overrun N's reserve by 5.4 tasks, so N's S0 coding (24.25 tasks without the two F-09 rows) is about 102% of N's gross coding time (23.8). Three adapter and build tasks (Q-01-T08, Q-01-T09, Q-01-T11) are therefore planned to land in S1 B1, where M2 still has room for them only if S1 is re-balanced (§7.3.1).

**N — 33 tasks, size 25.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-01-T01 | Baseline tag, full-history secret scan and rotation, org transfer, private repo … | 1 | reserve | B1 Tue 10/20 |
| F-01-T04 | _protected.py two-founder fix, CODEOWNERS catch-all and gaps … | 1 | reserve | B2 Thu 10/22 |
| F-01-T05 | Make main green: fix stale assertions against their spec ACs and measure coverage against … | 1 | reserve | B2 Thu 10/22 |
| F-01-T06 | CI rebuild: stage 2 on push to main and merge_group, ready-for-review gating, caches … | 1 | reserve | B2 Thu 10/22 |
| F-01-T07 | Path filters that report success for backend shards on frontend- or docs-only diffs … | 0.5 | reserve | B3 Tue 10/27 |
| F-01-T09 | Worktree isolation (compose project and port offset), no-Docker fixture dev target … | 1.5 | reserve | B3 Tue 10/27 |
| F-01-T10 | Number blocks and numbering protocol in validate_docs … | 0.5 | reserve | B3 Tue 10/27 |
| F-02-T02 | ADR programme: docs/adr/backlog.md (P-01..P-69 with drafter, approver, owning epic, number … | 0.5 | plan | B1 Tue 10/20 |
| F-02-T05 | Decision Day Fri Oct 23 (M0): agenda pack Thu Oct 22 with drafts linked … | 0.5 | plan | B3 Tue 10/27 |
| F-02-T06 | M1 orphan ADR drafts: ADR-125 (P-26) e-signature … | 0.5 | plan | B4 Thu 10/29 |
| F-02-T13 | ADR-127 (P-37) clock, scenario loader and synthetic marker, drafted from chapter 03 text for F-04 … | 0.25 | plan | B4 Thu 10/29 |
| F-03-T01 | Contract register: docs/contracts/README.md for C1–C21 … | 1 | plan | B3 Tue 10/27 |
| F-03-T02 | Draft N's F-03 ADRs from chapter 03 text: P-38, P-04, P-05, P-39, P-36 for Decision Day, then P-44 … | 1 | plan | B4 Thu 10/29 |
| F-03-T06 | C1 stub PR: work-item and lifecycle Pydantic models with classification tags, 501 route stubs … | 0.5 | plan | B4 Thu 10/29 |
| F-05-T02 | Allowlist bundle #1: Fontsource Geist/Geist Mono/Arimo/Gelasio, react-table, react-virtual … | 1 | plan | B3 Tue 10/27 |
| F-05-T04 | Self-hosted fonts: fonts.css (Geist and Geist Mono eager with preload), fonts-doc.css … | 0.5 | plan | B5 Fri 10/30 |
| F-05-T06 | Codemod DS-06 before the theme swap: bg-surface to bg-card first, spacing x4 … | 1 | plan | B5 Fri 10/30 |
| F-05-T07 | ESLint design-system rules (palette regex that admits Accrued tokens … | 1 | plan | B5 Fri 10/30 |
| F-09-T11 | notanaskhan's S0 vendor share: SES production access and Bedrock model access and quota requests … | 0.75 | non-code | — |
| F-09-T17 | Independent M1 check of F-09's S0 exit: every application filed, counsel engaged … | 0.5 | non-code | — |
| Q-01-T01 | AWS landing zone: Organizations, Control Tower, Identity Center with passkey or hardware-key MFA … | 1 | plan | B3 Tue 10/27 |
| Q-01-T02 | TASK-014 plan rewritten as 'Staging and production on AWS through Terraform' … | 1 | plan | B2 Thu 10/22 |
| Q-01-T03 | Terraform bootstrap and infra CI: infra/bootstrap … | 1 | plan | B4 Thu 10/29 |
| Q-01-T04 | Technical vendor set-up after F-09 contracts: Temporal Cloud account … | 0.5 | plan | B4 Thu 10/29 |
| Q-01-T05 | Platform allowlist PR (protected): workos approved … | 0.5 | plan | B3 Tue 10/27 |
| Q-01-T06 | Container image: backend/Dockerfile (multi-stage, uv sync --locked --no-dev … | 0.5 | plan | B4 Thu 10/29 |
| Q-01-T07 | Terraform envs/shared: ECR (immutable tags, scan on push, replication to production and us-west-2) … | 1 | plan | B5 Fri 10/30 |
| Q-01-T08 | Production adapters P1 and P2: KmsKeyService in kernel/crypto … | 1 | plan | carry ▲ |
| Q-01-T09 | Production adapters P3 and P4: SesTransport in communications/transport.py … | 1 | plan | carry ▲ |
| Q-01-T10 | ADR drafts P-45 unauthenticated operational routes … | 0.5 | plan | B5 Fri 10/30 |
| Q-01-T11 | Build once (ADR-088): build.yml on push to main builds the image once … | 1 | plan | carry ▲ |
| Q-02-T01 | Compliance programme set-up: docs/ops/compliance/README.md gate tracker … | 0.5 | plan | B4 Thu 10/29 |
| Q-02-T03 | Draft the Bedrock provider-terms entry for counsel … | 0.5 | plan | B5 Fri 10/30 |

**AY — 31 tasks, size 24.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-01-T02 | ADR-116 (P-02) two-founder governance text plus AGENTS.md, build-plan header, protected-paths.md … | 1 | reserve | B1 Tue 10/20 |
| F-01-T03 | Independent AC tests for the two-founder hook, origin/main immutability … | 0.5 | reserve | B2 Thu 10/22 |
| F-01-T08 | Repair the nightly e2e journey for the Setup-first flow with an idempotent seed step and … | 1 | reserve | B2 Thu 10/22 |
| F-01-T11 | Independent AC tests for the S0 CI and local-safety tooling … | 1 | reserve | B3 Tue 10/27 |
| F-02-T01 | Decision register: docs/product/decision-log.md with DEC-01..DEC-99 plus proposed DEC-100/101 … | 0.5 | plan | B1 Tue 10/20 |
| F-02-T03 | ADR-118 (P-01 product naming) plus the AGENTS.md mission, naming … | 0.5 | plan | B2 Thu 10/22 |
| F-02-T04 | Glossary change-set PR (DEC-14, chapter 09 section 9.5) … | 1 | plan | B4 Thu 10/29 |
| F-03-T03 | Draft AY's F-03 ADRs: P-34 status registry and codegen; P-28 entitlements and agent-minutes | 0.5 | plan | B2 Thu 10/22 |
| F-03-T04 | Author docs/product/status-vocabulary.yaml from blueprint 3.3.1 + addendum 3.2 + gap 6.5 … | 1.5 | plan | B4 Thu 10/29 |
| F-05-T01 | ADR P-03 and SPEC-1NN Accrued design system; seed tokens/DECISIONS.md conflict log | 1 | plan | B3 Tue 10/27 |
| F-05-T03 | Tokens: tokens.ts, theme.css (@theme static with namespace resets), root.css, contrast.css … | 1.5 | plan | B4 Thu 10/29 |
| F-05-T05 | base.css, motion.css, utilities.css (hairline, pane, well, tabular … | 0.5 | plan | B4 Thu 10/29 |
| F-05-T08 | Independent AC tests for the font and lint tasks (ADR-078) | 0.5 | plan | B5 Fri 10/30 |
| F-05-T09 | /components gallery skeleton (VITE_UI_GALLERY lazy subtree, specimen registry … | 1 | plan | B5 Fri 10/30 |
| F-09-T01 | Programme set-up: docs/ops/vendors/README.md tracker with one row and one vendor issue per chapter … | 1 | non-code | — |
| F-09-T02 | Company and legal foundation for M0 (RK-59): formation documents, founder agreement … | 0.5 | non-code | — |
| F-09-T03 | DEC-03 year-one external spend plan: envelope by line … | 0.5 | non-code | — |
| F-09-T04 | Counsel engagement with a dated scope batched by gate … | 1 | non-code | — |
| F-09-T05 | Intuit developer account, production-keys app assessment and App Partner Program tier application … | 0.75 | non-code | — |
| F-09-T06 | Wolters Kluwer CCH partner programme application … | 0.5 | non-code | — |
| F-09-T07 | Microsoft AI Cloud Partner Program enrolment and publisher verification of the multi-tenant Entra … | 0.5 | non-code | — |
| F-09-T08 | DocuSign developer account, Go-Live plan for the Nov 2 start and the Dec 4 go/no-go … | 0.5 | non-code | — |
| F-09-T09 | Domains: product domain, a neutral portal domain that never contains accrued … | 0.5 | non-code | — |
| F-09-T10 | Commercial terms for WorkOS (DEC-22 commercial part), Temporal Cloud, Sentry … | 0.5 | non-code | — |
| F-09-T12 | Independent check of notanaskhan's questionnaire answers against commercial terms … | 0.5 | non-code | — |
| F-09-T13 | SOC 2 compliance tool chosen and contracted (Drata recommended … | 1 | non-code | — |
| F-09-T14 | Discovery thresholds W1-W3 (and the build-plan section 4.1 blanks) in … | 1 | non-code | — |
| F-09-T15 | Partner profile and named target lists per window … | 1.5 | non-code | — |
| F-09-T16 | Non-binding LOI template: pilot windows on chapter 01 dates … | 0.5 | non-code | — |
| Q-01-T12 | Independent AC tests (ADR-078) for the KMS, keyring, SES and ClamAV adapters … | 1 | plan | B5 Fri 10/30 |
| Q-02-T02 | docs/architecture/ai-threat-model.md (ADR-064) … | 1 | plan | B5 Fri 10/30 |

*Pool:* `plan` = planned capacity; `reserve` = the 22.5% hardening reserve (F-01, Q-03, and 20 tasks of N's Q-01 shown as `plan` but charged pro rata to the reserve in the load figures); `support` = pilot-support reserve (Q-04); `non-code` = non-coding time (F-09; AY's programme, plus N's two S0 vendor rows). *Batch:* the window the PR merges in; `—` = not a PR (vault, calls, contracts); `carry ▲` = beyond capacity at plan velocity.

---

## 7.3 Sprints S1–S12

**How each sprint is laid out.** Goal and milestones; contracts handed over; capacity used against available (from the §7.5.1 model); each founder's full task list from the CSVs; merge batches; demo script; exit check; and the candidate re-balancing moves for that sprint. **Merge batches are simulated**, not guessed: each founder works through their tasks in dependency order at plan velocity (gross coding capacity ÷ 10 days), milestone-critical tasks first, and a PR merges in the first window after it finishes plus its review SLA (contract stubs same day, red half a day, amber one day). Tasks that finish after the last window are marked ▲: they carry into the next sprint unless the sprint is re-balanced. The candidate moves are generated by the method of §7.5.4 and are confirmed or rejected at each Contract Monday; none of them changes a chapter 01 date.

### 7.3.1 S1 · Mon Nov 2 – Nov 13, 2026 · Model migrations, contracts C1/C2 and R0 staging

**Goal.** Migrate the work-item model, lifecycle, binders and the request enum once, before any data; freeze C1 and C2; stand up R0 staging with WorkOS, SES and ClamAV; turn on the release train; ship the T0 primitives and status runtime.
**Milestone.** **M2 Fri Nov 13**: R0 staging; work-item and request-enum migrations; C1 and C2 frozen.
**Contracts handed over.** C1 v1 and C2 v1 recorded frozen (F-03-T19, consumer tests by AY in F-03's CI); C15 search slot reserved in the module pre-registration PR (F-03-T08); platform-ops contract v1 (Q-01-T13, internal to N's lane).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 24.8 | 135% **over** | 5.4 / 8.2 | 0.0 / 0.0 | — | F-03-T10, F-03-T14, F-03-T15, F-04-T02, F-05-T11, F-05-T13, F-05-T16, F-05-T17, Q-02-T06, Q-02-T07, Q-02-T08, Q-02-T10 |
| AY (ayushkbhatia) | 11.1 | 14.5 | 131% **over** | 3.2 / 1.0 | 0.0 / 0.0 | 11.2 / 11.0 | F-05-T10, F-05-T15, Q-02-T09 |

**N — 37 tasks, size 33.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-01-T12 | PR hygiene and S4 review-record checks: [mig NNNN] title, one migration per PR … | 1 | reserve | B1 Tue 11/3 |
| F-01-T13 | Release-train merge side: hold-for-batch and ship-now labels, merge-window status … | 1 | reserve | B2 Thu 11/5 |
| F-01-T14 | ADR P-56 release train and previews (amends ADR-088) plus docs/process/release-train.md | 0.5 | reserve | B1 Tue 11/3 |
| F-01-T15 | Escaped-defect log and weekly delivery-health summary … | 1 | reserve | B2 Thu 11/5 |
| F-02-T07 | L12 glossary identifier rule in banned_patterns.py generated from Don't-use columns with dated … | 0.5 | plan | B4 Thu 11/12 |
| F-02-T08 | Scope guards: protected docs/architecture/scope-guards.yaml … | 0.5 | plan | B4 Thu 11/12 |
| F-03-T05 | Migration 0056_work_items: work_items, work_item_assignments, assurance_work_items … | 1 | plan | B5 Fri 11/13 |
| F-03-T07 | Per-module registries (P-39): modules/<m>/registry.py collected for TABLE_OWNERS … | 1 | plan | B2 Thu 11/5 |
| F-03-T08 | Module pre-registration PR (P-05): 16 empty module packages … | 1 | plan | B4 Thu 11/12 |
| F-03-T09 | Status codegen (C2): abacus_tools/codegen/status_vocabulary.py emits kernel StrEnums and CHECK … | 1 | plan | B2 Thu 11/5 |
| F-03-T10 | Independent conformance tests for AY's status YAML (ADR-078) … | 0.5 | plan | carry ▲ |
| F-03-T12 | Migration 0057_engagement_lifecycle: 14-type CHECK with audit->fs_audit rewrite, service_line … | 1 | plan | B5 Fri 11/13 |
| F-03-T14 | Migration 0058_binders: request_lists gain work_item_id, name, kind, part … | 1 | plan | carry ▲ |
| F-03-T15 | Migration 0059_request_status_v2 and switch: rewrite codes per chapter 09 9.5.6, registry CHECK … | 1.5 | plan | carry ▲ |
| F-03-T18 | Contract-test CI: consumer tests under backend/tests/contracts/<C>/ and apps/web contract fixtures … | 1 | plan | B3 Tue 11/10 |
| F-04-T02 | kernel.clock core: now/today/system_now/frozen, tenant provider slot, production refusal | 1 | plan | carry ▲ |
| F-05-T11 | Independent format.ts AC suite: at least 60 cited golden cases, DST change and relative dates | 0.5 | plan | carry ▲ |
| F-05-T13 | Icon registry: 234 handoff kebab names to lucide-react 1.52.0 with DF-37 substitutes; custom glyphs … | 1 | plan | carry ▲ |
| F-05-T16 | Visual-parity harness: crop_handoff.py, Playwright visual project, tiers A to D … | 1.5 | plan | carry ▲ |
| F-05-T17 | CI frontend job: gallery screenshot regression on packages/ui changes, Tier A and D blocking … | 1 | plan | carry ▲ |
| F-09-T23 | Independent check of the technical facts in ayushkbhatia's counsel briefs … | 0.5 | non-code | — |
| Q-01-T13 | Platform-ops contract stub docs/contracts/platform-ops.md v1 … | 0.5 | plan | B4 Thu 11/12 |
| Q-01-T14 | Terraform staging network and data: VPC 10.20.0.0/16 … | 1.5 | plan | B1 Tue 11/3 |
| Q-01-T15 | Terraform staging compute and edge: ECS cluster and service module … | 1.5 | plan | B3 Tue 11/10 |
| Q-01-T16 | P-45 operational routes and middleware: /healthz and /readyz outside AbacusRouter on an explicit … | 1 | plan | B3 Tue 11/10 |
| Q-01-T17 | WorkOS base adapter (P-54) and staging identity … | 1 | plan | B3 Tue 11/10 |
| Q-01-T18 | Staging train deploy: deploy-staging.yml dispatched once after each F-01 merge window or by Ship … | 1.5 | plan | B3 Tue 11/10 |
| Q-01-T19 | Migration 00NN_platform_tenancy: firms.region … | 1 | plan | B3 Tue 11/10 |
| Q-01-T20 | R0 bring-up on staging: bootstrap task (bootstrap.sql, never bootstrap-local), first migrate … | 1 | plan | B4 Thu 11/12 |
| Q-01-T21 | R0 runbooks under docs/runbooks/: deploy and rollback (RB-01), failed migration … | 0.5 | plan | B3 Tue 11/10 |
| Q-01-T22 | ADR drafts P-65 tenant key provisioning and P-66 platform controls and kill switches … | 0.5 | plan | B1 Tue 11/3 |
| Q-02-T04 | SPEC-0NN Compliance kernel and real-data readiness … | 1 | plan | B4 Thu 11/12 |
| Q-02-T05 | Draft P-14 retention, holds, destruction: per record type x service line … | 0.5 | plan | B4 Thu 11/12 |
| Q-02-T06 | Protected bundle A: matrix rows firm.ai_client_data, engagement.ai_exclude … | 0.5 | plan | carry ▲ |
| Q-02-T07 | TASK-076 part 1 (SPEC-036): migration firms.ai_client_data_at/_by/_version, agent_stages … | 1 | plan | carry ▲ |
| Q-02-T08 | TASK-076 part 2: shadow filtering on every firm-facing read of specialist output … | 1 | plan | carry ▲ |
| Q-02-T10 | Compliance tool connected: every AWS account, the GitHub org, IAM Identity Center … | 0.5 | plan | carry ▲ |

**AY — 28 tasks, size 26.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-01-T16 | Independent AC tests for the S1 tooling (pr hygiene, review record, merge window and batch … | 1 | reserve | B1 Tue 11/3 |
| F-02-T09 | Frontend guards: apps/web/src/shell/nav.ts 13-item constant with nav.test.ts … | 0.5 | plan | B4 Thu 11/12 |
| F-02-T10 | Independent AC tests (ADR-078) for the L12 rule, ADR decider checks and scope-guard scans … | 0.5 | plan | B4 Thu 11/12 |
| F-02-T11 | C1 v1 consumer contract test, schema shape only … | 0.25 | plan | B1 Tue 11/3 |
| F-03-T11 | Tolerant status reader in the legacy web screens … | 0.5 | plan | B3 Tue 11/10 |
| F-03-T17 | Split apps/web/src/router.tsx into lazy area subtrees … | 1 | plan | B3 Tue 11/10 |
| F-03-T19 | Consumer contract tests for C1 and C2 (pytest against the stub … | 0.75 | plan | B3 Tue 11/10 |
| F-04-T01 | SPEC: Brightwater Hale scenario, epochs vs slices, holdouts and journey harness | 0.5 | plan | B3 Tue 11/10 |
| F-04-T03 | Frontend clock source chain: apps/web/src/app-core/clock.ts feeding F-05-T10's ClockProvider and … | 0.25 | plan | B3 Tue 11/10 |
| F-04-T04 | Fixture mode: fetch-swap over OpenAPI paths, personas (?as=), latency and never(), defineScenarios() | 1 | plan | B4 Thu 11/12 |
| F-04-T05 | Interim TS seed: E0 audit-core slice plus portal minimum … | 1 | plan | B4 Thu 11/12 |
| F-05-T10 | format.ts with bigint decimal parsing, Amount and DateText, ClockProvider and useNow in packages/ui | 1 | plan | carry ▲ |
| F-05-T12 | status.ts runtime over the C2 generated data; StatusPill, StatusDisc, SubLine, SyncChip, Tick … | 1.5 | plan | B2 Thu 11/5 |
| F-05-T14 | T0 primitives: Button and IconButton (opensDialog ellipsis), Pill, Count, Tick, Tag, DoneCount … | 1.5 | plan | B2 Thu 11/5 |
| F-05-T15 | Inputs and tabs: SearchField, FilterChip, Picker, ValueRow, Toggle, Radio, Checkbox, Fieldset, Menu … | 1.5 | plan | carry ▲ |
| F-09-T18 | Xero app and NetSuite SDN no-fee registrations or enquiries … | 0.5 | non-code | — |
| F-09-T19 | S1 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T20 | Discovery interviews wave 1 (at least 8: partners, managers … | 3 | non-code | — |
| F-09-T21 | Wave-1 notes anonymised (firm codes only) under docs/product/discovery/interviews/ and tagged … | 1 | non-code | — |
| F-09-T22 | Counsel early answers due Nov 13: DF-11 KBA three-failure path … | 1 | non-code | — |
| F-09-T24 | SOC 2 auditor RFP: Type I as of Mon Mar 1, 2027, Type II window May 1-Jul 31, March fieldwork slot … | 1 | non-code | — |
| F-09-T25 | SOC 2 policy set (ayushkbhatia's share of chapter 06 section 5.7) … | 1 | non-code | — |
| F-09-T26 | Pricing hypothesis instrument for proposed DEC-100 … | 1 | non-code | — |
| F-09-T27 | LOI outreach wave 1: walkthrough of the design-handoff prototypes by screen share … | 1.5 | non-code | — |
| F-09-T28 | Application follow-ups: Intuit assessment questions, Entra verification evidence … | 0.5 | non-code | — |
| Q-01-T23 | Runtime config for build once: app-core/runtime-config.ts loads /runtime-config.json before router … | 0.75 | plan | B5 Fri 11/13 |
| Q-01-T24 | Independent AC tests for the P-45 routes, middleware and WorkOS adapter … | 1 | plan | B3 Tue 11/10 |
| Q-02-T09 | Independent AC tests (ADR-078) for TASK-076 written from SPEC-036 … | 1 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Nov 3, 17:00 CT** · 6 PRs · no staging yet (merge only): Q-01-T14, F-01-T12, F-01-T14, F-01-T16, F-02-T11, Q-01-T22
- **B2 · Thu Nov 5, 17:00 CT** · 6 PRs · no staging yet (merge only): F-01-T13, F-01-T15, F-03-T07, F-03-T09, F-05-T12, F-05-T14
- **B3 · Tue Nov 10, 17:00 CT** · 13 PRs · no staging yet (merge only): F-03-T11, F-03-T17, F-03-T18, F-03-T19, F-04-T01, F-04-T03, Q-01-T15, Q-01-T16, Q-01-T17, Q-01-T18, Q-01-T19, Q-01-T21, Q-01-T24
- **B4 · Thu Nov 12, 17:00 CT** · 11 PRs · one staging deploy: F-02-T07, F-02-T08, F-02-T09, F-02-T10, F-03-T08, F-04-T04, F-04-T05, Q-01-T13, Q-01-T20, Q-02-T04, Q-02-T05
- **B5 · Fri Nov 13, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: F-03-T05, F-03-T12, Q-01-T23
- **Beyond capacity (▲)** · 15 tasks, 14.5 size: F-03-T10, F-03-T14, F-03-T15, F-04-T02, F-05-T10, F-05-T11, F-05-T13, F-05-T15, F-05-T16, F-05-T17, Q-02-T06, Q-02-T07, Q-02-T08, Q-02-T09, Q-02-T10

**Demo (Fri Nov 13, first staging build).** (1) Open staging: `/healthz` and `/readyz` answer outside the router (Q-01-T16); a staff member signs in through WorkOS staging (Q-01-T17). (2) Show the staging train: one deploy for the B4 batch, none per merge (Q-01-T18, F-01-T13). (3) Run `alembic heads` on staging after R0 bring-up: one head with 0056–0059 applied (F-03-T05, T12, T14, T15; Q-01-T20). (4) `make generate`: C2 codegen produces the kernel StrEnums and `status.ts`; the gallery shows StatusPill and the T0 primitives (F-03-T09, F-05-T12, T14). (5) Release-train labels and the merge-window status check on a live PR (F-01-T13). (6) TASK-076 firm AI opt-in with shadow filtering on a synthetic firm (Q-02-T07, T08).

**Exit check.** M2 met: Terraform staging, WorkOS, SES (sandbox plus production request filed) and ClamAV live; 0056–0059 applied on staging; C1 v1 and C2 v1 frozen in `docs/contracts/README.md`; router split into lazy subtrees (F-03-T17); escaped-defect log running (F-01-T15); ADR P-56 release train accepted (F-01-T14).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.0, AY 2.2
- Defer inside the chapter 01 window (2.0): F-05-T13→S9, Q-02-T09→S13
- Residual after these moves: N 8.2, AY 0.2 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.2 S2 · Mon Nov 16 – Nov 27, 2026 · Roles and grants, demo clock, production account, shell L1

**Goal.** Offices, teams, role catalogue and client access grants (P-09); engagement transitions and gates; the API list envelope; database business time and the tenant demo clock; production Terraform, DR pilot light and the canary workflow; observability; Bedrock route on staging; AppShell, overlays and toasts around the legacy screens.
**Milestone.** **M3 Fri Nov 20**: ≥2 signed LOIs and a named target list per window; first live ledger chosen (DEC-70, ADR-045); group-audit record (DEC-65); calibration #1. Thanksgiving week (capacity ×0.9).
**Contracts handed over.** C16 v1 notifications-half stub (P-01-T01).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 16.6 | 21.0 | 127% **over** | 4.8 / 3.7 | 0.0 / 0.0 | — | F-03-T13, F-03-T25, F-03-T26, F-03-T29, F-04-T06, F-04-T07, F-05-T22, F-05-T24, Q-01-T31, Q-02-T12 |
| AY (ayushkbhatia) | 10.0 | 14.2 | 143% **over** | 2.9 / 0.0 | 0.0 / 0.0 | 10.1 / 9.5 | F-03-T20, F-05-T20, F-05-T21, F-05-T23, P-01-T02 |

**N — 24 tasks, size 24.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-02-T12 | S1-S2 decision burn-down and close-out: DEC-20, DEC-46, DEC-64, DEC-65 and DEC-70 at M3 recorded … | 0.5 | plan | B1 Tue 11/17 |
| F-03-T13 | Engagement transitions and gates: engagements/transitions.py table, 409 illegal_transition … | 1.5 | plan | carry ▲ |
| F-03-T16 | Rename reminders/reminder_items to follow_up_schedules/follow_up_items and /reminders routes to … | 0.5 | plan | B1 Tue 11/17 |
| F-03-T23 | Offices, teams and membership attributes: organisations offices/teams/team_members … | 1 | plan | B1 Tue 11/17 |
| F-03-T24 | Matrix codegen: role catalogue; conditions level_in, function_in, scope_only, not_offshore … | 1.5 | plan | B2 Thu 11/19 |
| F-03-T25 | Client record and contacts: client kind/status/office/partner/risk_tier and derived … | 1 | plan | carry ▲ |
| F-03-T26 | client_access_grants (P-09): 12 roles x 9 scope kinds, document_classes, status and expiry … | 1.5 | plan | carry ▲ |
| F-03-T29 | API conventions kernel (P-36): kernel/listing.py list envelope with encrypted keyset cursors … | 1 | plan | carry ▲ |
| F-03-T38 | Draft ADR P-40 client-scoped files and cross-engagement fulfilment … | 0.25 | plan | B1 Tue 11/17 |
| F-04-T06 | Database business time: abacus_now(), switched defaults, audit_events.effective_at, firm_demo_clocks | 1.5 | plan | carry ▲ |
| F-04-T07 | Tenant demo-clock service, demo_clock.set matrix action, /v1/me server_now and clock_mode | 1 | plan | carry ▲ |
| F-05-T22 | Independent AC tests for E3 overlays, toasts and Undo | 1 | plan | carry ▲ |
| F-05-T24 | Accessibility harness: axe on every specimen and forced state, forced-colors emulation … | 1 | plan | carry ▲ |
| Q-01-T25 | Observability (P-67): ADOT to CloudWatch EMF and X-Ray, KMS-encrypted log groups … | 1 | plan | B2 Thu 11/19 |
| Q-01-T26 | Temporal Schedules for platform jobs: kernel.dispatch.schedule, pause, unpause and delete … | 1 | plan | B2 Thu 11/19 |
| Q-01-T27 | Tenant keys (P-65): abacus-worker-keyops service on the keyops queue … | 1.5 | plan | B3 Tue 11/24 |
| Q-01-T28 | Terraform production: envs/production from the same modules … | 1.5 | plan | B3 Tue 11/24 |
| Q-01-T29 | DR pilot light and AWS security baseline: envs/production-dr in us-west-2 … | 1 | plan | B3 Tue 11/24 |
| Q-01-T30 | CanaryWorkflow on a 15-minute Schedule (time_sensitive) as the canary staff identity … | 1.5 | plan | B3 Tue 11/24 |
| Q-01-T31 | Independent tests for AY's runtime-config and auth-config change (T23) | 0.5 | plan | carry ▲ |
| Q-02-T11 | Bedrock route on staging after R0 (Fri Nov 13) … | 0.5 | plan | B3 Tue 11/24 |
| Q-02-T12 | Bedrock reruns on synthetic data for evidence.upload_reviewer v3 and evidence.matcher v2 … | 1 | plan | carry ▲ |
| Q-02-T13 | Generated security tests part 1 (ADR-080): backend/tests/security/test_tenant_isolation.py … | 1.5 | plan | B3 Tue 11/24 |
| Q-02-T14 | Draft P-43: per-tenant hash-chain checkpoints … | 0.5 | plan | B1 Tue 11/17 |

**AY — 25 tasks, size 23.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-03-T20 | Independent AC tests (ADR-078) for work items, lifecycle, gate policy and slots … | 1 | plan | carry ▲ |
| F-04-T08 | Independent AC tests for kernel.clock, DB business time and the demo-clock service (ADR-078) | 1 | plan | B3 Tue 11/24 |
| F-04-T10 | Python scenario package skeleton: firm, people, clients, timeline, epochs, holdouts, slices … | 1.5 | plan | B3 Tue 11/24 |
| F-05-T18 | Shell L1: AppShell (firm, portal, framed), Toolbar with measured nav overflow, RecordHeader … | 1.5 | plan | B3 Tue 11/24 |
| F-05-T19 | View states and feedback: ViewState, EmptyState, Skeleton, ErrorRow, OfflineBanner, AgentRunningRow … | 1 | plan | B4 Wed 11/25 |
| F-05-T20 | E3 overlay stack O1 to O6: OverlayStack store, Popover, Drawer, SheetModal, FullSheet … | 1.5 | plan | carry ▲ |
| F-05-T21 | E3 toasts: ToastStore, ToastHost, useToast, running pill, toast.running in place … | 1 | plan | carry ▲ |
| F-05-T23 | Legacy re-skin M1: move the 51 screens into apps/web/src/legacy under current routes inside … | 1 | plan | carry ▲ |
| F-05-T25 | Skills setup PR: ui-kit-component, build-screen-from-handoff, updated frontend-feature … | 1 | plan | B2 Thu 11/19 |
| F-05-T26 | M3 calibration: log kit-task throughput for S1 and S2 and propose the F-05 cut tier if below 85 … | 0.5 | plan | B1 Tue 11/17 |
| F-09-T29 | S2 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T30 | Discovery interviews wave 2 (at least 15 in total) and retrievability tagging of at least 10 … | 2 | non-code | — |
| F-09-T31 | M3 discovery read: W1-W3 against thresholds, ledger distribution table and the DEC-70 … | 1 | non-code | — |
| F-09-T32 | M3 LOIs: at least 2 signed and a named target list per window, or the M3 fallback recorded | 1.5 | non-code | — |
| F-09-T33 | Google Workspace check across LOI and target firms and the Google OAuth and CASA go/no-go … | 0.5 | non-code | — |
| F-09-T34 | CPA advisor with audit and tax experience engaged … | 0.5 | non-code | — |
| F-09-T35 | SOC 2 vendor and sub-processor register (chapter 06 section 6.9) with DPAs and SOC reports … | 0.75 | non-code | — |
| F-09-T36 | SOC 2 auditor selected after an independence check, with both founders approving the spend | 0.75 | non-code | — |
| F-09-T37 | Pen-test RFP: CREST- or OSCP-staffed, multi-tenant SaaS experience, chapter 06 section 5.6 scope … | 0.75 | non-code | — |
| F-09-T38 | Counsel answers due Nov 27: retention floors (DEC-71, ADR P-14) … | 0.75 | non-code | — |
| F-09-T39 | Insurance broker engaged for cyber and tech E&O; submission data gathered … | 0.5 | non-code | — |
| P-01-T01 | C16 v1 stub, notifications half: v2 Pydantic models with classification tags … | 0.5 | plan | B1 Tue 11/17 |
| P-01-T02 | SHL-01 toolbar data: render from nav.ts, navArea active mapping … | 1 | plan | carry ▲ |
| Q-01-T32 | Deploy smoke spec apps/web/e2e/smoke/deploy-smoke.spec.ts in a staging Playwright project … | 1 | plan | B2 Thu 11/19 |
| Q-01-T58 | Independent AC tests (ADR-078) for CanaryWorkflow (T30), written from the Q-01 F6 text … | 0.75 | plan | B1 Tue 11/17 |

**Merge batches.**

- **B1 · Tue Nov 17, 17:00 CT** · 8 PRs · one staging deploy: F-02-T12, F-03-T16, F-03-T23, F-03-T38, F-05-T26, P-01-T01, Q-01-T58, Q-02-T14
- **B2 · Thu Nov 19, 17:00 CT** · 5 PRs · one staging deploy: F-03-T24, F-05-T25, Q-01-T25, Q-01-T26, Q-01-T32
- **B3 · Tue Nov 24, 17:00 CT** · 9 PRs · one staging deploy: F-04-T08, F-04-T10, F-05-T18, Q-01-T27, Q-01-T28, Q-01-T29, Q-01-T30, Q-02-T11, Q-02-T13
- **B4 · Wed Nov 25, 17:00 CT (sprint close, holiday week)** · 1 PRs · one staging deploy: F-05-T19
- **Beyond capacity (▲)** · 15 tasks, 16.5 size: F-03-T13, F-03-T20, F-03-T25, F-03-T26, F-03-T29, F-04-T06, F-04-T07, F-05-T20, F-05-T21, F-05-T22, F-05-T23, F-05-T24, P-01-T02, Q-01-T31, Q-02-T12

**Demo (Wed Nov 25).** (1) The 51 legacy screens render inside the new AppShell with the Toolbar and RecordHeader (F-05-T18, T23). (2) Set the tenant demo clock and watch `/v1/me` `server_now` and every "today" move together (F-04-T06, T07). (3) Matrix codegen emits the role catalogue and its conditions, and a client access grant with scope kind and expiry is created and read back (F-03-T24, T26; AY's independent tests F-03-T33 follow in S3). (4) Production Terraform applies from CI, and the canary workflow runs every 15 minutes on staging as the canary staff identity, ready for the production canary tenant in S3 (Q-01-T28, T30). (5) A screener call on synthetic data routes through Bedrock on staging (Q-02-T11, T12). (6) The M3 board: LOIs, ledger choice, group-audit NO-GO record, S1–S2 throughput (F-02-T12, F-05-T26, F-09).

**Exit check.** M3 recorded in the decision log; DEC-20, -46, -64, -65 and -70 closed (F-02-T12); kit-task throughput for S1–S2 logged and compared with 85% of plan (F-05-T26); **the ADR-078 test-row cost measured separately** (§7.7); production Terraform applies from CI.

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 1.1, AY 2.9
- Residual after these moves: N 3.3, AY 1.4 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.3 S3 · Mon Nov 30 – Dec 11, 2026 · R1 production, review-grammar schemas, C5 frozen

**Goal.** Production with the canary tenant, kill switches, restore drill, runbooks and status page, so SOC 2 controls operate from Dec 11; the four P-04 review-grammar migrations and C3 stubs 1–2; C5 v1 stub and freeze; entitlements, generalised `visible()`, `/v1/me` capabilities and C1 live; DataTable, IndexList and SplitLayout.
**Milestones.** DocuSign go/no-go Fri Dec 4 (DEC-25). **M4 Fri Dec 11**: R1 production with canary; SOC 2 controls operating; auditor engaged; pen test booked.
**Contracts handed over.** C3 schema v1 (stubs 1 and 2: P-04-T07, T08; consumer tests P-04-T09) frozen per the register's S3; C5 v1 stub (P-06-T01) frozen Fri Dec 11 (P-06-T02); C16 email-template half (P-01-T05).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 27.8 | 151% **over** | 5.4 / 4.0 | 0.0 / 0.0 | — | F-04-T11, F-04-T12, F-05-T31, P-01-T04, P-01-T05, P-06-T05, P-06-T06, Q-01-T41, Q-02-T16, Q-02-T17, Q-02-T18 |
| AY (ayushkbhatia) | 11.1 | 19.8 | 178% **over** | 3.2 / 0.0 | 0.0 / 0.0 | 11.2 / 10.0 | F-03-T33, F-05-T28, F-05-T29, F-05-T30, F-05-T33, P-01-T06, P-04-T02, P-06-T03 |

**N — 39 tasks, size 33.25**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-03-T22 | Minimal subtype tables for the other four kinds … | 1 | plan | B4 Thu 12/10 |
| F-03-T27 | Generalised visible() (P-06): scope kinds engagement, work_item, client, client_entity … | 1 | plan | B4 Thu 12/10 |
| F-03-T28 | Entitlements (P-28): platform plans and tenant_entitlements for attest, internal_audit, group_audit … | 1 | plan | B5 Fri 12/11 |
| F-03-T30 | /v1/me and /v1/me/capabilities: capabilities, role labels, flags, entitlements, office, tz … | 1 | plan | B5 Fri 12/11 |
| F-03-T31 | C1 live: implement the work-item routes and the engagement projection … | 1 | plan | B5 Fri 12/11 |
| F-04-T11 | Adopt kernel.clock in red modules and kernel (agents, connections, evidence, identity, ai_gateway) | 1 | plan | carry ▲ |
| F-04-T12 | Scenario-level golden-figure tests from blueprint and screen sources (ADR-078) | 1 | plan | carry ▲ |
| F-05-T31 | Independent INV-1 and INV-5 tests over every specimen | 0.5 | plan | carry ▲ |
| F-05-T34 | Retire Atelier tokens and fonts (DS-32): remove Source Sans 3 and Newsreader packages and allowlist … | 0.5 | plan | B5 Fri 12/11 |
| F-09-T43 | notanaskhan co-signs pen-test scope and rules of engagement … | 0.5 | non-code | — |
| F-09-T46 | notanaskhan checks that the DEC-100 packaging maps onto ADR P-28 entitlements and DEC-51 … | 0.5 | non-code | — |
| F-09-T49 | notanaskhan verifies every technical claim in Resource Pack v1 against the repo … | 0.5 | non-code | — |
| P-01-T04 | /v1/me v3 (initials, job title, firm region, time zone, seats, sandbox, offices, default office) … | 0.5 | plan | carry ▲ |
| P-01-T05 | C16 email-template half: communications email_templates with insert-only versions … | 0.5 | plan | carry ▲ |
| P-04-T01 | ADR P-07 Review grammar (ADR-133) and ADR P-35 Suggestions, proposals, approval grants and Undo … | 0.5 | plan | B1 Tue 12/1 |
| P-04-T03 | Migration NNNN_review_core: sign_offs (level, kind, content_hash … | 1 | plan | B3 Tue 12/8 |
| P-04-T04 | Migration NNNN_review_cards_checkpoints_issues … | 1 | plan | B3 Tue 12/8 |
| P-04-T05 | Migration NNNN_agent_suggestions_proposals (agents) … | 1 | plan | B3 Tue 12/8 |
| P-04-T06 | review package scaffolding: models with classification tags … | 1 | plan | B3 Tue 12/8 |
| P-04-T07 | C3 stub PR 1 (SHL-12 family): sign-off, review-note and human-gate Pydantic models … | 1 | plan | B3 Tue 12/8 |
| P-04-T08 | C3 stub PR 2 (SHL-10 and SHL-11 family): proposal … | 1 | plan | B3 Tue 12/8 |
| P-06-T01 | C5 v1 stub PR for the BND/SHL-14 family: Pydantic models with classification tags … | 1.25 | plan | B1 Tue 12/1 |
| P-06-T05 | Migration binder_engine: binder unpublish stamps, created_from, follow-up override, closed_at … | 1 | plan | carry ▲ |
| P-06-T06 | Idempotency-Key kernel (P-36): kernel/idempotency with a 24-hour replay store … | 0.75 | plan | carry ▲ |
| P-06-T28 | ADR P-31 Client withdrawal of unaccepted uploads … | 0.25 | plan | B5 Fri 12/11 |
| Q-01-T33 | SLOs as code (ADR-093): docs/ops/slos.md with the chapter 06 section 3.3 SLIs available today … | 1 | plan | B5 Fri 12/11 |
| Q-01-T34 | Production release path: deploy/production/release.json owned by both founders and make release-pr … | 1.5 | plan | B2 Thu 12/3 |
| Q-01-T35 | Production canary tenant through an ops request … | 0.5 | plan | B2 Thu 12/3 |
| Q-01-T36 | Kill switches part 1 (P-66): platform-wide AI pause checked in ai_gateway before any network call … | 1 | plan | B2 Thu 12/3 |
| Q-01-T37 | Kill switches part 2 (P-66): read-only mode per platform and per firm in AbacusRoute refusing … | 1 | plan | B2 Thu 12/3 |
| Q-01-T38 | Restore-drill tooling: abacus_tools.drill.verify … | 1 | plan | B2 Thu 12/3 |
| Q-01-T39 | First production restore drill and kill-switch game day … | 1 | plan | B3 Tue 12/8 |
| Q-01-T40 | R1 runbooks: RB-03, RB-06 to RB-12, RB-15, RB-20, RB-22, RB-23 … | 1 | plan | B1 Tue 12/1 |
| Q-01-T41 | Status page and on-call: Better Stack status page at status.<product-domain> … | 0.5 | plan | carry ▲ |
| Q-02-T15 | Generated security tests part 2: test_route_introspection.py … | 1 | plan | B3 Tue 12/8 |
| Q-02-T16 | Audit attribution migration and unit of work: audit_events gains engagement_id, work_item_id … | 1.5 | plan | carry ▲ |
| Q-02-T17 | Human-only guard: protected docs/architecture/human-only-actions.yaml … | 1 | plan | carry ▲ |
| Q-02-T18 | Bedrock entry live: provider-terms schema gains a second approver … | 0.5 | plan | carry ▲ |
| Q-02-T19 | Controls operating by Fri Dec 11 (M4): first quarterly access review … | 0.5 | plan | B3 Tue 12/8 |

**AY — 34 tasks, size 29.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-03-T21 | Independent AC tests (ADR-078) for binders and the request enum … | 1 | plan | B1 Tue 12/1 |
| F-03-T32 | app-core session hooks: useSession, useCan/<Can>, useFlag, useEntitlement … | 0.5 | plan | B5 Fri 12/11 |
| F-03-T33 | Independent AC tests (ADR-078) for roles, conditions, overrides, client record … | 1.5 | plan | carry ▲ |
| F-04-T13 | Scenario loader: service-API replay under frozen clock, settle barrier, local and staging modes … | 1.5 | plan | B3 Tue 12/8 |
| F-04-T14 | Route registry from the handoff link graph: seed-manifest.mjs, manifests, to.ID() builders … | 1 | plan | B3 Tue 12/8 |
| F-04-T15 | Make targets seed-demo, seed-staging, fixtures, journeys, journeys-full … | 0.5 | plan | B3 Tue 12/8 |
| F-04-T16 | Adopt kernel.clock in amber modules and tooling (engagements, communications, abacus_tools) | 0.5 | plan | B4 Thu 12/10 |
| F-05-T27 | E4 DataTable core: headless model on react-table, ledger grammar, MoneyCell, TickCell, PropChip … | 1.5 | plan | B4 Thu 12/10 |
| F-05-T28 | T1 IndexList with FilterBar and StatusTileRow on the list-envelope view model; states T1a to T1e | 1.5 | plan | carry ▲ |
| F-05-T29 | SplitLayout with 12 presets, ResizeGutter (16px keyboard steps, Enter resets … | 1 | plan | carry ▲ |
| F-05-T30 | Attribution and human-verb primitives: HumanAction, formatActor, AgentText restyle … | 1 | plan | carry ▲ |
| F-05-T33 | Specimen data from the F-04 Brightwater Hale seed at E0 … | 1 | plan | carry ▲ |
| F-09-T40 | S3 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T41 | DocuSign go/no-go on Fri Dec 4: Go-Live readiness, ID Verification commercial terms … | 1 | non-code | — |
| F-09-T42 | Pen-test vendor booked by Fri Dec 4: SOW for Feb 15-Mar 5 against production with retest by Apr 9 … | 0.75 | non-code | — |
| F-09-T44 | SOC 2 auditor engagement letter signed by Fri Dec 11 (M4) | 0.75 | non-code | — |
| F-09-T45 | Proposed DEC-100 decided at M4: packaging, list-price ranges, founding price … | 1.5 | non-code | — |
| F-09-T47 | Counsel review of the draft Bedrock provider-terms entry as the second approver … | 0.5 | non-code | — |
| F-09-T48 | Technology Resource Pack v1 draft (docs/ops/diligence/technology-resource-pack.md) … | 1 | non-code | — |
| F-09-T50 | Resource Pack v1 sent as a PDF from the vault to every LOI and target-list firm before their Dec 15 … | 1 | non-code | — |
| F-09-T51 | December discovery interviews with LOI firms on ledger, tax-engine and e-signature distribution … | 1.5 | non-code | — |
| F-09-T52 | Founding-partner agreement term sheet (chapter 01 section 1.6.4) … | 1 | non-code | — |
| F-09-T53 | Microsoft publisher verification close-out (target Dec 11) and Intuit assessment follow-up | 0.5 | non-code | — |
| P-01-T03 | Migration 00NN_notifications_v2: 0024's dotted-only kind CHECK dropped and re-created as … | 0.5 | plan | B3 Tue 12/8 |
| P-01-T06 | Notifications catalogue v2: register_kind slot, categories … | 1 | plan | carry ▲ |
| P-01-T07 | Scenario data: TS seed rows for SHL-03 and SHL-04 artboards … | 0.5 | plan | B3 Tue 12/8 |
| P-04-T02 | Status registry entries and glossary gap PR: sign-off slot, review note, issue … | 0.5 | plan | carry ▲ |
| P-04-T09 | C3 consumer contract tests for stubs 1 and 2: pytest against the stubs and TypeScript fixture … | 0.5 | plan | B4 Thu 12/10 |
| P-06-T02 | C5 consumer contract tests (pytest in backend/tests/contracts and TS fixture assertions) on behalf … | 0.5 | plan | B2 Thu 12/3 |
| P-06-T03 | Screen contracts docs/screens/{BND-01,BND-02,SHL-14,SHL-20}.md … | 0.5 | plan | carry ▲ |
| P-06-T04 | Glossary rows (protected): binder_recipient, request_upload_intent, screening_feedback … | 0.25 | plan | B3 Tue 12/8 |
| Q-01-T42 | Status-page content and incident templates: component names from the SHL-05 list, SEV1 … | 0.5 | plan | B2 Thu 12/3 |
| Q-01-T43 | Independent AC tests for schedules, tenant keys and platform controls (T26, T27, T36, T37) | 1.5 | plan | B2 Thu 12/3 |
| Q-01-T44 | Independent AC tests for the deploy, release, rollback and drill paths (T18, T34, T38) | 1 | plan | B2 Thu 12/3 |

**Merge batches.**

- **B1 · Tue Dec 1, 17:00 CT** · 4 PRs · one staging deploy: F-03-T21, P-04-T01, P-06-T01, Q-01-T40
- **B2 · Thu Dec 3, 17:00 CT** · 9 PRs · one staging deploy: P-06-T02, Q-01-T34, Q-01-T35, Q-01-T36, Q-01-T37, Q-01-T38, Q-01-T42, Q-01-T43, Q-01-T44
- **B3 · Tue Dec 8, 17:00 CT** · 15 PRs · one staging deploy: F-04-T13, F-04-T14, F-04-T15, P-01-T03, P-01-T07, P-04-T03, P-04-T04, P-04-T05, P-04-T06, P-04-T07, P-04-T08, P-06-T04, Q-01-T39, Q-02-T15, Q-02-T19
- **B4 · Thu Dec 10, 17:00 CT** · 5 PRs · one staging deploy: F-03-T22, F-03-T27, F-04-T16, F-05-T27, P-04-T09
- **B5 · Fri Dec 11, 12:00 CT (sprint close)** · 7 PRs · one staging deploy: F-05-T34, F-03-T28, F-03-T30, F-03-T31, F-03-T32, P-06-T28, Q-01-T33
- **Beyond capacity (▲)** · 19 tasks, 16.8 size: F-03-T33, F-04-T11, F-04-T12, F-05-T28, F-05-T29, F-05-T30, F-05-T31, F-05-T33, P-01-T04, P-01-T05, P-01-T06, P-04-T02, P-06-T03, P-06-T05, P-06-T06, Q-01-T41, Q-02-T16, Q-02-T17, Q-02-T18

**Demo (Fri Dec 11).** (1) Merge the first release PR: the other founder's approval triggers `deploy-production`, and the canary tenant "Canary & Co (synthetic)" answers (Q-01-T34, T35). (2) Kill-switch game day: platform AI pause and per-firm read-only mode refuse writes (Q-01-T36, T37, T39). (3) The restore-drill report: per-tenant row counts and the audit-event sequence verified (Q-01-T38, T39). (4) The status page and the on-call path (Q-01-T41, T42). (5) C1 live on staging: create a work item and read the engagement projection (F-03-T31). (6) An agent principal calling a human-only action gets 403 from the generated guard (Q-02-T17).

**Exit check.** M4 criteria met (production account with canary, SLO alarms, status page, paging, first restore drill, controls operating, auditor engaged, pen test booked); C3 schema v1 and C5 v1 frozen; first quarterly access review recorded (Q-02-T19); Bedrock provider-terms entry live with a second approver (Q-02-T18).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 1.4, AY 3.2
- Defer inside the chapter 01 window (0.5): P-04-T02→S14 (N)
- Residual after these moves: N 8.0, AY 5.0 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.4 S4 · Mon Dec 14 – Dec 25, 2026 · Flag renewals, family stubs, staff sign-in (holiday sprint)

**Goal.** The Dec 14–18 protected bundle (9 flag renewals, P-29 accepted); C3 stub 3; the clients, engagements and portal-identity family stubs; staff session BFF on hosted WorkOS AuthKit; tenant provisioning and SES identities; access events and the hash chain; portal layout, request kit and auth card; firm menu and notifications drawer.
**Milestones.** Dec 14–18 bundle (chapter 01 M4 row); SQMS 1 Technology Resource Pack to prospects by Dec 15 (F-09). Capacity ×0.6.
**Contracts handed over.** C3 stub 3, additive (P-04-T11, T12); C1 v1.1 clients and engagements family stubs (P-07-T04, T05; consumer tests P-07-T06); C5 v1.1 portal half (P-08-T01; consumer tests P-08-T02).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 11.1 | 17.8 | 161% **over** | 3.2 / 2.7 | 0.0 / 0.0 | — | F-04-T17, F-04-T18, F-04-T19, F-05-T39, P-01-T09, P-04-T10, P-04-T11, P-06-T07, P-07-T07, P-07-T66, Q-02-T20, Q-02-T21 |
| AY (ayushkbhatia) | 6.6 | 20.0 | 301% **over** | 1.9 / 0.0 | 0.0 / 0.0 | 6.7 / 5.5 | F-04-T20, F-04-T21, F-05-T35, F-05-T36, F-05-T37, P-01-T10, P-04-T12, P-06-T08, P-06-T09, P-07-T01, P-07-T03, P-07-T06, P-08-T02, P-08-T03, P-08-T04, Q-02-T22 |

**N — 24 tasks, size 20.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-03-T36 | Docs and skills: migration and backend-module skills, module READMEs … | 0.5 | plan | B1 Tue 12/15 |
| F-03-T37 | Dec 14–18 protected bundle: renew or retire the 9 flags expiring Jan 5–13, 2027 with handle owners … | 0.5 | plan | B1 Tue 12/15 |
| F-04-T17 | CLOCK-001 banned pattern and ESLint Date.now/new Date() ban | 0.5 | plan | carry ▲ |
| F-04-T18 | Scanner fake: LocalScanner verdict injection (infected, error, timeout, pending) | 0.5 | plan | carry ▲ |
| F-04-T19 | Fake-model scenario response registry keyed by prompt and document hash | 0.5 | plan | carry ▲ |
| F-05-T39 | White-label and portal-isolation tests: import-boundary lint for portal entries … | 1 | plan | carry ▲ |
| P-01-T09 | Staff session BFF on hosted WorkOS AuthKit: /v1/auth/sign-in, callback, refresh and sign-out … | 1 | plan | carry ▲ |
| P-04-T10 | Migration NNNN_approval_grants (identity) and identity.api issue_grant, consume_grant, void_grant … | 0.5 | plan | carry ▲ |
| P-04-T11 | C3 stub PR 3 (SHL-15, SHL-16 and SHL-09 family) … | 1 | plan | carry ▲ |
| P-06-T07 | Binder lifecycle service and routes: create (blank, template, prior-year via roll_forward.py) … | 1.25 | plan | carry ▲ |
| P-07-T04 | Clients family contract stub (organisations): classified Pydantic models and 501 routes for GET … | 1 | plan | B3 Tue 12/22 |
| P-07-T05 | Engagements family contract stub: index envelope with status tiles and service-line facets … | 1 | plan | B3 Tue 12/22 |
| P-07-T07 | Migration client_tin_relationships: sealed TIN columns … | 1 | plan | carry ▲ |
| P-07-T66 | ADR P-13 Independence and attest-client rules … | 0.5 | plan | carry ▲ |
| P-08-T01 | Portal identity and home contract stub PR (C5 v1.1 portal half) … | 1 | plan | B3 Tue 12/22 |
| Q-01-T45 | TenantProvisioningWorkflow v1 and operator CLIs … | 1.5 | plan | B2 Thu 12/17 |
| Q-01-T46 | SES events and suppression: configuration set to EventBridge to SQS … | 1 | plan | B2 Thu 12/17 |
| Q-01-T47 | SES per-firm sender identity port and staging mail sink … | 1 | plan | B3 Tue 12/22 |
| Q-01-T48 | Telemetry tunnel route POST /v1/telemetry/errors … | 0.75 | plan | B1 Tue 12/15 |
| Q-01-T49 | Opt-in preview builds (D-OPS-13): preview.yml only on the preview label runs vite build --mode … | 0.5 | plan | B3 Tue 12/22 |
| Q-01-T53 | Independent tests for AY's browser error reporting and the sub-processor register drift check … | 0.5 | plan | B3 Tue 12/22 |
| Q-01-T55 | Synthetic tenants for consumers through TenantProvisioningWorkflow … | 0.5 | plan | B3 Tue 12/22 |
| Q-02-T20 | access_events: monthly-partitioned insert-only table with forced RLS … | 1.5 | plan | carry ▲ |
| Q-02-T21 | Hash chain: audit_checkpoints insert-only; AuditCheckpointJob every 5 minutes with a settle window … | 1.5 | plan | carry ▲ |

**AY — 31 tasks, size 25.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-03-T34 | Independent AC tests (ADR-078) for entitlements, /v1/me capabilities … | 0.5 | plan | B1 Tue 12/15 |
| F-03-T35 | Foundation journey test backend/tests/integration/test_model_foundation_journey.py on the J02 data … | 1 | plan | B2 Thu 12/17 |
| F-04-T20 | E0 audit-core slice content: Northwind EBP, Granite Peak PBC, 25 shallow audits, portal users … | 1.5 | plan | carry ▲ |
| F-04-T21 | Journey harness core: assertInvariants UI layer, axeStep, persona adapters … | 1.5 | plan | carry ▲ |
| F-05-T35 | T7 PortalLayout (split, reduced, mobile), PortalToolbar, MobileTabBar with More sheet … | 1.5 | plan | carry ▲ |
| F-05-T36 | C-16 Request kit portal variant (RequestSection, RequestRow, CategoryRail, DropZone … | 1 | plan | carry ▲ |
| F-05-T37 | T15 AuthCard (400 card and 720 single page) with six code boxes … | 1 | plan | carry ▲ |
| F-09-T54 | S4 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T55 | LOI wave 2: convert remaining target-list firms so each window has its complement … | 1 | non-code | — |
| F-09-T56 | Pilot 0 plan: biweekly 60-minute session calendar per partner from Mon Jan 11 … | 1.5 | non-code | — |
| F-09-T57 | Cyber and tech E&O applications submitted through the broker with SOC 2 programme evidence | 1 | non-code | — |
| F-09-T58 | Counsel M7 brief: MSA, DPA (CCPA service provider, Safeguards flow-down, 72-hour incident notice … | 1 | non-code | — |
| F-09-T59 | Year-end spend review against the DEC-03 envelope (RK-05) and Q1 commitments | 0.5 | non-code | — |
| P-01-T08 | SHL-03 firm menu: O1 tray, person card, capability-gated admin rows, office submenu with PUT … | 1 | plan | B4 Wed 12/23 |
| P-01-T10 | SHL-04 drawer v2: O2 frame, segmented tabs with counts, day groups, kind glyphs incl. R2 … | 1.5 | plan | carry ▲ |
| P-04-T12 | C3 consumer tests for stub 3 (SHL-09 a-f, SHL-15 a-e, SHL-16 a-f shapes) … | 0.5 | plan | carry ▲ |
| P-06-T08 | Brightwater Hale binder slice in the scenario package … | 1 | plan | carry ▲ |
| P-06-T09 | BND-01 Binders index states a, c, d, e in fixture mode on T1 … | 1 | plan | carry ▲ |
| P-07-T01 | Screen contracts wave 1: docs/screens/{CLI-01,CLI-02,ENG-01,ENG-02,ENG-03}.md from the template … | 0.5 | plan | carry ▲ |
| P-07-T03 | Glossary and status-vocabulary rows (protected) … | 0.25 | plan | carry ▲ |
| P-07-T06 | Consumer contract tests for the clients and engagements stubs … | 0.5 | plan | carry ▲ |
| P-08-T02 | C5 portal-half consumer contract tests: pytest in backend/tests/contracts/c5_portal/ and TS fixture … | 0.5 | plan | carry ▲ |
| P-08-T03 | Screen contracts docs/screens/POR-01.md and POR-02.md … | 0.5 | plan | carry ▲ |
| P-08-T04 | Glossary rows (protected): portal_branding, portal_domain, portal_preferences, sign_in_challenge … | 0.25 | plan | carry ▲ |
| P-08-T30 | ADR P-11 White-label portal, domains, branded email … | 0.25 | plan | B3 Tue 12/22 |
| Q-01-T50 | Browser error reporting and error copy: @sentry/browser initialised from runtime config with … | 0.75 | plan | B2 Thu 12/17 |
| Q-01-T51 | Sub-processor register docs/operations/sub-processors.yaml … | 0.5 | plan | B3 Tue 12/22 |
| Q-01-T52 | Independent AC tests for tenant provisioning, entitlement CLI, SES events and the SES identity port … | 1 | plan | B3 Tue 12/22 |
| Q-01-T54 | Second-person runbook walkthrough (ADR-100): AY alone rolls back a staging release … | 0.5 | plan | B3 Tue 12/22 |
| Q-01-T59 | Independent AC tests (ADR-078) for the telemetry tunnel POST /v1/telemetry/errors (T48) … | 0.5 | plan | B2 Thu 12/17 |
| Q-02-T22 | Independent AC tests (ADR-078) for attribution, the dormant policy actor … | 1 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Dec 15, 17:00 CT** · 4 PRs · one staging deploy: F-03-T37, Q-01-T48, F-03-T34, F-03-T36
- **B2 · Thu Dec 17, 17:00 CT** · 5 PRs · one staging deploy: Q-01-T50, Q-01-T59, F-03-T35, Q-01-T45, Q-01-T46
- **B3 · Tue Dec 22, 17:00 CT** · 11 PRs · one staging deploy: P-07-T04, P-07-T05, P-08-T01, P-08-T30, Q-01-T47, Q-01-T49, Q-01-T51, Q-01-T52, Q-01-T53, Q-01-T54, Q-01-T55
- **B4 · Wed Dec 23, 17:00 CT (sprint close, holiday week)** · 1 PRs · one staging deploy: P-01-T08
- **Beyond capacity (▲)** · 28 tasks, 24.8 size: F-04-T17, F-04-T18, F-04-T19, F-04-T20, F-04-T21, F-05-T35, F-05-T36, F-05-T37, F-05-T39, P-01-T09, P-01-T10, P-04-T10, P-04-T11, P-04-T12, P-06-T07, P-06-T08, P-06-T09, P-07-T01, P-07-T03, P-07-T06, P-07-T07, P-07-T66, P-08-T02, P-08-T03, P-08-T04, Q-02-T20, Q-02-T21, Q-02-T22

**Demo (Wed Dec 23).** (1) `make check-fast` with the clock set to Jan 14, 2027 stays green: the 9 flags carry handle owners and new expiries (F-03-T37). (2) Staff sign-in through WorkOS AuthKit on staging, refresh and sign-out (P-01-T09). (3) Provision a synthetic tenant through TenantProvisioningWorkflow and see its SES sender identity in the mail sink (Q-01-T45, T47). (4) SHL-03 firm menu and SHL-04 notifications drawer in fixture mode (P-01-T08, T10). (5) T7 PortalLayout and the AuthCard specimen (F-05-T35, T37).

**Exit check.** Flags renewed before Dec 18; P-29 accepted; C3 stub 3 recorded additive by Fri Dec 18 (P-04-T12); access events written for reads of restricted rows (Q-02-T20); hash-chain checkpoints running every 5 minutes (Q-02-T21). AY's S4 load is the worst of PH1 (about 3× planned capacity); the carry list is long by design of the CSV and is the first target of §7.5.4.

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.5, AY 1.9
- Defer inside the chapter 01 window (0.2): P-07-T03→S13
- Residual after these moves: N 6.2, AY 11.2 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.5 S5 · Mon Dec 28 – Jan 8, 2027 · Trust kit stub, clients live, staging demo tenant (holiday sprint)

**Goal.** C4 stub and the trust-kit migration; request lifecycle v2 and the binders index read model; clients index and record live; portal branding and the WorkOS portal adapter; retention floors and Object Lock; T2 RecordCockpit, E1/E2 and DataTable grammars 2; BND-02, CLI-01 and POR-01 part 1 in fixture mode; the staging demo tenant loaded.
**Milestones.** C4 and C16 frozen (register S5). Capacity ×0.6.
**Contracts handed over.** C4 v1 stub (P-03-T02) with ADR P-48 accepted first (P-03-T27) and consumer tests (P-03-T03); C16 v1 frozen (P-01-T12).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 11.1 | 15.5 | 140% **over** | 3.2 / 0.7 | 0.0 / 0.0 | — | F-05-T42, P-07-T08, P-07-T09 |
| AY (ayushkbhatia) | 6.6 | 16.2 | 245% **over** | 1.9 / 0.0 | 0.0 / 0.0 | 6.7 / 5.0 | F-05-T41, F-05-T43, F-05-T44, P-03-T03, P-07-T11, P-07-T12, P-08-T08, P-08-T09, Q-02-T26, Q-02-T27 |

**N — 19 tasks, size 16.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-04-T23 | Independent AC tests for the synthetic mail sink (ADR-078) | 0.5 | plan | B4 Thu 1/7 |
| F-05-T42 | Independent AC tests for E1 and E2 | 0.5 | plan | carry ▲ |
| F-09-T65 | Technical answers for the DocuSign Go-Live review and the Intuit app assessment | 0.5 | non-code | — |
| P-01-T11 | Staff auth client in app-core/auth: in-memory access token, refresh via cookie … | 0.5 | plan | B3 Tue 1/5 |
| P-03-T01 | SPEC-0NN Trust kit v1 (citations v2, viewer, masked PII, unlock) … | 0.5 | plan | B3 Tue 1/5 |
| P-03-T02 | C4 stub PR: CitationV2 union of 10 kinds, CitationDisplay, ViewerManifest, regions, search, reveal … | 1.5 | plan | B3 Tue 1/5 |
| P-03-T04 | Migration trust_kit_v1: citations, citation_events, evidence_pages, pii_scan_runs, pii_regions … | 1 | plan | B4 Thu 1/7 |
| P-03-T27 | ADR P-48 Citation v2 and number provenance (ADR-144) drafted from chapter 03 section 3.7.2 and … | 0.5 | plan | B3 Tue 1/5 |
| P-06-T10 | Request lifecycle v2: extended create and patch, send with scope check … | 1.5 | plan | B3 Tue 1/5 |
| P-06-T11 | Binders index read model: service, season, office, preparer, client-activity … | 1 | plan | B3 Tue 1/5 |
| P-07-T08 | Clients index live: GET /v1/clients on the P-36 envelope through visible(scope=client) with 404 … | 1.5 | plan | carry ▲ |
| P-07-T09 | Client record and overview live: subbar facts and tab counts; per-kind overview … | 1 | plan | carry ▲ |
| P-08-T05 | Branding and host resolution: migration 00NN_portal_branding … | 1 | plan | B3 Tue 1/5 |
| P-08-T06 | WorkOS portal adapter port: user upsert, Magic Auth code issue and verify with the firm-branded … | 0.75 | plan | B1 Tue 12/29 |
| Q-01-T56 | Portal edge completion (OPS-14 part): portal distribution as a multi-tenant distribution with the … | 1 | plan | B1 Tue 12/29 |
| Q-01-T57 | Close-out docs and skills: infra/README.md final, docs/ops/environments.md … | 0.5 | plan | B1 Tue 12/29 |
| Q-02-T23 | Retention floors and policies: platform retention_floors … | 1.5 | plan | B5 Fri 1/8 |
| Q-02-T24 | Object Lock per record class: evidence/storage.py retain-until from the record's policy … | 1 | plan | B5 Fri 1/8 |
| Q-02-T25 | Draft P-12: TRI, phi and pii_kind field tags beside ADR-031's four levels … | 0.5 | plan | B1 Tue 12/29 |

**AY — 23 tasks, size 21.25**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-04-T22 | Synthetic mail sink rewrite and refusal, FakeSesTransport, local and staging mailbox readers | 1 | plan | B3 Tue 1/5 |
| F-04-T24 | Staging demo tenant: first E0 load via ECS run, offset demo clock at 9:24 AM CT, reset runbook | 1 | plan | B3 Tue 1/5 |
| F-05-T40 | T2 RecordCockpit frame: C-03 rail, C-04 record kit, canvas host, dock slot … | 1.5 | plan | B3 Tue 1/5 |
| F-05-T41 | E1 MatchProvider, E2 anchored popover host, C-07 CiteMarker and CitationChip visuals | 1.5 | plan | carry ▲ |
| F-05-T43 | DataTable grammars 2: statement and evidence, VarianceCell with five states, TallyStrip, AccountTree | 1 | plan | carry ▲ |
| F-05-T44 | Consumer contract tests (TypeScript fixture assertions in the provider's CI) for C2, C4 … | 0.5 | plan | carry ▲ |
| F-09-T60 | S5 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T61 | Pilot 0 readiness: session scripts over F-04's staging journeys, feedback form … | 1.5 | non-code | — |
| F-09-T62 | PW1-PW2 thresholds W4-W8 recorded in thresholds.md before Pilot 0 (chapter 11 section 11.8) | 0.5 | non-code | — |
| F-09-T63 | DocuSign ID Verification contract negotiation from Jan 4 (needed by Mar 31 for M8 criterion c) | 0.75 | non-code | — |
| F-09-T64 | Intuit production keys (target Jan 29) and DocuSign Go-Live review submission follow-ups | 0.5 | non-code | — |
| F-09-T66 | Founding-partner agreement first draft with counsel from the term sheet | 0.75 | non-code | — |
| F-09-T67 | Second-wave vendors only on discovery evidence … | 0.5 | non-code | — |
| P-01-T12 | Notification preferences API and email channel … | 1 | plan | B2 Wed 12/30 |
| P-03-T03 | C4 consumer contract tests: pytest against the stub in backend/tests/contracts/c04_citations_viewer/ | 0.5 | plan | carry ▲ |
| P-06-T12 | BND-02 states a-f: rail with categories and ticks, publish bar … | 2 | plan | B4 Thu 1/7 |
| P-07-T11 | Fixtures and scenarios wave 1: handlers apps/web/src/fixtures/handlers/{clients,engagements}.ts … | 1 | plan | carry ▲ |
| P-07-T12 | CLI-01 Clients index on T1: filter chips, search, header count, rows, Load more, row menu … | 1 | plan | carry ▲ |
| P-08-T07 | Portal build entry and shell data: apps/web/portal.html, src/entries/portal.tsx … | 1 | plan | B5 Fri 1/8 |
| P-08-T08 | Fixtures and scenarios: TS seed rows and fixture handlers for the portal routes … | 0.75 | plan | carry ▲ |
| P-08-T09 | POR-01 frontend part 1 on the F-05 AuthCard: a email entry with the 600 ms spinner, b code … | 1 | plan | carry ▲ |
| Q-02-T26 | Screener eval cases and labels from F-04 scenario documents … | 1 | plan | carry ▲ |
| Q-02-T27 | Independent AC tests (ADR-078) for the hash chain … | 0.5 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Dec 29, 17:00 CT** · 4 PRs · one staging deploy: P-08-T06, Q-01-T56, Q-01-T57, Q-02-T25
- **B2 · Wed Dec 30, 17:00 CT** · 1 PRs · one staging deploy: P-01-T12
- **B3 · Tue Jan 5, 17:00 CT** · 10 PRs · one staging deploy: F-04-T22, F-04-T24, F-05-T40, P-01-T11, P-03-T01, P-03-T02, P-03-T27, P-06-T10, P-06-T11, P-08-T05
- **B4 · Thu Jan 7, 17:00 CT** · 3 PRs · one staging deploy: F-04-T23, P-03-T04, P-06-T12
- **B5 · Fri Jan 8, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: P-08-T07, Q-02-T23, Q-02-T24
- **Beyond capacity (▲)** · 13 tasks, 11.8 size: F-05-T41, F-05-T42, F-05-T43, F-05-T44, P-03-T03, P-07-T08, P-07-T09, P-07-T11, P-07-T12, P-08-T08, P-08-T09, Q-02-T26, Q-02-T27

**Demo (Fri Jan 8).** (1) Brightwater Hale E0 loaded on staging with the demo clock at 9:24 AM CT (F-04-T24). (2) CLI-01 clients index live through `visible(scope=client)` with 404 semantics (P-07-T08, T12). (3) BND-02 binder states a–f in fixture mode (P-06-T12). (4) POR-01 email entry and code boxes on the AuthCard (P-08-T09). (5) A CitationChip rendering a C4 stub fixture (F-05-T41, P-03-T02).

**Exit check.** C4 v1 and C16 v1 frozen; staging tenant reloadable by runbook; Object Lock retain-until set from the record's policy (Q-02-T24); retention floors and policies tables in place (Q-02-T23), with counsel's content v1 following in S6 (Q-02-T31).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 1.0, AY 1.5
- Defer inside the chapter 01 window (1.5): P-07-T08→S15
- Residual after these moves: N 2.0, AY 8.1 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.6 S6 · Mon Jan 11 – Jan 22, 2027 · M5: the spine walkable on staging

**Goal.** Make the J02-audit-core and J12-core skeletons walkable on staging; lock DS tiers 0–1 at Tier A; firm-settings, contacts and screening stubs; follow-ups v2; portal sign-in BFF and portal home; screener's first real-model run on synthetic data; legal holds. Pilot 0 starts Mon Jan 11.
**Milestones.** PW0 from Mon Jan 11. **M5 Fri Jan 22**: platform spine walkable on staging; re-baseline #2.
**Contracts handed over.** C5 additive SHL-20 screening family (P-06-T15); firm-settings family stub (G-01-T02; consumer tests G-01-T03); contacts and portal-access stub (P-07-T17).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 22.0 | 119% **over** | 5.4 / 5.0 | 0.0 / 0.0 | — | F-05-T48, P-04-T15, P-07-T22, Q-03-T003, Q-03-T005, Q-03-T009 |
| AY (ayushkbhatia) | 11.1 | 21.2 | 192% **over** | 3.2 / 4.5 | 0.0 / 0.0 | 11.2 / 9.2 | F-04-T09, F-04-T25, F-05-T32, F-05-T47, F-05-T62, G-01-T01, G-01-T03, P-07-T19, P-07-T20, P-07-T21, Q-02-T31, Q-03-T001, Q-03-T002, Q-03-T006, Q-03-T007, Q-03-T008, Q-03-T010 |

**N — 29 tasks, size 27**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-04-T28 | CI wiring: paths-filtered PR fixture journeys and nightly fullstack and staging runs | 0.5 | plan | B3 Tue 1/19 |
| F-05-T48 | Independent AC tests for E5: hostile content and logged reveal | 0.5 | plan | carry ▲ |
| G-01-T02 | Firm-settings family contract stub: Pydantic models with classification, 501 routes … | 0.75 | plan | B2 Thu 1/14 |
| G-01-T04 | Typed settings registry and store (migration 00NN_firm_settings_v2) … | 1 | plan | B3 Tue 1/19 |
| P-01-T13 | Evidence decision Undo per DEC-24 and ADR P-35 … | 0.75 | plan | B1 Tue 1/12 |
| P-01-T14 | Independent AC tests (ADR-078) and C16 notifications-half contract tests for AY's amber work … | 1 | plan | B2 Thu 1/14 |
| P-03-T05 | Word-box layer: UploadProcessing patched step words … | 1.5 | plan | B3 Tue 1/19 |
| P-03-T06 | Citation v2 verifier registry evidence.register_citable with built-in verifiers document_text … | 1.5 | plan | B3 Tue 1/19 |
| P-04-T14 | Content hash and staleness: review.hashing canonical JSON under RFC 8785 rules … | 1 | plan | B5 Fri 1/22 |
| P-04-T15 | Matrix condition types not_preparer_of_target and reserved_role in … | 1 | plan | carry ▲ |
| P-06-T14 | Follow-ups v2: migration follow_ups_v2, template-composed drafts per contact without repeated items … | 1 | plan | B1 Tue 1/12 |
| P-06-T15 | SHL-20 family stub: screening aggregate, rerun, feedback and follow-up draft, edit and send shapes … | 0.5 | plan | B2 Thu 1/14 |
| P-06-T29 | ADR-078 golden-figure tests for AY's binder slice (T08), written in N's session … | 0.25 | plan | B2 Thu 1/14 |
| P-07-T10 | TIN seal, mask and reveal: organisations.api sealing with the per-tenant key … | 0.75 | plan | B4 Thu 1/21 |
| P-07-T15 | Engagements index and record live: ENG-01 read model … | 1.5 | plan | B4 Thu 1/21 |
| P-07-T16 | Engagement-type catalogue, wizard drafts and create … | 1.5 | plan | B5 Fri 1/22 |
| P-07-T17 | Contacts and portal-access contract stub: contact CRUD and roles per entity … | 0.5 | plan | B2 Thu 1/14 |
| P-07-T22 | Journey steps for M5: P-07 steps in apps/web/e2e/j02-client-onboarding.spec.ts … | 0.75 | plan | carry ▲ |
| P-08-T10 | Portal sign-in BFF core: migration 00NN_portal_sign_in … | 1.75 | plan | B1 Tue 1/12 |
| P-08-T11 | Portal auth client apps/web/src/app-core/auth/bff.ts … | 0.25 | plan | B2 Thu 1/14 |
| P-08-T16 | M5 journey steps on staging: j12 1 (Claire Feld signs in with an emailed code) and the home half of … | 0.25 | plan | B5 Fri 1/22 |
| Q-02-T28 | Screener first passing real-model run on synthetic data, direct then Bedrock … | 1.5 | plan | B3 Tue 1/19 |
| Q-02-T29 | Legal holds: legal_holds and reference-counted hold_objects … | 1.5 | plan | B4 Thu 1/21 |
| Q-02-T30 | Protected bundle B: matrix rows retention.read, retention_policy.manage … | 0.5 | plan | B2 Thu 1/14 |
| Q-03-T003 | Weekly quality report backend/src/abacus_tools/quality/report.py (new; protected path, AY approves) … | 1 | reserve | carry ▲ |
| Q-03-T004 | DAST (QD-9): protected allowlist PR adding the OWASP ZAP container under containers: … | 1 | reserve | B2 Thu 1/14 |
| Q-03-T005 | Call-off, only if F-01 applied its section 2.3 cut list … | 1 | reserve | carry ▲ |
| Q-03-T009 | S6 back-fill defect fixes: every failing AC from the S6 suites triaged as defect or spec drift in … | 1 | reserve | carry ▲ |
| Q-03-T011 | ADR-078 catch-up lane 2027 Q1: independent AC suites … | 1 | reserve | B2 Thu 1/14 |

**AY — 38 tasks, size 35**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| F-04-T09 | Seed contamination and canonical-name lint (DF-35 … | 0.5 | plan | carry ▲ |
| F-04-T25 | Scenario documents with fixed citation regions and fake-model response data; staging reload | 1 | plan | carry ▲ |
| F-04-T26 | J02-audit-core and J12-core skeleton journey specs | 1 | plan | B1 Tue 1/12 |
| F-04-T27 | WorkOS fake: hosted staff sign-in and portal email code with MFA and lockout | 1 | plan | B2 Thu 1/14 |
| F-05-T32 | Copy registry: defineCopy, copy/common.ts with firm and portal-safe variants, copy-registry.test.ts … | 0.5 | plan | carry ▲ |
| F-05-T38 | O6 wizard specimen TPL-18a to TPL-18e with a data-driven type catalogue and gate cards | 1 | plan | B2 Thu 1/14 |
| F-05-T45 | T12 SettingsLayout with step-up slot; T12a to T12d and TPL-12a to TPL-12e | 1 | plan | B3 Tue 1/19 |
| F-05-T46 | T11 DashboardLayout; T11a to T11f and TPL-11a to TPL-11f | 1.5 | plan | B3 Tue 1/19 |
| F-05-T47 | E5 SourceViewer shell (C-08): full and evidence variants, toolbar, server page images … | 1.5 | plan | carry ▲ |
| F-05-T49 | M5 lock: DS tiers 0 and 1 at Tier A (tokens, primitives, chrome strips) and Tier D … | 1 | plan | B3 Tue 1/19 |
| F-05-T62 | Independent AC tests (ADR-078) for N's CI frontend job (T17) … | 0.5 | plan | carry ▲ |
| F-09-T68 | S6 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T69 | Pilot 0 sessions wave A: J02-audit-core and J12-core skeletons on each partner's sandbox … | 3 | non-code | — |
| F-09-T70 | Pilot 0 usability log: findings filed as issues with screen ID, state letter … | 1 | non-code | — |
| F-09-T71 | Auditor relationship during readiness (Jan 4-Feb 26) … | 0.75 | non-code | — |
| F-09-T72 | Tax-partner track: CCH admin named, a list of 5-15 extended 1065 and 1040 returns sketched … | 1 | non-code | — |
| F-09-T73 | M5 partner checkpoint: Pilot 0 attendance, champion responsiveness … | 0.5 | non-code | — |
| F-09-T74 | Founding-partner agreement negotiation round 1 with each LOI firm … | 1.5 | non-code | — |
| F-09-T75 | Discovery synthesis docs/product/discovery/summary-2026.md … | 1 | non-code | — |
| G-01-T01 | Screen contracts docs/screens/ADM-01.md, ADM-02.md, ADM-03.md … | 0.5 | plan | carry ▲ |
| G-01-T03 | Consumer contract tests (pytest against the stub, TS fixture assertions) … | 0.5 | plan | carry ▲ |
| P-01-T16 | Wire-up and journeys: flags on for synthetic firms, manifest live, Tier C locks for SHL-03/04/06g … | 1 | plan | B2 Thu 1/14 |
| P-06-T13 | SHL-14 composer drawer states a, b, e, f plus revision items 1-5 … | 1.5 | plan | B3 Tue 1/19 |
| P-06-T16 | Follow-up sheet for BND-01 b and BND-02 d; fixture-to-live swap for BND-01 … | 0.75 | plan | B4 Thu 1/21 |
| P-07-T19 | CLI-02 Client record core on T2: subbar, tabs … | 1 | plan | carry ▲ |
| P-07-T20 | ENG-02 Engagement record core on T2 without dock … | 1 | plan | carry ▲ |
| P-07-T21 | ENG-03 wizard core on O6 for the audit and assurance family … | 1 | plan | carry ▲ |
| P-08-T12 | Client stage projection library modules/portal/stages.py … | 0.5 | plan | B4 Thu 1/21 |
| P-08-T13 | Portal home read model: GET /v1/portal/home and PUT /v1/portal/preferences composed through … | 1 | plan | B4 Thu 1/21 |
| P-08-T14 | Scenario slice in the Python loader: Brightwater Hale branding row and staging portal host … | 0.5 | plan | B5 Fri 1/22 |
| P-08-T15 | POR-02 frontend part 1 on T7: rail (household card, team rows with client-facing labels … | 1 | plan | B5 Fri 1/22 |
| Q-02-T31 | Retention floors content v1 per counsel (DEC-71, never defaults) … | 0.5 | plan | carry ▲ |
| Q-03-T001 | Q-03 programme set-up: reserve section in docs/product/capacity-ledger.md … | 0.5 | reserve | carry ▲ |
| Q-03-T002 | Back-fill tracker docs/quality/backfill.md: the 55 owed tasks … | 0.5 | reserve | carry ▲ |
| Q-03-T006 | Back-fill TASK-041 and TASK-045 (people and firm roles … | 1 | reserve | carry ▲ |
| Q-03-T007 | Back-fill TASK-030 and TASK-032 (client invitations and client users … | 1 | reserve | carry ▲ |
| Q-03-T008 | Back-fill TASK-040 and TASK-044 (self-serve sign-up and engagement types … | 1 | reserve | carry ▲ |
| Q-03-T010 | Skill .claude/skills/ac-test-author/SKILL.md (protected; N approves) … | 0.5 | reserve | carry ▲ |

**Merge batches.**

- **B1 · Tue Jan 12, 17:00 CT** · 4 PRs · one staging deploy: F-04-T26, P-01-T13, P-06-T14, P-08-T10
- **B2 · Thu Jan 14, 17:00 CT** · 12 PRs · one staging deploy: Q-02-T30, Q-03-T004, F-04-T27, F-05-T38, G-01-T02, P-01-T14, P-01-T16, P-06-T15, P-06-T29, P-07-T17, P-08-T11, Q-03-T011
- **B3 · Tue Jan 19, 17:00 CT** · 9 PRs · one staging deploy: F-04-T28, F-05-T45, F-05-T46, F-05-T49, G-01-T04, P-03-T05, P-03-T06, P-06-T13, Q-02-T28
- **B4 · Thu Jan 21, 17:00 CT** · 6 PRs · one staging deploy: P-06-T16, P-07-T10, P-07-T15, P-08-T12, P-08-T13, Q-02-T29
- **B5 · Fri Jan 22, 12:00 CT (sprint close)** · 5 PRs · one staging deploy: P-04-T14, P-07-T16, P-08-T14, P-08-T15, P-08-T16
- **Beyond capacity (▲)** · 23 tasks, 18.2 size: F-04-T09, F-04-T25, F-05-T32, F-05-T47, F-05-T48, F-05-T62, G-01-T01, G-01-T03, P-04-T15, P-07-T19, P-07-T20, P-07-T21, P-07-T22, Q-02-T31, Q-03-T001, Q-03-T002, Q-03-T003, Q-03-T005, Q-03-T006, Q-03-T007, Q-03-T008, Q-03-T009, Q-03-T010

**Demo (Fri Jan 22, the M5 walk).** J02 skeleton on staging, real WorkOS and SES, scanner live: (1) sign in as staff (F-04-T27 fake in fixture mode; WorkOS on staging); (2) create a client (CLI-02 record core, P-07-T19); (3) start an audit engagement through the ENG-03 wizard and record G1–G3 (P-07-T21, ENG-02 core P-07-T20); (4) create the binder and send a request (BND-01/02, follow-up sheet P-06-T16). J12 skeleton: (5) Claire Feld signs in with an emailed code (P-08-T10, T16), (6) lands on the portal home (P-08-T13, T15), (7) opens documents. Both runs assert INV-1…5 and axe (F-04-T26, P-07-T22).

**Exit check.** M5: R0 and R1 live with SLO alarms, status page, on-call and a passed restore drill; work-item, request-enum, client-grant, role, review-grammar and citation-v2 schemas migrated; every contract frozen on its register sprint so far (C1 and C2 in S1; C3 schema and C5 in S3; C4 and C16 in S5; chapter 01's PH1 exit also names C3 services, C6 and C13, which its own register freezes in S10–S12, see §7.5.5); DS tiers 0–1 at Tier A and axe AA (F-05-T49); J02-audit-core and J12-core skeletons walkable on staging; 9 flags renewed and P-29 accepted; Pilot 0 running since Jan 11. **Re-baseline #2:** planned-epic throughput S1–S5 per founder against the ledger — ≥90% hold; 80–90% cut tiers 1–2; <80% tier 3 (shadow Jun 15, R3 Jul 27).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.4, AY 0.0
- Defer inside the chapter 01 window (0.8): P-07-T22→S15
- Residual after these moves: N 2.4, AY 11.5 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.7 S7 · Mon Jan 25 – Feb 5, 2027 · PH2 opens: audits stub, viewer endpoints, portal MFA

**Goal.** Audits family stub and phase service; citations read API, viewer endpoints and v2 citations persisted by the three specialists; people v2 and ADM-01; G2 independence in authz; contacts and portal access live; portal MFA and invitations v2; client withdrawal with detached keys; classification flags and gateway PII refusal; incident register; Type I readiness and the pen-test environment; T3 EvidenceTriad, workpaper kit and the Northwind cockpit specimen; ENG-01; POR-03 part 1.
**Milestones.** AY's coding share rises to 75%. Threat-model refresh by Fri Feb 5 (Q-03-T018); pen-test readiness gate (Q-03-T019) ahead of the Feb 12 build pin.
**Contracts handed over.** Audits family stub with the C5 v1.1 audit fields (A-01-T02; consumer tests A-01-T03); C5 additive portal-pbc stub (R-01-T01; consumer tests R-01-T02); contacts and portal-access consumer tests (P-07-T18).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 21.0 | 114% **over** | 5.4 / 4.8 | 0.0 / 0.0 | — | G-01-T07, Q-03-T016, Q-03-T020 |
| AY (ayushkbhatia) | 13.8 | 26.0 | 188% **over** | 4.0 / 5.0 | 0.0 / 0.0 | 7.0 / 5.5 | F-05-T53, G-01-T06, P-03-T07, P-03-T11, P-07-T14, P-07-T23, P-07-T26, P-07-T27, P-07-T28, P-08-T19, P-08-T20, Q-02-T36, Q-03-T014, Q-03-T015, Q-03-T018, R-01-T02, R-01-T03, R-01-T05, R-01-T06 |

**N — 24 tasks, size 26.25**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T02 | Audits family contract stub: assurance Pydantic models with classification tags … | 1 | plan | B1 Tue 1/26 |
| A-01-T05 | Migration assurance_profile_phase and phase service … | 0.75 | plan | B2 Thu 1/28 |
| F-04-T29 | Loaded-state golden tests and loader AC tests (ADR-078) | 1 | plan | B1 Tue 1/26 |
| F-09-T79 | notanaskhan checks the DPA and MSA technical commitments … | 0.5 | non-code | — |
| G-01-T05 | People v2 (migration 00NN_people_v2): staff list on the envelope with bands and tallies … | 1.5 | plan | B4 Thu 2/4 |
| G-01-T07 | ADM-01 on the T12 frame: /settings area subtree, section list from the overview, fieldsets A-D … | 1 | plan | carry ▲ |
| P-03-T08 | Citations read API: GET /v1/citations/{id} display contract … | 1 | plan | B3 Tue 2/2 |
| P-03-T09 | Viewer endpoints: GET /v1/evidence-versions/{v}/viewer manifest, /pages/{n} … | 1.5 | plan | B3 Tue 2/2 |
| P-03-T10 | Persist screener, upload-reviewer and matcher citations as v2 rows … | 1 | plan | B3 Tue 2/2 |
| P-06-T18 | Detached-key storage for client-channel uploads (ADR-137) … | 1 | plan | B2 Thu 1/28 |
| P-06-T19 | Client withdrawal: withdraw route, void and hide from firm reads, agents … | 1 | plan | B2 Thu 1/28 |
| P-07-T24 | G2 v2 in identity authz (DEC-39, ADR P-13): the independence condition guards work assignment … | 1 | plan | B4 Thu 2/4 |
| P-07-T25 | Contacts and portal access live: contacts migration … | 1.5 | plan | B5 Fri 2/5 |
| P-08-T17 | Portal MFA: migration 00NN_portal_mfa (trusted_devices, mfa_backup_codes, portal_security_policies) … | 1.5 | plan | B3 Tue 2/2 |
| P-08-T18 | Invitations v2: migration 00NN_client_invitations_v2 … | 1 | plan | B3 Tue 2/2 |
| Q-02-T32 | Classification flags and gateway PII refusal: classified(level, tri=, phi= … | 1.5 | plan | B4 Thu 2/4 |
| Q-02-T33 | Incident register in platform: security_incidents … | 1.5 | plan | B5 Fri 2/5 |
| Q-02-T34 | Draft P-47: canonical run states with the legacy map … | 0.5 | plan | B2 Thu 1/28 |
| Q-02-T35 | Type I readiness and pen-test environment: readiness assessment in the tool … | 1 | plan | B2 Thu 1/28 |
| Q-03-T016 | S7 back-fill defect fixes for the portal, upload and request suites, red first … | 1 | reserve | carry ▲ |
| Q-03-T017 | OWASP ASVS Level 2 self-assessment of the pen-test build (inferred checklist) … | 1 | reserve | B2 Thu 1/28 |
| Q-03-T019 | Pen-test readiness gate (chapter 10 section 10.13) with Q-02-T35 … | 0.5 | reserve | B4 Thu 2/4 |
| Q-03-T020 | Integration and conflict lane 2027 Q1: batch-branch failures … | 2.25 | reserve | carry ▲ |
| R-01-T01 | C5 additive portal-pbc contract stub PR for the POR-03/04/14 family … | 0.75 | plan | B2 Thu 1/28 |

**AY — 43 tasks, size 36.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T01 | Screen contracts docs/screens/{AUD-01,AUD-02,AUD-03}.md … | 0.75 | plan | B2 Thu 1/28 |
| A-01-T03 | Consumer contract tests for the audits stub and the C5 v1.1 additive fields … | 0.5 | plan | B1 Tue 1/26 |
| A-01-T06 | Audit cockpit L3 in apps/web/src/domain/audits … | 0.5 | plan | B3 Tue 2/2 |
| F-04-T30 | Data-layer invariant checker INV-1 to INV-5 and harness self-tests with injected violations | 1 | plan | B2 Thu 1/28 |
| F-04-T31 | make fixtures export from the Python scenario and fixture vs seed-demo equivalence test | 1 | plan | B2 Thu 1/28 |
| F-04-T36 | Independent AC tests (ADR-078) for N's red F-04 tasks … | 1 | plan | B3 Tue 2/2 |
| F-05-T50 | C-02 Workpaper kit (WorkpaperPane, SectionBand … | 1 | plan | B3 Tue 2/2 |
| F-05-T51 | TPL-02a to TPL-02e Northwind 401(k) cockpit specimen | 1 | plan | B3 Tue 2/2 |
| F-05-T52 | DataTable grammars 3: grid and leadsheet fields, virtualisation above 200 rows | 1.5 | plan | B5 Fri 2/5 |
| F-05-T53 | T3 EvidenceTriad (Review, Prepare and Two-pane presets in a MatchScope); states T3a to T3e | 1.5 | plan | carry ▲ |
| F-09-T76 | S7 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T77 | Pilot 0 sessions wave B: J02 and J12 retests, the first partner PBC template imported through the … | 2 | non-code | — |
| F-09-T78 | Counsel M7 drafts received by Fri Jan 29 and reviewed … | 1.5 | non-code | — |
| F-09-T80 | Insurance quotes compared and a carrier selected for binding by Mar 31 | 0.5 | non-code | — |
| F-09-T81 | Intuit production keys (Jan 29) and DocuSign Go-Live (Jan 29) close-out or fallback | 0.5 | non-code | — |
| F-09-T82 | Founding-price validation in Pilot 0 conversations and the first champion feedback on packaging | 0.5 | non-code | — |
| G-01-T06 | Seed slice and fixtures: Python scenario slice … | 1 | plan | carry ▲ |
| P-01-T15 | Independent AC tests (ADR-078) and C16 email-half contract tests for N's red work … | 1 | plan | B1 Tue 1/26 |
| P-01-T17 | Docs and runbooks: docs/screens SHL-01/03/04/06 with Deviations … | 0.5 | plan | B2 Thu 1/28 |
| P-03-T07 | Fixture scenarios screens/SHL-07 (a-e) and screens/SHL-08 … | 1 | plan | carry ▲ |
| P-03-T11 | SHL-07 CitationPopover container: single (a), stack with stepper, ghost edges and page thumb … | 1 | plan | carry ▲ |
| P-04-T13 | Independent AC tests (ADR-078) for the four P-04 migrations … | 1.25 | plan | B1 Tue 1/26 |
| P-06-T17 | ADR-078 independent AC tests for T05, T06, T07, T10 and T11, including the model-text send refusal … | 1 | plan | B4 Thu 2/4 |
| P-07-T02 | SPEC-1NN Acceptance, independence and conflicts performed in-app, superseding SPEC-025's non-goals … | 0.5 | plan | B4 Thu 2/4 |
| P-07-T14 | Independent AC tests (ADR-078) for T15-T16: tiles foot to the total … | 0.75 | plan | carry ▲ |
| P-07-T18 | Consumer contract tests for the contacts and portal-access stub … | 0.25 | plan | B4 Thu 2/4 |
| P-07-T23 | Screen contracts wave 2: CLI-04 (DF-24 lockout copy), CLI-06 … | 0.5 | plan | carry ▲ |
| P-07-T26 | Independent AC tests (ADR-078) for T24-T25: third party limited to delegated items … | 1 | plan | carry ▲ |
| P-07-T27 | ENG-01 Engagements index on T1: service-line segmented, seven status tiles that filter and foot … | 0.75 | plan | carry ▲ |
| P-07-T28 | ENG-02 remaining: CAS variant a, Work items tab from kind providers, Team tab host … | 0.5 | plan | carry ▲ |
| P-08-T19 | POR-01 frontend part 2: c two-step (authenticator code, trust-device toggle, backup code path) … | 0.75 | plan | carry ▲ |
| P-08-T20 | Independent AC tests (ADR-078) for T05, T06, T10 and T11 … | 1 | plan | carry ▲ |
| Q-02-T36 | Independent AC tests (ADR-078) for retention and holds … | 1 | plan | carry ▲ |
| Q-03-T012 | Security file backend/tests/security/test_walls_and_need_to_know.py … | 1.5 | reserve | B3 Tue 2/2 |
| Q-03-T013 | Security file test_upload_hostile_files.py: EICAR, zip bombs, polyglots, PDFs with JavaScript … | 1 | reserve | B4 Thu 2/4 |
| Q-03-T014 | Back-fill TASK-035 and TASK-056 (portal item visibility and client uploads … | 1 | reserve | carry ▲ |
| Q-03-T015 | Back-fill TASK-054 and TASK-055 (upload processing parts 1-2 … | 1 | reserve | carry ▲ |
| Q-03-T018 | Threat-model refresh of docs/architecture/ai-threat-model.md for pen test #1 … | 0.5 | reserve | carry ▲ |
| R-01-T02 | C5 portal-pbc consumer contract tests on behalf of R-01, T-02, C-01 and A-09 … | 0.25 | plan | carry ▲ |
| R-01-T03 | Screen contracts docs/screens/POR-03.md, POR-04.md, POR-14.md, POR-20.md and ADM-10.md … | 0.5 | plan | carry ▲ |
| R-01-T04 | Glossary rows (protected): email_template_draft, email_template_version … | 0.25 | plan | B4 Thu 2/4 |
| R-01-T05 | TS fixtures and scenarios for POR-03 (12 artboards), POR-04 (7) and POR-14 (6) … | 0.5 | plan | carry ▲ |
| R-01-T06 | POR-03 frontend part 1 in fixture mode on T7 and the C-16 Request kit … | 1 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Jan 26, 17:00 CT** · 5 PRs · one staging deploy: A-01-T02, A-01-T03, F-04-T29, P-01-T15, P-04-T13
- **B2 · Thu Jan 28, 17:00 CT** · 11 PRs · one staging deploy: A-01-T01, A-01-T05, F-04-T30, F-04-T31, P-01-T17, P-06-T18, P-06-T19, Q-02-T34, Q-02-T35, Q-03-T017, R-01-T01
- **B3 · Tue Feb 2, 17:00 CT** · 10 PRs · one staging deploy: A-01-T06, F-04-T36, F-05-T50, F-05-T51, P-03-T08, P-03-T09, P-03-T10, P-08-T17, P-08-T18, Q-03-T012
- **B4 · Thu Feb 4, 17:00 CT** · 9 PRs · one staging deploy: G-01-T05, P-06-T17, P-07-T02, P-07-T18, P-07-T24, Q-02-T32, Q-03-T013, Q-03-T019, R-01-T04
- **B5 · Fri Feb 5, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: F-05-T52, P-07-T25, Q-02-T33
- **Beyond capacity (▲)** · 22 tasks, 19.8 size: F-05-T53, G-01-T06, G-01-T07, P-03-T07, P-03-T11, P-07-T14, P-07-T23, P-07-T26, P-07-T27, P-07-T28, P-08-T19, P-08-T20, Q-02-T36, Q-03-T014, Q-03-T015, Q-03-T016, Q-03-T018, Q-03-T020, R-01-T02, R-01-T03, R-01-T05, R-01-T06

**Demo (Fri Feb 5).** (1) ENG-01 engagements index: seven status tiles that filter and foot (P-07-T27). (2) SHL-07 citation popover over a v2 citation from the screener (P-03-T10, T11). (3) POR-01 two-step with authenticator code and trusted device (P-08-T17, T19). (4) ADM-01 firm settings on the T12 frame (G-01-T07). (5) A client withdraws an unaccepted upload; it disappears from firm reads, agents and exports (P-06-T18, T19). (6) The gateway refuses a classified PII field (Q-02-T32).

**Exit check.** Pen-test environment ready and the build pin date agreed (Q-02-T35, Q-03-T019); C5 additive fields green in N's CI; P-04 migration AC tests by AY pass (P-04-T13).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.6, AY 0.0
- Defer inside the chapter 01 window (0.2): R-01-T04→S14 (N)
- Residual after these moves: N 1.9, AY 12.9 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.8 S8 · Mon Feb 8 – Feb 19, 2027 · Audit cockpit, C9 stub, walls v2, viewer (pen test starts)

**Goal.** AUD-01 index read model and cockpit projection; C9 v1 stub and the TB-of-record migration; walls v2 and offshore fail-closed; ADM-02 users; moved and broken citation detection; PII detection by code; the human-gate projector; screening aggregate; team and roles backend; secure links; MFA overlay; WISP v1; AUD-01 and AUD-02 screens; SHL-08 viewer on two hosts; SHL-20 screening card; CLI-04; POR-03 part 2.
**Milestones.** Pen test #1 begins Mon Feb 15.
**Contracts handed over.** C9 v1 stub (A-02-T03); G-02 incident and firm-export stub (Q-02-T38); team, acceptance, independence and conflict stubs (P-07-T29; consumer tests P-07-T31).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 21.0 | 114% **over** | 5.4 / 5.0 | 0.0 / 0.0 | — | Q-03-T025, Q-03-T027, Q-03-T028, Q-03-T029 |
| AY (ayushkbhatia) | 13.8 | 25.5 | 184% **over** | 4.0 / 3.5 | 0.0 / 0.0 | 7.0 / 6.0 | A-02-T05, P-07-T13, P-07-T32, P-07-T33, P-07-T34, Q-02-T39, Q-02-T52, Q-03-T021, Q-03-T022, Q-03-T023, Q-03-T024, R-01-T07, R-01-T08, R-01-T10, R-01-T11 |

**N — 27 tasks, size 26**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T08 | AUD-01 index read model GET /v1/audits: tiles minus tile, segments, caption, facets, filters … | 1.25 | plan | B3 Tue 2/16 |
| A-01-T09 | Cockpit projection and A-01 providers (Overview links, Source Documents, Team … | 0.75 | plan | B3 Tue 2/16 |
| A-01-T10 | C5 v1.1 additive fields on the P-06 binder-requests projection … | 0.75 | plan | B2 Thu 2/11 |
| A-02-T01 | Gate check and SPEC-0NN Trial balance & ledger connections … | 0.5 | plan | B2 Thu 2/11 |
| A-02-T02 | Protected bundle: matrix sections (ledger, assurance TB, workpapers ties, connections … | 0.5 | plan | B2 Thu 2/11 |
| A-02-T03 | C9 v1 contract stub (AUD-06 family): classified Pydantic models for TB list, view by layer … | 0.5 | plan | B2 Thu 2/11 |
| A-02-T04 | Migration ledger TB of record: ledger_snapshots.label and generated source_kind, trial_balances … | 0.5 | plan | B4 Thu 2/18 |
| G-01-T08 | Offices, teams and groups (migration 00NN_org_v2) … | 0.75 | plan | B3 Tue 2/16 |
| G-01-T09 | Walls v2 and offshore fail-closed (migration 00NN_walls_v2) … | 1.5 | plan | B3 Tue 2/16 |
| G-01-T10 | ADM-02: Users table with bands, tally strip and filters … | 1.5 | plan | B4 Thu 2/18 |
| P-03-T12 | Moved and broken detection: outbox consumer on superseding evidence versions … | 1 | plan | B3 Tue 2/16 |
| P-03-T13 | PII detection by code: UploadProcessing patched step pii_scan over the word layer … | 1.5 | plan | B1 Tue 2/9 |
| P-04-T16 | Human-gate projector (outbox consumer, idempotent on event_id), register_gate_kind … | 1 | plan | B5 Fri 2/19 |
| P-06-T20 | Screening aggregate (DEC-48): migration screening_named_checks … | 1 | plan | B1 Tue 2/9 |
| P-07-T29 | Team, acceptance, independence and conflict contract stubs (engagements and organisations) … | 0.75 | plan | B2 Thu 2/11 |
| P-07-T30 | Team and roles backend (ENG-05): team_roles migration … | 1 | plan | B4 Thu 2/18 |
| P-08-T21 | Secure links and recovery: migration 00NN_secure_links … | 1 | plan | B3 Tue 2/16 |
| P-08-T22 | Independent AC tests (ADR-078) for AY's amber work T07, T12, T13 and T14 … | 0.75 | plan | B3 Tue 2/16 |
| Q-02-T37 | MFA enforcement overlay: lint and generated test that every action in fresh-mfa-actions.yaml … | 1 | plan | B4 Thu 2/18 |
| Q-02-T38 | Contract stub PR for G-02 (and Q-05 reads): incident create with clock fields, firm-export request … | 1 | plan | B1 Tue 2/9 |
| Q-02-T40 | Accrued WISP v1 (16 CFR 314.4 (a)-(j) per chapter 06 section 5.8 … | 1 | plan | B2 Thu 2/11 |
| Q-03-T025 | S8 back-fill defect fixes for connections, ledger and GL suites | 1 | reserve | carry ▲ |
| Q-03-T026 | Mutation wiring (ADR-079): mutmut nightly incremental over red files changed in 24 h … | 1.5 | reserve | B5 Fri 2/19 |
| Q-03-T027 | Protected thresholds file backend/mutation-thresholds.yaml … | 0.5 | reserve | carry ▲ |
| Q-03-T028 | Plan tests on a 10k-row synthetic fixture for the top 20 list endpoints asserting the composite … | 1 | reserve | carry ▲ |
| Q-03-T029 | Supply-chain hygiene 2027 Q1: pip-audit, bandit, Trivy … | 1 | reserve | carry ▲ |
| R-01-T09 | Portal drop sort and upload limits (evidence, red) … | 1.5 | plan | B4 Thu 2/18 |

**AY — 36 tasks, size 35**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T07 | Brightwater Hale assurance slice through A-01 service APIs … | 0.5 | plan | B2 Thu 2/11 |
| A-01-T11 | AUD-01 screen on T1 with the R2 tabs bar: states a-f live, g and h as fixture scenarios, tiles … | 1.25 | plan | B2 Thu 2/11 |
| A-01-T12 | AUD-02 screen: cockpit with the Source Documents canvas, Viewer dock tab … | 1 | plan | B3 Tue 2/16 |
| A-02-T05 | AUD-06 fixture scenarios a-h plus loading, empty, newer-TB … | 0.5 | plan | carry ▲ |
| F-04-T32 | J04-PBC slice and J01-core skeleton specs plus Pilot 0 PBC top-up at the Sep 24 snapshot | 1 | plan | B1 Tue 2/9 |
| F-04-T33 | Local screen parity report from the manifest (parity.json and HTML) | 1 | plan | B1 Tue 2/9 |
| F-05-T54 | TPL-03a to TPL-03e Feld 1040 review specimen | 1 | plan | B3 Tue 2/16 |
| F-05-T55 | T9 QueueDetailLayout (issues-individual, close-review, issues-entity) and C-17 Issue kit visuals … | 1.5 | plan | B3 Tue 2/16 |
| F-05-T56 | T8 InboxLayout and C-15/C-18 File kit visuals; states T8a to T8e | 1 | plan | B3 Tue 2/16 |
| F-09-T83 | S8 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T84 | Pilot 0 sessions wave C: the J04-PBC slice on staging … | 2.5 | non-code | — |
| F-09-T85 | Decision by Fri Feb 19 on the synthetic CCH return files for the Apr-May tax sessions … | 0.5 | non-code | — |
| F-09-T86 | Founding-partner agreement round 2 with counsel's redlines | 1.5 | non-code | — |
| F-09-T87 | SOC 2 readiness gap fixes for ayushkbhatia-owned policies, the vendor register and HR evidence … | 1 | non-code | — |
| G-01-T11 | Independent AC tests (ADR-078) for T04 and T05 … | 1 | plan | B5 Fri 2/19 |
| P-03-T14 | SHL-08 EvidenceViewer on two hosts (O2 drawer ?ov=viewer, T2 dock ?dock=viewer) … | 2 | plan | B4 Thu 2/18 |
| P-06-T21 | Upload-review eval cases: statement uploaded to an invoice request … | 0.5 | plan | B3 Tue 2/16 |
| P-06-T22 | C-34 ScreeningCard kit in packages/ui; SHL-20 states a-f with O3 follow-up sheet … | 1.75 | plan | B2 Thu 2/11 |
| P-07-T13 | Independent AC tests (ADR-078) for T07-T10: walls answer 404 with no count … | 0.75 | plan | carry ▲ |
| P-07-T31 | Consumer contract tests for the team, acceptance, independence and conflict stubs | 0.5 | plan | B3 Tue 2/16 |
| P-07-T32 | Independent AC tests (ADR-078) for T30: EQR eligibility rules, approver not the EP … | 0.5 | plan | carry ▲ |
| P-07-T33 | CLI-04 Contacts and portal access: T1 inside the client record … | 1.5 | plan | carry ▲ |
| P-07-T34 | ENG-03 remaining types: tax forms, CAS, notice and advisory step shapes … | 0.75 | plan | carry ▲ |
| P-08-T23 | POR-02 frontend part 2: d overdue entity owner … | 0.75 | plan | B4 Thu 2/18 |
| P-08-T24 | Independent AC tests (ADR-078) for T17, T18 and T21 … | 0.75 | plan | B4 Thu 2/18 |
| P-08-T25 | Security suite files backend/tests/security/test_portal_scope_isolation.py and … | 0.5 | plan | B4 Thu 2/18 |
| Q-02-T39 | Brightwater Hale compliance seed slice through the scenario loader … | 1 | plan | carry ▲ |
| Q-02-T52 | Independent AC tests (ADR-078) for classification flags and the gateway PII refusal (T32 … | 1 | plan | carry ▲ |
| Q-03-T021 | Re-run and extend the tranche-0 TASK-029 suite … | 0.5 | reserve | carry ▲ |
| Q-03-T022 | Back-fill TASK-036 and TASK-052 (client connection flow, health, access log and revoke … | 1 | reserve | carry ▲ |
| Q-03-T023 | Back-fill TASK-069 and TASK-048 (GL detail part 1 … | 1 | reserve | carry ▲ |
| Q-03-T024 | Back-fill amber TASK-038, TASK-068, TASK-070 and TASK-071 … | 1 | reserve | carry ▲ |
| R-01-T07 | Portal PBC read model (portal, amber): GET /v1/portal/binders … | 1.5 | plan | carry ▲ |
| R-01-T08 | Client ignore note and undo (requests, amber) … | 0.5 | plan | carry ▲ |
| R-01-T10 | POR-03 frontend part 2: drop target b and motion … | 1 | plan | carry ▲ |
| R-01-T11 | Python scenario slice through service APIs: Feld binder at Sep 14 … | 0.5 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Feb 9, 17:00 CT** · 5 PRs · one staging deploy: F-04-T32, F-04-T33, P-03-T13, P-06-T20, Q-02-T38
- **B2 · Thu Feb 11, 17:00 CT** · 9 PRs · one staging deploy: A-02-T02, A-01-T07, A-01-T10, A-01-T11, A-02-T01, A-02-T03, P-06-T22, P-07-T29, Q-02-T40
- **B3 · Tue Feb 16, 17:00 CT** · 13 PRs · one staging deploy: A-01-T08, A-01-T09, A-01-T12, F-05-T54, F-05-T55, F-05-T56, G-01-T08, G-01-T09, P-03-T12, P-06-T21, P-07-T31, P-08-T21, P-08-T22
- **B4 · Thu Feb 18, 17:00 CT** · 9 PRs · one staging deploy: A-02-T04, G-01-T10, P-03-T14, P-07-T30, P-08-T23, P-08-T24, P-08-T25, Q-02-T37, R-01-T09
- **B5 · Fri Feb 19, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: G-01-T11, P-04-T16, Q-03-T026
- **Beyond capacity (▲)** · 19 tasks, 16.5 size: A-02-T05, P-07-T13, P-07-T32, P-07-T33, P-07-T34, Q-02-T39, Q-02-T52, Q-03-T021, Q-03-T022, Q-03-T023, Q-03-T024, Q-03-T025, Q-03-T027, Q-03-T028, Q-03-T029, R-01-T07, R-01-T08, R-01-T10, R-01-T11

**Demo (Fri Feb 19).** (1) AUD-01 audits index live: tiles minus the active tile, segments and grouping (A-01-T08, T11). (2) AUD-02 cockpit with the Source Documents canvas and the viewer dock (A-01-T12). (3) SHL-08 viewer in the drawer and the dock, with PII regions detected (P-03-T13, T14). (4) SHL-20 screening card with the follow-up sheet (P-06-T20, T22). (5) ADM-02 users with walls v2; an offshore user is refused a restricted record (G-01-T09, T10).

**Exit check.** Pen test #1 running on the pinned build without blocking environment issues; WISP v1 approved by both founders (Q-02-T40); MFA overlay lint green (Q-02-T37).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.4, AY 0.5
- Residual after these moves: N 2.2, AY 11.1 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.9 S9 · Mon Feb 22 – Mar 5, 2027 · M6: J04 PBC slice on staging, pen test #1 closes

**Goal.** C20 v1 stub and the ledger TB-of-record service; ADM-03; the G-02 governance SPEC and audit-log stub; masked renditions and logged reveal; acceptance and continuance live (CLI-07, human-only); conflict check; agent run records; AUD-03 and the AUD-06 TB tab in fixture mode; POR-04 and POR-14; ENG-05.
**Milestones.** SOC 2 Type I as-of date Mon Mar 1. **M6 Fri Mar 5**: pen test #1 complete; audit cockpit, PBC, viewer and TB import on staging.
**Contracts handed over.** C20 v1 stub (A-02-T06; consumer tests A-02-T08 with C9); C16 v1.1 stub (R-01-T16; consumer tests R-01-T17); audit-log stub (G-02-T04); intake and import stubs (P-07-T37); engagement export format v1 (A-01-T17).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 17.2 | 94% | 5.4 / 5.5 | 0.0 / 0.0 | — | Q-03-T037 |
| AY (ayushkbhatia) | 13.8 | 23.8 | 172% **over** | 4.0 / 4.5 | 0.0 / 0.0 | 7.0 / 6.2 | A-02-T08, A-02-T09, G-02-T07, P-04-T17, P-07-T38, P-07-T39, P-07-T40, Q-03-T031, Q-03-T032, Q-03-T033, R-01-T12, R-01-T13, R-01-T14, R-01-T17 |

**N — 25 tasks, size 22.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T17 | Engagement export format v1: SPEC, Pydantic manifest with generated JSON schema, export routes stub … | 0.75 | plan | B2 Thu 2/25 |
| A-02-T06 | C20 v1 contract stub (POR-16 family and framework) … | 0.5 | plan | B2 Thu 2/25 |
| A-02-T07 | Ledger TB-of-record service and layer engine: adopt and re-version, prior-snapshot pairing … | 1 | plan | B4 Thu 3/4 |
| G-01-T12 | Service-line need-to-know (migration 00NN_need_to_know_v2) … | 0.5 | plan | B3 Tue 3/2 |
| G-01-T13 | Seasonal access end and annual independence (migration 00NN_annual_independence) … | 0.5 | plan | B3 Tue 3/2 |
| G-01-T14 | ADM-03: offices expand, teams and groups, service lines with confirm row h … | 1.5 | plan | B3 Tue 3/2 |
| G-02-T01 | Gate check and SPEC-0NN Firm governance v1 (AI policy, security center … | 0.5 | plan | B3 Tue 3/2 |
| G-02-T02 | Protected bundle: matrix rows in audit_trail, identity, agents and evidence files … | 0.5 | plan | B2 Thu 2/25 |
| G-02-T04 | Audit-log contract stub (ADM-07 family): classified Pydantic models … | 0.5 | plan | B3 Tue 3/2 |
| G-02-T06 | Expand-only migration on audit_events (ip, user_agent_family, device_label, session_id, auth_method … | 1 | plan | B4 Thu 3/4 |
| P-03-T15 | Masked renditions and masked agent material: patched step masked_preview burns opaque boxes into … | 1.5 | plan | B1 Tue 2/23 |
| P-03-T16 | Logged reveal: POST /v1/evidence-versions/{v}/pii-reveals with pii.reveal … | 1 | plan | B1 Tue 2/23 |
| P-03-T17 | Code-only citation conformance suite evals/citations/suite.yaml … | 0.5 | plan | B3 Tue 3/2 |
| P-06-T25 | Journey E2E in fixture and full-stack modes: j06 2, j16 5, j03 4 and 10, j10 2, j22 3-4 … | 1 | plan | B3 Tue 3/2 |
| P-07-T35 | Acceptance and continuance live (CLI-07, human-only) … | 2 | plan | B4 Thu 3/4 |
| P-07-T36 | Conflict-check service and screening records (organisations) … | 1 | plan | B4 Thu 3/4 |
| P-07-T37 | Intake and import contract stubs: client-intake drafts and commit, dedupe, client-imports … | 0.5 | plan | B2 Thu 2/25 |
| P-08-T26 | Playwright: j12 2b (Tess two-step), j12 1e (expired link renew), j12 1g … | 0.5 | plan | B2 Thu 2/25 |
| Q-02-T41 | Agent run records (P-47, conflict C-12): agent_run_records insert-only … | 1 | plan | B3 Tue 3/2 |
| Q-02-T42 | Pen test #1 (Feb 15 - Mar 5) triage and Type I as of Mar 1 … | 0.5 | plan | B2 Thu 2/25 |
| Q-03-T034 | Pen test #1 remediation part 1 (findings arrive Feb 15 - Mar 5) … | 2.5 | reserve | B2 Thu 2/25 |
| Q-03-T035 | Load-test harness part 1: abacus_tools.loadtest.run … | 1.5 | reserve | B5 Fri 3/5 |
| Q-03-T036 | Perf stack (QD-6): infra/envs/perf, an ephemeral Terraform environment in the staging account at … | 1 | reserve | B5 Fri 3/5 |
| Q-03-T037 | Pen-finding protocol: docs/ops/pentests/README.md and .claude/skills/pen-finding/SKILL.md … | 0.5 | reserve | carry ▲ |
| R-01-T16 | C16 v1.1 contract stub PR for the POR-20 and ADM-10 family … | 0.5 | plan | B2 Thu 2/25 |

**AY — 37 tasks, size 34.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T14 | ADR-078 independent AC tests for A-01-T05, T08, T09 and T10 | 1 | plan | B3 Tue 3/2 |
| A-01-T15 | AUD-03 screen on the 536 + 490 audit split: Missing first, folder bands, Linked … | 1.75 | plan | B2 Thu 2/25 |
| A-01-T16 | Remind and third-party wiring to P-06 follow-ups and delegation … | 0.5 | plan | B2 Thu 2/25 |
| A-02-T08 | Consumer contract tests for C9 v1 and C20 v1: pytest in backend/tests/contracts/c09_ledger and … | 0.5 | plan | carry ▲ |
| A-02-T09 | AUD-06 trial balance tab in fixture mode: T2 workpaper pane in the AUD-02 cockpit, header pills … | 1 | plan | carry ▲ |
| F-04-T34 | Docs: e2e-journeys.md (ADR-077), demo-tenant runbook, fixture-scenario and journey-step skills | 0.5 | plan | B1 Tue 2/23 |
| F-04-T35 | Canary profile: self-provisioning journeys with the real clock and no loader | 0.5 | plan | B1 Tue 2/23 |
| F-05-T57 | TPL-09a to TPL-09g three-preset specimen | 1 | plan | B3 Tue 3/2 |
| F-05-T58 | TPL-08a to TPL-08e firm Inbox specimen | 1 | plan | B3 Tue 3/2 |
| F-05-T59 | T5 CatalogLayout with C-11 AgentCard and IconTile and C-14 ConnectionTile visuals … | 1.5 | plan | B3 Tue 3/2 |
| F-09-T88 | S9 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T89 | Pilot 0 sessions wave D: J04-PBC on partner PBC lists | 2 | non-code | — |
| F-09-T90 | Pen-test window management (Feb 15-Mar 5): vendor contact, findings intake to notanaskhan … | 0.5 | non-code | — |
| F-09-T91 | SOC 2 system description sections (product, people, data, sub-processors … | 1.5 | non-code | — |
| F-09-T92 | Counsel M8 tax brief: section 7216 templates (consent to use and consent to disclose to AI … | 1 | non-code | — |
| F-09-T93 | Pilot 0 top-10 usability list v1 handed to owning epics (P-07, P-08, R-01, A-01, K-01) | 0.75 | non-code | — |
| G-01-T15 | Independent AC tests (ADR-078) for T08, T09, T12, T13 … | 1 | plan | B4 Thu 3/4 |
| G-02-T03 | Screen contracts docs/screens/ADM-04.md, ADM-06.md, ADM-07.md … | 1.25 | plan | B5 Fri 3/5 |
| G-02-T05 | Independent AC suite 1 (ADR-078) for the audit log against the stubs … | 1 | plan | B3 Tue 3/2 |
| G-02-T07 | Brightwater Hale seed slices and fixtures: AI policy v1 Jan 5, v2 Jan 9, v3 Jan 14 … | 1 | plan | carry ▲ |
| P-03-T18 | Independent AC tests (ADR-078) for citations v2 and the viewer … | 1.5 | plan | B4 Thu 3/4 |
| P-04-T17 | C13 consumer contract tests and independent AC tests (ADR-078) for the projector … | 0.5 | plan | carry ▲ |
| P-06-T23 | ADR-078 independent AC tests for T14, T18, T19 and T20 … | 1 | plan | B2 Thu 2/25 |
| P-06-T24 | SHL-14 d close variant on close_intake binders hosted from BND-02 until CLS-03 | 0.5 | plan | B3 Tue 3/2 |
| P-07-T38 | Independent AC tests (ADR-078) for T35-T36: EP-only decision with fresh MFA at matrix, live-human … | 1 | plan | carry ▲ |
| P-07-T39 | ENG-05 Team and roles: T1 inside ENG-02 with inspector, states a-e, blocked-assignment dialog … | 1 | plan | carry ▲ |
| P-07-T40 | Scenario content wave 2 through service APIs: Northwind contacts and delegations … | 0.5 | plan | carry ▲ |
| P-08-T27 | Parity and accessibility: Tier C report for POR-01 a-g and POR-02 a-h and M … | 0.5 | plan | B3 Tue 3/2 |
| Q-03-T030 | Nightly Hypothesis fuzzing of the TB and GL import parsers … | 1 | reserve | B1 Tue 2/23 |
| Q-03-T031 | Back-fill TASK-050 and TASK-051 (engagement agent v1 parts 1-2 … | 1.5 | reserve | carry ▲ |
| Q-03-T032 | Back-fill TASK-058 and TASK-059 (upload reviewer parts 1-2 … | 1 | reserve | carry ▲ |
| Q-03-T033 | Back-fill TASK-065 and TASK-066 (matcher agent … | 1 | reserve | carry ▲ |
| R-01-T12 | POR-04 request sheet frontend: O3 500 sheet route over /documents with a to do … | 1 | plan | carry ▲ |
| R-01-T13 | Third-party room read model and invitations on delegation (portal, amber) … | 1 | plan | carry ▲ |
| R-01-T14 | POR-14 frontend on T7 reduced and T7-M as the ScopedRequestRoom composition … | 1 | plan | carry ▲ |
| R-01-T15 | ADR-078 independent AC tests for T09: drop scope … | 0.5 | plan | B3 Tue 3/2 |
| R-01-T17 | C16 v1.1 consumer contract tests on behalf of R-01, P-06, N-02, A-02, A-08 and R-02 … | 0.25 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Feb 23, 17:00 CT** · 5 PRs · one staging deploy: F-04-T34, F-04-T35, P-03-T15, P-03-T16, Q-03-T030
- **B2 · Thu Feb 25, 17:00 CT** · 11 PRs · one staging deploy: G-02-T02, A-01-T15, A-01-T16, A-01-T17, A-02-T06, P-06-T23, P-07-T37, P-08-T26, Q-02-T42, Q-03-T034, R-01-T16
- **B3 · Tue Mar 2, 17:00 CT** · 16 PRs · one staging deploy: A-01-T14, F-05-T57, F-05-T58, F-05-T59, G-01-T12, G-01-T13, G-01-T14, G-02-T01, G-02-T04, G-02-T05, P-03-T17, P-06-T24, P-06-T25, P-08-T27, Q-02-T41, R-01-T15
- **B4 · Thu Mar 4, 17:00 CT** · 6 PRs · one staging deploy: A-02-T07, G-01-T15, G-02-T06, P-03-T18, P-07-T35, P-07-T36
- **B5 · Fri Mar 5, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: G-02-T03, Q-03-T035, Q-03-T036
- **Beyond capacity (▲)** · 15 tasks, 12.8 size: A-02-T08, A-02-T09, G-02-T07, P-04-T17, P-07-T38, P-07-T39, P-07-T40, Q-03-T031, Q-03-T032, Q-03-T033, Q-03-T037, R-01-T12, R-01-T13, R-01-T14, R-01-T17

**Demo (Fri Mar 5, the J04 PBC slice).** (1) From the AUD-02 cockpit open AUD-03 PBC: Missing first, folder bands, Linked counts (A-01-T15). (2) Remind a client and delegate an item to a third party (A-01-T16, R-01-T13, T14). (3) Open the evidence in the viewer; masked PII stays masked until a logged reveal (P-03-T15, T16). (4) AUD-06 trial balance tab in fixture mode against the imported TB (A-02-T09). (5) CLI-07 acceptance decided by the engagement partner with fresh MFA (P-07-T35).

**Exit check.** M6 met; findings triaged with owners and severities (Q-02-T42); remediation part 1 under way (Q-03-T034); M6 journey steps green on staging (A-01-T16).

**Candidate re-balancing moves.**

- Arriving from other sprints (1.0): F-05-T13 (from S1)
- Residual after these moves: N 0.0, AY 10.4 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.10 S10 · Mon Mar 8 – Mar 19, 2027 · Sign-off service, export package, C13, Bedrock clearance

**Goal.** Engagement export workflow and package; integrations framework v1 and entity-scoped connections; audit-trail read service and read-time value resolution; password unlock; the sign-off service with content hash and stale detection; independence live (CLI-08) and single intake commit (CLI-06); firm export with dual approval; final Bedrock clearance for the screener, upload reviewer and matcher; email template versions; AUD-06 read model; DS tier-2 lock; the C13 home half; knowledge stubs; CLI-07 screen.
**Milestones.** F-05 and P-06 windows close (S10).
**Contracts handed over.** C13 frozen (home-half stub I-01-T02 plus the gate-half red ticket I-01-T03); C9 layers and C20 framework on their S10 freeze (A-02-T10, T12, T13); C5 v1 frozen note (P-06-T27); knowledge-catalog and methodology stubs (K-01-T01); security-center stub (G-02-T11).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 21.5 | 117% **over** | 5.4 / 6.0 | 0.0 / 0.0 | — | A-02-T13, P-04-T19, P-07-T42, Q-03-T038, Q-03-T046, R-01-T19, R-01-T21 |
| AY (ayushkbhatia) | 13.8 | 20.2 | 146% **over** | 4.0 / 4.5 | 0.0 / 0.0 | 7.0 / 6.0 | I-01-T01, I-01-T03, K-01-T02, P-04-T20, Q-03-T039, Q-03-T040, Q-03-T042, R-01-T22 |

**N — 25 tasks, size 27.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T18 | Migration engagement_exports and exports.create … | 1 | plan | B4 Thu 3/18 |
| A-01-T19 | EngagementExportWorkflow and package builder: snapshot at one audit sequence, deterministic ZIP … | 1.5 | plan | B4 Thu 3/18 |
| A-02-T12 | Integrations framework v1: migration for integration_catalog … | 1 | plan | B5 Fri 3/19 |
| A-02-T13 | Migration entity-scoped connections: provider pattern, category, external_account_ref … | 1 | plan | carry ▲ |
| G-02-T08 | audit_trail read service and routes: list_events, get_event and events_for_work_item APIs … | 1.5 | plan | B2 Thu 3/11 |
| G-02-T09 | Read-time value resolution (DEC-60): platform.register_audit_value_resolver and labeler slots … | 1 | plan | B2 Thu 3/11 |
| G-02-T10 | Label index and search: audit_event_labels projection … | 1 | plan | B4 Thu 3/18 |
| G-02-T11 | Security-center contract stub (ADM-06 family) … | 0.5 | plan | B1 Tue 3/9 |
| P-03-T19 | Password unlock: POST /v1/evidence-versions/{v}/unlock decrypts, extracts, word-boxes … | 1.5 | plan | B1 Tue 3/9 |
| P-04-T18 | Sign-off service: POST /v1/sign-offs (sign_off.create … | 1.5 | plan | B3 Tue 3/16 |
| P-04-T19 | Stale detection and re-sign: consumer of *.version_created emits sign_off.went_stale and notifies … | 1 | plan | carry ▲ |
| P-06-T27 | Docs: requests, evidence and agents READMEs, final SPEC, C5 v1 frozen note … | 0.5 | plan | B1 Tue 3/9 |
| P-07-T41 | Independence live (CLI-08): independence_v2 migration … | 2 | plan | B5 Fri 3/19 |
| P-07-T42 | Single intake commit (CLI-06 a-f, h, i): client_intake_drafts migration, dedupe scoring … | 1.5 | plan | carry ▲ |
| P-08-T28 | Rollout and docs: flags on for synthetic firms and the canary … | 0.5 | plan | B1 Tue 3/9 |
| Q-02-T43 | Firm export with dual approval (DEC-72, conflict C-11) … | 1 | plan | B2 Thu 3/11 |
| Q-02-T44 | Final Bedrock clearance: screener, upload reviewer and matcher full suites on Bedrock with P-03's … | 1 | plan | B2 Thu 3/11 |
| Q-03-T038 | S9-S10 back-fill defect fixes for the agent, comments and guidance suites | 1 | reserve | carry ▲ |
| Q-03-T041 | Pen test #1 remediation part 2: highs fixed by Fri Mar 26 … | 3 | reserve | B3 Tue 3/16 |
| Q-03-T043 | Load harness part 2: the chapter 10 section 10.11.3 scenarios … | 1 | reserve | B3 Tue 3/16 |
| Q-03-T045 | ADR-086 earned auto-merge: after four clean sprints in F-01-T15's log … | 0.5 | reserve | B3 Tue 3/16 |
| Q-03-T046 | Load-test runbook docs/ops/loadtests/README.md and .claude/skills/loadtest/SKILL.md … | 0.5 | reserve | carry ▲ |
| R-01-T19 | Email template versions (communications, red) … | 1 | plan | carry ▲ |
| R-01-T20 | ADR-078 independent AC tests for AY's amber T07, T08, T11 and T13 … | 1 | plan | B3 Tue 3/16 |
| R-01-T21 | Playwright: j12 steps 4, 5 and 15, j03 steps 4c and 10, the j04-fs-audit PBC slice on POR-04 … | 0.5 | plan | carry ▲ |

**AY — 34 tasks, size 30.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T21 | Retire legacy evidence screens (Board, ItemDetail, EvidencePreview, DecisionActions, AIReviewPanel … | 0.5 | plan | B3 Tue 3/16 |
| A-01-T31 | AUD-02 f Auto mode confirm in fixture mode: the Auto mode toggle and confirm dialog … | 0.5 | plan | B3 Tue 3/16 |
| A-02-T10 | AUD-06 read model in assurance: TB list, view by layer, candidates with a code-computed diff … | 1 | plan | B5 Fri 3/19 |
| A-02-T11 | Migration workpapers tie_out_checks and insert-only tie_out_check_versions … | 0.5 | plan | B5 Fri 3/19 |
| A-02-T14 | AUD-06 remaining states in fixture mode: b agent-outlined ticks with Draft · Accrued Agent … | 1 | plan | B5 Fri 3/19 |
| F-05-T60 | Tier-2 lock: T3, T5, T8, T9 and TPL-02, TPL-03, TPL-05, TPL-08, TPL-09 at Tier B … | 1 | plan | B1 Tue 3/9 |
| F-05-T61 | Docs and runbook: DECISIONS.md complete, docs/design/parity.md … | 1 | plan | B1 Tue 3/9 |
| F-09-T94 | S10 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T95 | Pilot 0 sessions wave E: audit cockpit and TB import on staging | 1.5 | non-code | — |
| F-09-T96 | Cyber and tech E&O bound; certificate filed for the vendor-diligence pack | 1 | non-code | — |
| F-09-T97 | DocuSign ID Verification contract signed (M8 criterion c) | 1 | non-code | — |
| F-09-T98 | Type I fieldwork support: auditor interviews and management responses for ayushkbhatia-owned … | 1 | non-code | — |
| F-09-T99 | Counsel M7 finals: MSA, DPA with the generated sub-processor list, founding-partner agreement … | 1 | non-code | — |
| G-01-T16 | Playwright journey steps (fixture and compose, staging smoke) … | 1 | plan | B3 Tue 3/16 |
| G-02-T12 | Independent AC suite 2 (ADR-078) for the security center against the stubs … | 1 | plan | B2 Thu 3/11 |
| I-01-T01 | Screen contracts docs/screens/HOME-01.md and HOME-02.md from the template … | 0.5 | plan | carry ▲ |
| I-01-T02 | C13 home-half stub PR: practice Pydantic models for HomeVM … | 1 | plan | B3 Tue 3/16 |
| I-01-T03 | Red-zone service ticket for the C13 gate half … | 1 | plan | carry ▲ |
| K-01-T01 | Contract stubs: docs/contracts/knowledge-catalog.md and methodology-programs.md … | 1 | plan | B3 Tue 3/16 |
| K-01-T02 | Migration methodology_reown (chapter 03 step 8 without the links) … | 1 | plan | carry ▲ |
| P-03-T20 | SHL-08 masked PII (c) and password-locked (d) plus in-document search … | 1.5 | plan | B2 Thu 3/11 |
| P-03-T21 | Independent AC tests (ADR-078) for PII detection, masked renditions, agent masking and reveal … | 1 | plan | B2 Thu 3/11 |
| P-04-T20 | Independent AC and property tests (ADR-078, hypothesis) for I-SEGREGATION and the sign-off … | 1 | plan | carry ▲ |
| P-06-T26 | Parity and accessibility: 23 artboards reported at Tier C, BND-01 and BND-02 locked at Tier C … | 0.5 | plan | B1 Tue 3/9 |
| P-07-T43 | Independent AC tests (ADR-078) for T41: self-only confirmation, decline note … | 1 | plan | B4 Thu 3/18 |
| P-07-T44 | Independent AC tests (ADR-078) for T42: atomicity, Idempotency-Key replay … | 0.5 | plan | B4 Thu 3/18 |
| P-07-T45 | Consumer contract tests for the intake and import stubs | 0.25 | plan | B2 Thu 3/11 |
| P-07-T46 | CLI-07 Acceptance and continuance: T2 with decision dock … | 1.5 | plan | B4 Thu 3/18 |
| Q-03-T039 | Back-fill TASK-062 (comments backend, kept until P-05) and TASK-072 (guidance drafter … | 1.5 | reserve | carry ▲ |
| Q-03-T040 | Back-fill TASK-073 and TASK-074 (drafting in the product, review … | 1 | reserve | carry ▲ |
| Q-03-T042 | Pen test #1 regression tests part 1: one test per critical or high in backend/tests/security/ … | 1.5 | reserve | carry ▲ |
| Q-03-T044 | Load scenario content from the journeys: J02, J04-PBC and J12 step mixes, persona weights … | 0.5 | reserve | B3 Tue 3/16 |
| R-01-T18 | Live swap and legacy retirement: /documents serves POR-03 and POR-04 for synthetic firms and the … | 0.5 | plan | B5 Fri 3/19 |
| R-01-T22 | Fixtures and scenario rows for POR-20 (12 artboards) and ADM-10 (7) … | 0.5 | plan | carry ▲ |

**Merge batches.**

- **B1 · Tue Mar 9, 17:00 CT** · 7 PRs · one staging deploy: F-05-T60, F-05-T61, G-02-T11, P-03-T19, P-06-T26, P-06-T27, P-08-T28
- **B2 · Thu Mar 11, 17:00 CT** · 8 PRs · one staging deploy: G-02-T08, G-02-T09, G-02-T12, P-03-T20, P-03-T21, P-07-T45, Q-02-T43, Q-02-T44
- **B3 · Tue Mar 16, 17:00 CT** · 11 PRs · one staging deploy: A-01-T21, A-01-T31, G-01-T16, I-01-T02, K-01-T01, P-04-T18, Q-03-T041, Q-03-T043, Q-03-T044, Q-03-T045, R-01-T20
- **B4 · Thu Mar 18, 17:00 CT** · 6 PRs · one staging deploy: A-01-T18, A-01-T19, G-02-T10, P-07-T43, P-07-T44, P-07-T46
- **B5 · Fri Mar 19, 12:00 CT (sprint close)** · 6 PRs · one staging deploy: A-02-T10, A-02-T11, A-02-T12, A-02-T14, P-07-T41, R-01-T18
- **Beyond capacity (▲)** · 15 tasks, 14.5 size: A-02-T13, I-01-T01, I-01-T03, K-01-T02, P-04-T19, P-04-T20, P-07-T42, Q-03-T038, Q-03-T039, Q-03-T040, Q-03-T042, Q-03-T046, R-01-T19, R-01-T21, R-01-T22

**Demo (Fri Mar 19).** (1) Sign off a workpaper; edit the target; the sign-off goes stale and the signer is notified; re-sign (P-04-T18, T19). (2) Build an engagement export package: deterministic ZIP and manifest from one audit sequence (A-01-T18, T19). (3) CLI-07 acceptance on staging (P-07-T46). (4) The Bedrock clearance report for the three agents, with masked inputs (Q-02-T44). (5) A password-locked PDF unlocked, extracted and word-boxed (P-03-T19).

**Exit check.** DS tier-2 lock at Tier B (F-05-T60); C13 frozen; Bedrock clearance recorded for the M7 dossier; pen-test highs in remediation with a retest date before Apr 9.

**Candidate re-balancing moves.**

- Defer inside the chapter 01 window (1.5): R-01-T20→S15, R-01-T21→S15
- Residual after these moves: N 2.2, AY 6.9 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.11 S11 · Mon Mar 22 – Apr 2, 2027 · Admin screens, review notes and decision cards, HOME-01

**Goal.** Export download and interim record-mode G8 and G9 providers; the write-capability registry skeleton; the entity-scoped connection service; ADM-06 and ADM-07; security policies; review notes, bulk sign-off and decision cards; human-gate home migration; template preview, lint and test send; follow-up policy; HOME-01 main region; KNW-01 catalog; CLI-08 and CLI-06 screens; POR-16 in fixture mode; POR-20.
**Milestones.** Independent tests for incidents, export, MFA and run records pass before Fri Apr 2 (Q-02-T46).
**Contracts handed over.** C6 v1 stub (Q-02-T45, conditional on the owner change being recorded; see §7.5.5); AI-policy stub (G-02-T15).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 18.0 | 98% | 5.4 / 6.0 | 0.0 / 0.0 | — | I-01-T04, P-04-T22 |
| AY (ayushkbhatia) | 13.8 | 17.0 | 123% **over** | 4.0 / 3.5 | 0.0 / 0.0 | 7.0 / 5.0 | I-01-T06, Q-03-T047, Q-03-T048, Q-03-T049, Q-03-T050 |

**N — 23 tasks, size 24.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T22 | Export download with Range, status and list routes, 7-day expiry sweep, void on withdrawal … | 0.75 | plan | B3 Tue 3/30 |
| A-01-T23 | Interim record-mode G8 and G9 providers in assurance/release.py and archive_gate.py … | 0.75 | plan | B4 Thu 4/1 |
| A-02-T15 | Write-capability registry skeleton: protected docs/architecture/write-capabilities.yaml … | 1 | plan | B4 Thu 4/1 |
| A-02-T16 | Entity-scoped connection service: portal card list composed in integrations … | 1.5 | plan | B4 Thu 4/1 |
| F-09-T103 | notanaskhan verifies Resource Pack v2 figures against the committed eval runs and the register | 0.5 | non-code | — |
| G-01-T17 | Parity lock and cleanup: ADM-01/02/03 locked at Tier C with Tier D styles, keyboard suites … | 0.75 | plan | B4 Thu 4/1 |
| G-02-T13 | ADM-07 screen at /settings/audit-log: T1 inside the T12 frame, FilterChips, count with Lock … | 1.5 | plan | B1 Tue 3/23 |
| G-02-T14 | Security policies and enforcement: security_policies table … | 1.5 | plan | B2 Thu 3/25 |
| G-02-T15 | AI-policy contract stub (ADM-04 family): classified models for policy versions, sections A to E … | 0.5 | plan | B4 Thu 4/1 |
| G-02-T16 | ADM-06 screen at /settings/security: two-column T12 … | 1.75 | plan | B2 Thu 3/25 |
| I-01-T04 | Migration NNNN_human_gate_home (review): human_gates gains subkind, office_id, blocked … | 1 | plan | carry ▲ |
| P-03-T23 | Independent AC tests (ADR-078) for the amber viewer UI … | 0.5 | plan | B1 Tue 3/23 |
| P-04-T21 | Review notes service: raise, respond, clear and withdraw with sealed bodies and anchors … | 1 | plan | B2 Thu 3/25 |
| P-04-T22 | Bulk sign-off (R-SO-7): POST /v1/sign-offs:bulk with Idempotency-Key, reviewers only … | 1 | plan | carry ▲ |
| P-04-T23 | Decision cards service: review.api.raise_decision_card … | 1.5 | plan | B2 Thu 3/25 |
| P-07-T47 | Human-gate and notification registrations: C13 gate kinds … | 0.5 | plan | B4 Thu 4/1 |
| Q-02-T45 | Conditional on the C6 v1 owner change being recorded … | 0.5 | plan | B1 Tue 3/23 |
| Q-03-T051 | Mutation baselines per red module measured and floors set at the baseline on S11 … | 1 | reserve | B3 Tue 3/30 |
| Q-03-T052 | x25 load test before M7 on the perf stack: 2 hours at x25 then an 8-hour soak over the MVP-1 audit … | 2 | reserve | B3 Tue 3/30 |
| Q-03-T053 | 2027 Q1 restore drill by Fri Mar 26 (RB-15): random PITR within 7 days in the production drill … | 1 | reserve | B3 Tue 3/30 |
| Q-03-T054 | Pen test #1 remediation part 3: retest coordination so criticals and highs are retested closed by … | 2 | reserve | B3 Tue 3/30 |
| R-01-T23 | Template preview, lint, test send and import (communications, red) … | 1 | plan | B5 Fri 4/2 |
| R-01-T24 | Follow-up policy (DEC-74; communications and agents, red) … | 1 | plan | B5 Fri 4/2 |

**AY — 27 tasks, size 25.5**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T24 | Export sheet design follow-up composed from kits … | 1 | plan | B2 Thu 3/25 |
| A-02-T17 | Tie engine and tie-out check service in workpapers … | 1 | plan | B3 Tue 3/30 |
| A-02-T18 | POR-16 Connections in fixture mode: T7 reduced 720 and T7-M 390, relationship header … | 1 | plan | B3 Tue 3/30 |
| A-02-T19 | Independent AC tests (ADR-078) for the integrations framework and registry … | 0.5 | plan | B4 Thu 4/1 |
| F-09-T100 | S11 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T101 | Pilot 0 sessions wave F: retests of fixed top-10 items … | 1.5 | non-code | — |
| F-09-T102 | Technology Resource Pack v2 for the M7 vendor-diligence pack … | 1.5 | non-code | — |
| F-09-T104 | Type I report receipt (about Apr 2) and the NDA distribution process | 0.5 | non-code | — |
| F-09-T105 | Tax-partner addendum negotiated: 5-15 extended 1065 and 1040 returns for PWT (M8 criterion b) | 1 | non-code | — |
| I-01-T05 | HOME-01 fixtures and scenarios: handlers apps/web/src/fixtures/handlers/home.ts and human-gates.ts … | 1 | plan | B5 Fri 4/2 |
| I-01-T06 | HOME-01 main region on T11: subbar greeting and date … | 1.25 | plan | carry ▲ |
| K-01-T03 | Knowledge catalog read model: methodology.register_catalog_provider and register_usage_counter … | 1 | plan | B4 Thu 4/1 |
| K-01-T04 | KNW-01 on the T5 CatalogLayout: 11 categories in addendum section 4 order, status Picker … | 1.5 | plan | B4 Thu 4/1 |
| K-01-T05 | Workbook v2 and migration methodology_programs … | 1 | plan | B5 Fri 4/2 |
| P-03-T22 | Independent AC tests (ADR-078) for password unlock … | 1 | plan | B1 Tue 3/23 |
| P-03-T24 | Fixture-mode Playwright specs e2e/trust/shl-07-citation-popover.spec.ts and … | 1 | plan | B1 Tue 3/23 |
| P-07-T48 | CLI-08 Independence and conflicts: tabs Conflicts, NAS matrix, Team confirmations, Rotation … | 1 | plan | B3 Tue 3/30 |
| P-07-T49 | CLI-06 single intake on O6 over CLI-01: dedupe card, entity details, related entities, contacts … | 1.25 | plan | B3 Tue 3/30 |
| P-07-T50 | Scenario content wave 3: Thornbury intake holdout … | 0.5 | plan | B3 Tue 3/30 |
| P-08-T29 | Screen docs and skills: POR-01 and POR-02 Deviations closed … | 0.25 | plan | B1 Tue 3/23 |
| Q-02-T46 | Independent AC tests (ADR-078) for incidents, firm export, MFA and run records … | 1.25 | plan | B2 Thu 3/25 |
| Q-03-T047 | Back-fill amber TASK-033, TASK-037, TASK-039 and TASK-060 … | 1 | reserve | carry ▲ |
| Q-03-T048 | Back-fill TASK-024 (knowledge retrieval infrastructure on pgvector, without content) from SPEC-009 | 0.5 | reserve | carry ▲ |
| Q-03-T049 | Independent AC tests for the auto-merge rule: path classifier, flag requirement, window respected … | 0.5 | reserve | carry ▲ |
| Q-03-T050 | Back-fill amber TASK-026 (feature-flag registry with per-firm enablement, SPEC-011) … | 0.5 | reserve | carry ▲ |
| Q-03-T055 | Pen test #1 regression tests part 2, for the highs fixed after Mar 5 | 1 | reserve | B2 Thu 3/25 |
| R-01-T25 | POR-20 frontend with an interim EmailPreview until F-06-T16 … | 1.5 | plan | B4 Thu 4/1 |

**Merge batches.**

- **B1 · Tue Mar 23, 17:00 CT** · 6 PRs · one staging deploy: G-02-T13, P-03-T22, P-03-T23, P-03-T24, P-08-T29, Q-02-T45
- **B2 · Thu Mar 25, 17:00 CT** · 7 PRs · one staging deploy: A-01-T24, G-02-T14, G-02-T16, P-04-T21, P-04-T23, Q-02-T46, Q-03-T055
- **B3 · Tue Mar 30, 17:00 CT** · 10 PRs · one staging deploy: A-01-T22, A-02-T17, A-02-T18, P-07-T48, P-07-T49, P-07-T50, Q-03-T051, Q-03-T052, Q-03-T053, Q-03-T054
- **B4 · Thu Apr 1, 17:00 CT** · 10 PRs · one staging deploy: A-02-T19, A-01-T23, A-02-T15, A-02-T16, G-01-T17, G-02-T15, K-01-T03, K-01-T04, P-07-T47, R-01-T25
- **B5 · Fri Apr 2, 12:00 CT (sprint close)** · 4 PRs · one staging deploy: I-01-T05, K-01-T05, R-01-T23, R-01-T24
- **Beyond capacity (▲)** · 7 tasks, 5.8 size: I-01-T04, I-01-T06, P-04-T22, Q-03-T047, Q-03-T048, Q-03-T049, Q-03-T050

**Demo (Fri Apr 2).** (1) ADM-07 audit-log explorer with filters and the via-Agent actor grammar; ADM-06 security center (G-02-T13, T16). (2) Raise a decision card, respond and resolve it; bulk sign-off by a reviewer with an idempotency key (P-04-T22, T23). (3) HOME-01 main region in fixture mode (I-01-T06). (4) KNW-01 catalog in the T5 layout (K-01-T04). (5) CLI-06 single intake with the dedupe card (P-07-T49).

**Exit check.** Q-02-T46 green before Apr 2; C6 v1 owner recorded or the stub skipped; pen-test highs ready for retest.

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.0, AY 0.5
- Defer inside the chapter 01 window (1.0): P-04-T22→S15
- Arriving from other sprints (0.8): P-07-T51 (from S12)
- Residual after these moves: N 0.0, AY 2.6 task-equivalents over planned capacity (covered in §7.5.3)

### 7.3.12 S12 · Mon Apr 5 – Apr 16, 2027 · M7: the real-data gate

**Goal.** Journey E2E for the audit spine; ledger evidence and import hooks; audit export, incident-register depth, firm data export schedule and safeguards programme; C13 list facts and registrations; proposals and suggestions approval; C3 services v1 freeze; full-stack E2E for gates and access; sender domains and the client-mail gate; the M7 gate dossier; AUD-06 live swap; HOME-01 live tiles; KNW-02 workbook slice; bulk client and contact import; ADM-10; the real-data rehearsal.
**Milestones.** Pen-test criticals and highs retested closed by Fri Apr 9. **M7 Fri Apr 16**: real-data gate (R2), no exception path.
**Contracts handed over.** C3 services v1 frozen (P-04-T27); C6 v1 frozen (register S12); C13 list facts live (I-01-T07).

| Founder | Planned avail | Planned demand | Load | Reserve avail / demand | Support avail / demand | Non-code avail / demand | Tasks beyond capacity (▲) |
|---|---:|---:|---:|---:|---:|---:|---|
| N (notanaskhan) | 18.4 | 21.0 | 114% **over** | 5.4 / 5.2 | 0.0 / 0.0 | — | Q-03-T063, Q-04-T002, Q-04-T003 |
| AY (ayushkbhatia) | 13.8 | 17.2 | 125% **over** | 4.0 / 2.0 | 0.0 / 0.0 | 7.0 / 4.8 | I-01-T10, I-01-T11, Q-03-T059, Q-03-T061, Q-03-T062 |

**N — 31 tasks, size 26.75**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T26 | Journey E2E in fixture, full-stack and staging modes … | 1 | plan | B3 Tue 4/13 |
| A-02-T21 | Independent AC tests (ADR-078) for AY's amber code … | 1 | plan | B4 Thu 4/15 |
| A-02-T22 | Evidence and import hooks: ledger_line citable verifier registered from evidence … | 1 | plan | B4 Thu 4/15 |
| A-02-T23 | Firm reconnect requests and the portal reconnect to-do … | 0.5 | plan | B4 Thu 4/15 |
| F-09-T108 | Independent M7 check of F-09's items: insurance bound, MSA and DPA final … | 0.5 | non-code | — |
| G-01-T18 | Docs: freeze firm-settings.md; identity and organisations READMEs; SPEC-002 amendment accepted … | 0.5 | plan | B3 Tue 4/13 |
| G-02-T17 | Audit export: AuditExportWorkflow (batch) writing CSV plus manifest.json and manifest.sig … | 1 | plan | B1 Tue 4/6 |
| G-02-T18 | Incident register depth on Q-02's kernel: list, detail and append-only timeline entries … | 1 | plan | B1 Tue 4/6 |
| G-02-T19 | Firm data export schedule and history on Q-02's FirmExportWorkflow and A-01's package format … | 0.5 | plan | B3 Tue 4/13 |
| G-02-T20 | Safeguards program in platform: safeguards_programs record … | 0.5 | plan | B3 Tue 4/13 |
| I-01-T07 | C13 list facts and gate actions (review): GET /v1/human-gates filters state open, done and snoozed … | 1 | plan | B4 Thu 4/15 |
| I-01-T08 | C13 and home-count registrations for the wedge … | 1.25 | plan | B5 Fri 4/16 |
| I-01-T09 | ADR-078 AC tests for AY's amber home work (I-01-T10, T12, T13) … | 0.5 | plan | B3 Tue 4/13 |
| P-03-T26 | Runbook docs/runbooks/RB-31 PII reveal review and unlock abuse … | 0.5 | plan | B1 Tue 4/6 |
| P-04-T24 | Proposals and suggestions: approve, approve with edits … | 1.5 | plan | B2 Thu 4/8 |
| P-04-T25 | Typed proposal adapters for the live specialists … | 1 | plan | B4 Thu 4/15 |
| P-04-T26 | Notification kinds in notifications/catalogue.py … | 0.5 | plan | B4 Thu 4/15 |
| P-04-T27 | C3 services v1 freeze: docs/contracts/review-grammar.md complete … | 0.5 | plan | B2 Thu 4/8 |
| P-07-T51 | Independent AC tests (ADR-078) for AY's bulk import T52 … | 0.75 | plan | B3 Tue 4/13 |
| P-07-T53 | Full-stack E2E for gates and access: cli-04 invite with the portal limited to delegated requests … | 1 | plan | B3 Tue 4/13 |
| Q-02-T47 | Wire A-01's engagement export format v1 package builder into FirmExportWorkflow … | 0.5 | plan | B3 Tue 4/13 |
| Q-02-T49 | M7 gate dossier and vendor-diligence pack: pen-test retest closure and attestation letter … | 1 | plan | B3 Tue 4/13 |
| Q-03-T056 | x25 findings fixed as a reliability-only batch (ADR-093) and the test re-run before M7 | 1.5 | reserve | B2 Thu 4/8 |
| Q-03-T057 | 2027 Q1 kill-switch game day on staging (ADR-097) … | 0.5 | reserve | B5 Fri 4/16 |
| Q-03-T058 | Regional failover tabletop before R2 (RB-11): us-west-2 pilot-light restore walked with AY as … | 0.5 | reserve | B2 Thu 4/8 |
| Q-03-T060 | M7 quality evidence for Q-02-T49's dossier: back-fill tranche 0 and S6-S10 complete … | 0.5 | reserve | B2 Thu 4/8 |
| Q-03-T063 | Escaped-defect fix-forward 2027 Q1: defects that passed every gate … | 2.25 | reserve | carry ▲ |
| Q-04-T001 | P-29 implementation note and docs/ops/release-windows.md … | 0.5 | plan | B3 Tue 4/13 |
| Q-04-T002 | deploy/windows.yaml (new, protected, both handles in CODEOWNERS) and … | 1 | plan | carry ▲ |
| Q-04-T003 | Release gate in deploy-production.yml and make release-pr … | 1.25 | plan | carry ▲ |
| R-01-T27 | Sender domains, delivery events and the client-mail gate (communications, red) … | 1.25 | plan | B4 Thu 4/15 |

**AY — 24 tasks, size 24**

| Task | Title | Size | Pool | Batch |
|---|---|---:|---|---|
| A-01-T25 | ADR-078 independent AC tests for A-01-T18, T19, T22 and T23 … | 1.5 | plan | B2 Thu 4/8 |
| A-02-T20 | Independent AC tests (ADR-078) for the ledger TB of record, layers and import hooks … | 1 | plan | B4 Thu 4/15 |
| A-02-T24 | AUD-06 live swap: fixture to live, adopt a TB of record from the empty state, newer-TB banner … | 0.5 | plan | B4 Thu 4/15 |
| F-09-T106 | S12 programme cadence: Contract Monday note on RK-01, RK-04, RK-05, RK-47 and RK-50 … | 0.5 | non-code | — |
| F-09-T107 | Counsel's second approval of the Bedrock provider-terms entry, current for real data (ADR-114 Q3) | 0.5 | non-code | — |
| F-09-T109 | Pilot 0 tax session 1: coordination-slice walkthrough and CCH file-format validation with the … | 1.5 | non-code | — |
| F-09-T110 | PW1 contract and legal checklist for the first firm (chapter 06 section 8.3) … | 1.5 | non-code | — |
| F-09-T111 | Section 7216 consent text draft reviewed with notanaskhan … | 0.75 | non-code | — |
| G-02-T21 | Journey E2E and parity for ADM-06 and ADM-07: j01 2 and j14 7 Playwright tests with INV-1 to INV-5 … | 1 | plan | B2 Thu 4/8 |
| G-02-T22 | Independent AC suite 3 (ADR-078) for the AI policy against the stubs … | 1 | plan | B2 Thu 4/8 |
| I-01-T10 | GET /v1/home live in practice: tiles through platform.register_home_count with by-office breakdown … | 1.5 | plan | carry ▲ |
| I-01-T11 | HOME-01 right column and chrome: Your deadlines pane … | 0.75 | plan | carry ▲ |
| K-01-T06 | Lifecycle service: submit; approve with effective date and supersede … | 1 | plan | B3 Tue 4/13 |
| K-01-T07 | KNW-02 workbook slice on the T3 Prepare frame … | 1.5 | plan | B4 Thu 4/15 |
| K-01-T10 | Seed: Brightwater Hale methodology content through methodology service APIs under the demo clock … | 0.5 | plan | B4 Thu 4/15 |
| P-03-T25 | Full-stack E2E on staging: extend e2e/journeys/J04-pbc-slice.spec.ts with the trace-to-source step … | 1 | plan | B1 Tue 4/6 |
| P-04-T28 | Independent AC tests (ADR-078) for review notes, decision cards, proposals … | 1 | plan | B5 Fri 4/16 |
| P-07-T52 | Bulk client and contact import (engagements intake package) … | 1.5 | plan | B3 Tue 4/13 |
| Q-02-T48 | Real-data rehearsal system test on staging (backend/tests/system/test_real_data_rehearsal.py … | 1 | plan | B1 Tue 4/6 |
| Q-03-T059 | Re-run all 44 back-filled suites (tranche 0 and S6-S11) against the final MVP contracts … | 1 | reserve | carry ▲ |
| Q-03-T061 | Contract-test upkeep 2027 Q1 for N-provided contracts … | 0.5 | reserve | carry ▲ |
| Q-03-T062 | Quarterly reserve review 2027 Q1: burn by workstream against this plan, escaped-defect retro … | 0.5 | reserve | carry ▲ |
| R-01-T26 | Portal settings and preview (portal, amber): migration portal_settings … | 1 | plan | B3 Tue 4/13 |
| R-01-T28 | ADM-10 frontend on T12 with the live preview column … | 1.5 | plan | B3 Tue 4/13 |

**Merge batches.**

- **B1 · Tue Apr 6, 17:00 CT** · 5 PRs · one staging deploy: G-02-T17, G-02-T18, P-03-T25, P-03-T26, Q-02-T48
- **B2 · Thu Apr 8, 17:00 CT** · 8 PRs · one staging deploy: A-01-T25, G-02-T21, G-02-T22, P-04-T24, P-04-T27, Q-03-T056, Q-03-T058, Q-03-T060
- **B3 · Tue Apr 13, 17:00 CT** · 14 PRs · one staging deploy: A-01-T26, G-01-T18, G-02-T19, G-02-T20, I-01-T09, K-01-T06, P-07-T51, P-07-T52, P-07-T53, Q-02-T47, Q-02-T49, Q-04-T001, R-01-T26, R-01-T28
- **B4 · Thu Apr 15, 17:00 CT** · 11 PRs · one staging deploy: A-02-T20, A-02-T21, A-02-T22, A-02-T23, A-02-T24, I-01-T07, K-01-T07, K-01-T10, P-04-T25, P-04-T26, R-01-T27
- **B5 · Fri Apr 16, 12:00 CT (sprint close)** · 3 PRs · one staging deploy: I-01-T08, P-04-T28, Q-03-T057
- **Beyond capacity (▲)** · 8 tasks, 8.8 size: I-01-T10, I-01-T11, Q-03-T059, Q-03-T061, Q-03-T062, Q-03-T063, Q-04-T002, Q-04-T003

**Demo (Fri Apr 16, the gate review).** (1) Walk the M7 dossier and vendor-diligence pack: Type I report, pen-test retest letter, provider-terms entry with counsel as second approver, per-agent Bedrock evals including shadow-stage runs, MSA and DPA with the generated sub-processor list, insurance, WISP, MFA enforcement, restore drill, compliance kernel (Q-02-T49, Q-03-T060). (2) Run the real-data rehearsal system test on staging (Q-02-T48). (3) HOME-01 with live gate counts by office (I-01-T10). (4) J04 PBC slice with trace-to-source on staging (P-03-T25). (5) Approve an agent proposal with edits; the citation note is kept (P-04-T24).

**Exit check (M7, all required).** SOC 2 Type I report in hand; pen-test criticals and highs closed and retested; provider-terms Bedrock entry current; per-agent evals passed for every agent touching real data; firm opt-in recorded per firm before its first agent run; MSA, DPA and sub-processor list; cyber and tech E&O bound; WISP approved; MFA enforced for staff and portal owners and signers; restore drill within the quarter; compliance kernel complete; vendor-diligence pack ready. If the Type I report is late, chapter 01's fallback applies (gate Fri May 14; shadow Jun 15; R3 Jul 27).

**Candidate re-balancing moves.**

- Unused hardening reserve funds same-sprint ADR-078 test rows (tests, never features): N 0.1, AY 2.0
- Pull earlier inside the chapter 01 window (0.8): P-07-T51→S11
- Defer inside the chapter 01 window (1.5): I-01-T09→S16, A-02-T21→S16
- Residual after these moves: N 0.2, AY 1.4 task-equivalents over planned capacity (covered in §7.5.3)

---

## 7.4 S13 to S74 (Apr 19, 2027 – Aug 31, 2029)

One row per sprint. *Epics active* lists the build epics in which that founder has at least one CSV task in the sprint, with the planned size in brackets; Q-03 (reserve), Q-04 (support) and F-09 (non-code) run alongside and are left out. *Load* is planned demand over planned capacity (§7.5.1); bold means over 100%. Milestones and gates are chapter 01's (§1.2.2, §1.5); journey dates are chapter 01 §1.5.1.

| Sprint | Dates | Phase | N epics active (planned size) | AY epics active (planned size) | Milestone / key deliverable | Load N / AY |
|---|---|---|---|---|---|---|
| S13 | Apr 19 – Apr 30, 2027 | PH2 | A-01 (0.5), A-02 (2.5), G-01 (0.25), G-02 (2.5), K-01 (1.5), N-01 (2.5), N-02 (3.75), P-04 (2), P-07 (2), Q-02 (2), R-01 (0.25) | A-01 (1.5), A-02 (2.5), I-01 (1), K-01 (0.75), N-01 (1.5), N-02 (1.5), P-07 (2), R-01 (0.75) | Close-out of the spine: **A-01** and **Q-02** close; **N-01** inbox and **N-02** signatures start; tier-1 cut decision point if M5 invoked it | **115%** / 94% |
| S14 | May 3 – May 14, 2027 | PH2 | A-02 (1), F-06 (0.25), G-02 (2.75), N-01 (2.75), N-02 (3.25), P-04 (2.5), P-07 (0.5) | A-02 (2), F-06 (4), G-02 (1), I-01 (0.75), N-01 (2.5), N-02 (3.5), P-04 (1.5), P-07 (1.25), R-01 (0.5), T-02 (0.5) | Support reserve 10% begins (onboarding prep); DEC-49 tax-engine route needed; Pilot 0 CCH format validation with the tax partner | 78% / **141%** |
| S15 | May 17 – May 28, 2027 | PH2 | A-02 (0.5), F-06 (1), N-01 (5.75), N-02 (3), P-04 (1), P-07 (0.5), R-01 (0.25) | A-02 (1), F-06 (3.5), I-01 (0.75), N-01 (4.25), N-02 (2), P-04 (1.5), P-07 (1) | **M8 Fri May 28** MVP-1 code-complete (J01-core, J02-audit-core, J04-PBC slice, J12-core walkable in production); tax-pilot go/no-go; calibration #3 | 72% / **112%** |
| S16 | May 31 – Jun 11, 2027 | PH3 | A-02 (0.5), K-02 (2), N-01 (1), N-02 (3.75), T-01 (4), T-02 (0.5) | A-02 (0.5), F-06 (2), I-01 (1), K-01 (1), K-02 (3), N-01 (2), N-02 (1.5), P-04 (3), R-01 (0.75), T-01 (3), T-02 (5.25) | **M9 Tue Jun 1** first firm in internal shadow (PW1); **T-01**, **T-02**, **K-02** build window opens | 75% / **196%** |
| S17 | Jun 14 – Jun 25, 2027 | PH3 | A-02 (1), F-06 (0.5), N-01 (1.75), N-02 (3.25), P-04 (1.5), P-11 (3), R-01 (0.5), T-01 (2.5) | A-02 (0.5), F-06 (2.5), I-01 (1), K-01 (1), K-02 (4.5), N-02 (2.5), P-04 (2), P-11 (0.5), T-01 (3.5), T-02 (5) | Pen-test delta #1 Jun 21 – Jul 2; C7 DocuSign, C19 and C21 frozen; **A-02** closes | 89% / **196%** |
| S18 | Jun 28 – Jul 9, 2027 | PH3 | A-03 (0.5), K-02 (1), N-01 (3), N-02 (1.25), P-04 (0.5), P-11 (1.5), T-01 (6.5), T-02 (1) | A-03 (0.5), F-06 (2.5), K-01 (1), K-02 (4.5), N-01 (1), N-02 (3.75), P-04 (1), P-11 (1), R-01 (0.5), T-01 (4.25), T-02 (3.75) | **R-01** and **N-01** close (portal PBC core, inbox); delta #1 findings closed | 97% / **202%** |
| S19 | Jul 12 – Jul 23, 2027 | PH3 | F-06 (0.5), K-02 (1), N-02 (2), P-11 (3.5), T-01 (4.5), T-02 (1.5) | F-06 (1.5), K-01 (1), K-02 (3), N-02 (4), P-04 (2.5), T-01 (4.75), T-02 (5.5) | **M10 Tue Jul 13** client-facing audit pilot (R3, PW2); +10% learning gain from here; **K-02** closes | 75% / **172%** |
| S20 | Jul 26 – Aug 6, 2027 | PH3 | A-03 (3), K-01 (0.5), N-02 (2.75), P-04 (1), P-11 (1), T-01 (4), T-02 (1.5) | A-03 (2.5), F-06 (2.5), N-02 (2.75), P-04 (2.5), P-11 (2.5), T-01 (4.25), T-02 (4.25) | PWT shadow from Jul 27; pen-test delta #2 Aug 2–11; **A-03** window opens (pre-window ADR drafting booked in S18) | 80% / **164%** |
| S21 | Aug 9 – Aug 20, 2027 | PH3 | A-03 (2), A-05 (0.5), F-06 (0.5), N-02 (3.5), P-04 (1), P-11 (1), T-01 (4.25), T-02 (2) | A-03 (3.5), K-01 (0.5), N-02 (1.5), P-04 (0.5), P-11 (0.5), T-01 (5), T-02 (1.5) | **M11 Tue Aug 17** tax pilot live (coordination); **M12 Fri Aug 20** paid-conversion and hiring gate; **T-01**, **T-02**, **N-02** close | 97% / **114%** |
| S22 | Aug 23 – Sep 3, 2027 | PH3 | A-03 (0.5), A-04 (2.5) | A-03 (3.5), A-04 (2.5), F-06 (1), I-01 (2.25), K-01 (1.5), P-04 (1.5) | **M13 Tue Aug 31** 8879 with provider KBA, delivery, K-1 release; Sep 1 window opens for tax and EBP firms | 20% / **107%** |
| S23 | Sep 6 – Sep 17, 2027 | PH3 | A-03 (1), A-04 (2.5), A-05 (1.5), I-01 (0.5), K-01 (2), P-04 (1) | A-03 (2.5), A-04 (4), A-05 (3), F-06 (0.5), I-01 (1), P-04 (1) | Mini-freeze Sep 8–15 and the Sep 15 deadline; **A-03** closes; **A-05** window opens | 56% / **105%** |
| S24 | Sep 20 – Oct 1, 2027 | PH3 | A-04 (3.5), A-05 (2.5), A-06 (4), P-04 (0.5) | A-04 (4.25), A-05 (4), A-06 (2), K-01 (2.5), P-04 (2) | Mini-freeze Sep 23–30 and the Sep 30 deadline; C8 adjustments frozen; **F-06** DS tier 3 closes | 69% / **129%** |
| S25 | Oct 4 – Oct 15, 2027 | PH3 | A-04 (3.5), A-05 (1.5), A-06 (3.5), K-01 (0.5), N-04 (1), P-04 (1) | A-04 (4.5), A-05 (4.5), A-06 (0.5), K-01 (0.5), N-04 (3.75), P-04 (1.5), P-11 (0.5) | Mini-freeze Oct 8–15; **M14 Fri Oct 15** extension season closes, Type II report, re-baseline #4; **N-04** starts | 72% / **138%** |
| S26 | Oct 18 – Oct 29, 2027 | PH3 | A-04 (2), A-05 (3), A-06 (4), N-04 (1.5), P-04 (1), P-11 (1.5), T-03 (1) | A-04 (5), A-05 (4), A-06 (2.5), I-01 (0.5), K-01 (0.5), N-04 (3.5), P-11 (0.5), T-03 (3) | Oct 20 window closes; **T-03** TY2027 readiness starts; **P-04** review grammar and **K-01** close | 78% / **146%** |
| S27 | Nov 1 – Nov 12, 2027 | PH3 | A-04 (2), A-05 (2), A-07 (3.5), N-04 (0.75), P-11 (3.5), T-03 (0.5) | A-04 (4.5), A-05 (5), A-06 (4), A-07 (1.75), I-01 (0.75), N-04 (4.5), T-03 (4.5) | **A-07** completion, release and archive starts; pen test #2 (Nov) | 69% / **187%** |
| S28 | Nov 15 – Nov 26, 2027 | PH3 | A-04 (0.5), A-05 (0.5), A-06 (2), A-07 (2), N-04 (2.25), P-11 (3.5), T-03 (2) | A-04 (4.25), A-05 (4.5), A-06 (2.5), A-07 (2.5), N-04 (4.5), P-11 (1), T-03 (3.5) | Thanksgiving sprint; **A-04** planning closes (J04 planning slice) | 79% / **189%** |
| S29 | Nov 29 – Dec 10, 2027 | PH3 | A-05 (1.5), A-06 (2.5), A-07 (3.5), N-04 (1.25), P-10 (6.5), P-11 (1.5), R-02 (0.5) | A-05 (5), A-06 (2.5), A-07 (1.75), I-01 (1.25), N-04 (3.75), P-10 (2.5), P-11 (2), R-02 (2.5), T-03 (2.5) | **M15 Fri Dec 10** season-ready 2028 (R4): notices live (J09 P0), EBP P0 and planning in production; C10 frozen; **T-03**, **N-04** close | 97% / **177%** |
| S30 | Dec 13 – Dec 24, 2027 | PH3 | A-05 (1), A-06 (1.5), A-07 (2), P-10 (4), P-11 (0.5), R-02 (1.5) | A-05 (3), A-06 (3), A-07 (1), P-10 (1), P-11 (0.5), R-02 (1.5) | Completion, release, archive and runtime-v2 schemas in production by Dec 24; C6 v2 and C18 frozen; **A-06** and **F-09** close | 98% / **124%** |
| S31 | Dec 27 – Jan 7, 2028 | PH4 | A-05 (1), A-07 (2.5), P-09 (2.5), P-10 (2.5), P-11 (1) | A-05 (4), A-07 (2.75), P-09 (2.5), R-02 (1.5) | Jan 1 freeze begins (PW3); **A-05** closes (EBP-07 by Jan 7); **P-09** run dock starts | **111%** / **168%** |
| S32 | Jan 10 – Jan 21, 2028 | PH4 | A-07 (3), P-09 (2.5), P-10 (2.5), P-11 (1), T-04 (2) | A-07 (2.75), P-09 (2.5), P-10 (1), R-02 (3), T-04 (5) | **T-04** return workspace starts; C17 Workbench tool registry frozen | 77% / **134%** |
| S33 | Jan 24 – Feb 4, 2028 | PH4 | A-07 (4.5), P-05 (0.5), P-09 (1.5), P-10 (3.5), P-11 (0.5), R-02 (0.5), T-04 (1.5) | A-07 (2.5), P-05 (2.25), P-09 (3.5), P-10 (1.5), P-11 (1), R-02 (3.5), T-04 (5.5), T-05 (0.5) | **P-05** collaboration starts; pre-window ADR P-69 drafted for **T-05** | 88% / **190%** |
| S34 | Feb 7 – Feb 18, 2028 | PH4 | A-07 (2.5), P-05 (1), P-09 (1), P-10 (2.75), P-11 (0.5), R-02 (1), T-04 (2.5) | A-07 (3.75), P-05 (3), P-09 (2), P-10 (2), R-02 (2.25), T-04 (4) | **P-09** and **P-11** close (dock, trace, renderer, OCR) | 79% / **160%** |
| S35 | Feb 21 – Mar 3, 2028 | PH4 | A-07 (4), P-05 (1), P-10 (4), T-04 (3), T-05 (0.75) | A-07 (1.75), I-01 (2), P-05 (2.5), P-10 (3), R-02 (3), T-04 (5.5), T-05 (3.5) | J12 P0 walkable (Mar 3); **R-02** closes; **T-05** window opens; chapter 01 closes **I-01** here (one post-freeze wire-up task sits in S39) | 90% / **199%** |
| S36 | Mar 6 – Mar 17, 2028 | PH4 | A-07 (1.5), P-10 (3.5), T-04 (2.5), T-05 (1.5) | A-07 (3), P-05 (2), P-10 (2.5), T-04 (4.5), T-05 (5) | **A-07** closes Mar 17: J03 P0 and J18 P0 walkable; Mar 15 deadline week (no production promotion) | 63% / **160%** |
| S37 | Mar 20 – Mar 31, 2028 | PH4 | P-10 (4.5), T-04 (1.5), T-05 (1) | P-05 (1.5), P-10 (1.5), T-04 (5.5), T-05 (5) | **M16 Tue Mar 21** release and archive flipped per firm; 1040 workspace shadow from Mar 20; **P-05** closes (J27 P0) | 49% / **127%** |
| S38 | Apr 3 – Apr 14, 2028 | PH4 | F-07 (1), P-10 (3.5), T-04 (3), T-05 (2) | F-07 (3.75), P-10 (3.5), T-04 (4.5), T-05 (3.5) | First report released (G8) and archived (G9) on Accrued by Apr 14; **P-10** runtime v2 closes; **F-07** starts | 67% / **143%** |
| S39 | Apr 17 – Apr 28, 2028 | PH5 | P-02 (1.25), T-04 (3.5), T-05 (2) | F-07 (3.75), I-01 (0.25), P-02 (1.5), T-04 (4), T-05 (5) | Apr 20 window closes; +15% gain only if auto-merge was earned; **T-04** closes; **P-02** search starts | 37% / **107%** |
| S40 | May 1 – May 12, 2028 | PH5 | I-02 (1.5), P-02 (3.5), T-05 (3), W-02 (1) | F-07 (3), I-02 (2), P-02 (3.5), T-05 (8), W-02 (5) | **M17 Tue May 2** 2028 extension-season release (J06 P0, J19 P0); **W-02** and **I-02** start | 50% / **159%** |
| S41 | May 15 – May 26, 2028 | PH5 | I-02 (2.5), P-02 (1.75), T-05 (2.5), W-02 (1.5) | F-07 (4.5), I-02 (3), T-05 (7), W-02 (5) | **P-02** search and command palette closes | 46% / **144%** |
| S42 | May 29 – Jun 9, 2028 | PH5 | F-07 (1), I-02 (1.5), T-05 (2.5), W-02 (2.5) | F-07 (3.5), I-02 (3), T-05 (6), W-02 (2.5) | Build sprint: **T-05** entity engines, **W-02** sessions, **I-02** Today brief | 42% / **111%** |
| S43 | Jun 12 – Jun 23, 2028 | PH5 | I-02 (1.5), T-05 (2.5), T-07 (0.5), W-02 (2.5) | F-07 (3), I-02 (2.25), T-05 (5), W-02 (3.5) | **F-07** and **I-02** close (Today brief in June); pre-window ADR amendment for **T-07** | 39% / **102%** |
| S44 | Jun 26 – Jul 7, 2028 | PH5 | C-01 (3.5), T-05 (1.5), T-07 (0.75), W-02 (1.5) | C-01 (5.5), T-05 (4.5), T-06 (0.5), T-07 (3.75), W-02 (1.5) | **T-05** closes (J08 P0 and J15 P0 paths); **C-01** close engine and **T-07** start; CLI-03 design board for **T-06** (pre-window) | 40% / **116%** |
| S45 | Jul 10 – Jul 21, 2028 | PH5 | A-08 (2.75), A-09 (2.5), C-01 (1.5), T-07 (2.5), W-01 (2.5), W-02 (1) | A-08 (4), A-09 (3), C-01 (6), T-07 (4.75), W-01 (1.5), W-02 (1.5) | **A-08**, **A-09** and **W-01** start; **W-02** closes; C20 catalogue frozen | 71% / **153%** |
| S46 | Jul 24 – Aug 4, 2028 | PH5 | A-08 (2.25), A-09 (3.5), C-01 (2.5), T-07 (1.75), W-01 (3) | A-08 (4.75), A-09 (4), C-01 (6.5), T-07 (5.25), W-01 (2.5) | **M18 Tue Aug 1** 1065 entity workspace live (J08 P0) | 72% / **170%** |
| S47 | Aug 7 – Aug 18, 2028 | PH5 | A-08 (2.75), A-09 (4.5), C-01 (3.5), G-04 (4), T-07 (1.75), W-01 (3) | A-08 (5), A-09 (4), C-01 (6.5), G-04 (1.5), T-07 (5.75), W-01 (3) | **T-07** closes (J07); **G-04** platform console starts | **108%** / **190%** |
| S48 | Aug 21 – Sep 1, 2028 | PH5 | A-08 (0.5), A-09 (4.5), C-01 (2), G-04 (3), W-01 (1.25) | A-08 (5.25), A-09 (4), C-01 (6.5), G-04 (2.5), W-01 (1) | **M18 Tue Aug 22** 1041 live; **W-01** closes (J14 P0 Sep 1); R4 Aug 25; Sep 1 window opens | 62% / **142%** |
| S49 | Sep 4 – Sep 15, 2028 | PH5 | A-08 (1.5), A-09 (3), C-01 (1.5), C-02 (3.5), G-04 (2.25), T-06 (2.25) | A-08 (6), A-09 (3.5), C-01 (6.25), C-02 (4.5), G-04 (1), T-06 (5.5) | **C-02** posting and **T-06** entity depth start (window); Sep 15 deadline | 88% / **224%** |
| S50 | Sep 18 – Sep 29, 2028 | PH5 | A-08 (1), A-09 (1), C-02 (3.5), G-04 (2), Q-05 (3), T-06 (2.75), T-08 (0.5) | A-08 (1.25), A-09 (1.5), C-01 (5.75), C-02 (3), F-08 (5), G-04 (1.5), Q-05 (3.25), T-06 (6), T-08 (4) | **M19 Fri Sep 29** group audit behind `ff.group_audit` (J20 P0), fieldwork depth live; **A-08**, **A-09** close; **F-08**, **T-08**, **Q-05** start; C12 frozen | 86% / **262%** |
| S51 | Oct 2 – Oct 13, 2028 | PH5 | C-01 (0.5), C-02 (3.5), F-08 (1), G-04 (0.5), Q-05 (3.25), T-06 (1.75), T-08 (1.5) | C-01 (2), C-02 (4), F-08 (6), G-04 (1), Q-05 (3.5), T-06 (5.5), T-08 (4) | **C-01** and **G-04** close (J02 P0, J16 P0); Oct 15 deadline | 75% / **218%** |
| S52 | Oct 16 – Oct 27, 2028 | PH6 | C-02 (4), F-08 (2.5), K-03 (4.5), Q-05 (4), T-06 (1), T-08 (3) | C-02 (4.5), F-08 (5.5), K-03 (4), Q-05 (4.25), T-06 (6.5), T-08 (4) | **K-03** templates v2 and Sheets starts; Oct 20 window closes | **105%** / **213%** |
| S53 | Oct 30 – Nov 10, 2028 | PH6 | C-02 (3.5), F-08 (1), K-03 (3), Q-05 (2), T-06 (1.25), T-08 (2.25) | C-02 (5), F-08 (5.5), K-03 (3.5), Q-05 (3.75), T-06 (6.5), T-08 (5.5) | **M20 Tue Oct 31** CAS live on October closes (J10 read-only path) | 72% / **220%** |
| S54 | Nov 13 – Nov 24, 2028 | PH6 | C-02 (2.5), K-03 (5), Q-05 (0.5), T-06 (2), T-08 (1.75) | C-02 (4.5), F-08 (5.5), K-03 (2.5), Q-05 (1.5), T-06 (6), T-08 (6) | Thanksgiving sprint; **Q-05** closes (J18 full); W1 posting delta pen test (Nov) | 72% / **214%** |
| S55 | Nov 27 – Dec 8, 2028 | PH6 | C-02 (1.5), F-08 (2), K-03 (5), T-06 (1.25) | C-02 (4), F-08 (5.5), K-03 (4), T-06 (5.5), T-08 (6) | **M21 Fri Dec 8** season-ready 2029: W1 posting for non-attest clients, TY2028 tools, QM; **C-02**, **T-06**, **T-08**, **F-08** close | 54% / **185%** |
| S56 | Dec 11 – Dec 22, 2028 | PH6 | K-03 (4.5), N-03 (4) | K-03 (4), N-03 (3.75) | **N-03** mailbox starts; Dec 15 SQMS evaluation supported by Q-05 | 47% / 57% |
| S57 | Dec 25 – Jan 5, 2029 | PH6 | K-03 (3), N-03 (2.25) | K-03 (3.5), N-03 (2.75) | Jan 1 freeze (PW5); holiday sprint | 59% / 94% |
| S58 | Jan 8 – Jan 19, 2029 | PH6 | A-10 (0.5), K-03 (2), N-03 (3) | A-10 (3.5), K-03 (4.5), N-03 (3.75) | **A-10** statements studio starts | 37% / **106%** |
| S59 | Jan 22 – Feb 2, 2029 | PH6 | K-03 (1), K-04 (4.5), N-03 (2.75), R-03 (2) | A-10 (7.5), K-03 (4), K-04 (4), N-03 (4), R-03 (1.75) | **K-04** Board and triggers and **R-03** portal depth start; C14 frozen | 69% / **191%** |
| S60 | Feb 5 – Feb 16, 2029 | PH6 | A-10 (2), K-03 (3), K-04 (2.5), N-03 (3.25), R-03 (1.75) | A-10 (6.5), K-03 (2.5), K-04 (4.5), N-03 (3.25), R-03 (2) | **K-03** closes; W6 send-as delta pen test (Feb) | 84% / **168%** |
| S61 | Feb 19 – Mar 2, 2029 | PH6 | A-10 (1), I-03 (1), K-04 (3), N-03 (3.25), R-03 (1.5) | A-10 (7.5), I-03 (4), K-04 (4.5), N-03 (2.25), R-03 (2) | **I-03** insights starts | 66% / **182%** |
| S62 | Mar 5 – Mar 16, 2029 | PH6 | A-10 (3), I-03 (1.25), K-04 (2.5), N-03 (1.25), R-03 (0.75), X-01 (1.5) | A-10 (5.5), I-03 (4), K-04 (4), N-03 (0.5), R-03 (2.5), X-01 (4) | **X-01** attest core starts; **N-03** closes (J10 full, J16 full) | 69% / **184%** |
| S63 | Mar 19 – Mar 30, 2029 | PH6 | A-10 (1.5), I-03 (1), K-04 (3), R-03 (1), W-03 (2.75), X-01 (1) | A-10 (5.5), I-03 (4), K-04 (4.5), R-03 (1.75), W-03 (2), X-01 (5) | **W-03** agent library starts; **R-03** closes (J09, J12, J19 full) | 69% / **204%** |
| S64 | Apr 2 – Apr 13, 2029 | PH6 | A-10 (0.5), I-03 (1), K-04 (5), W-03 (2.75), X-01 (3) | A-10 (2.5), I-03 (3), K-04 (4.5), W-03 (4.25), X-01 (2.5) | **A-10** closes (J21 P0) | 83% / **150%** |
| S65 | Apr 16 – Apr 27, 2029 | PH6 | A-11 (2.5), I-03 (2), K-04 (2.5), W-03 (3.5), X-01 (3) | A-11 (2.5), I-03 (4.25), K-04 (5.5), W-03 (2.5), X-01 (4.5) | **M22 Fri Apr 27** engine core: **K-04** closes (J13 and the engine-based P0 paths of J04, J22–J26); **A-11** starts | 91% / **173%** |
| S66 | Apr 30 – May 11, 2029 | PH7 | A-11 (2), I-03 (1.75), T-09 (0.5), W-03 (4), X-01 (2.75) | A-11 (2.5), I-03 (3.5), T-09 (3), W-03 (2.75), X-01 (5.5) | **T-09** advisory starts; spill-list checkpoint | 61% / **128%** |
| S67 | May 14 – May 25, 2029 | PH7 | A-11 (3), K-05 (2), T-09 (1), W-03 (0.5), X-01 (5.5) | A-11 (2), I-03 (2), K-05 (2), T-09 (4.5), W-03 (3), X-01 (5) | **K-05** learning layer starts; **I-03** closes | 67% / **137%** |
| S68 | May 28 – Jun 8, 2029 | PH7 | A-11 (1), K-05 (3), T-09 (1), X-01 (4.25), X-02 (2.5), X-03 (0.5) | A-11 (3.5), K-05 (3.5), T-09 (4), W-03 (2), X-01 (7.5), X-02 (2), X-03 (3.5) | **X-02** and **X-03** start; **A-11** closes (J04, J23 full) | 68% / **192%** |
| S69 | Jun 11 – Jun 22, 2029 | PH7 | G-03 (3.25), K-05 (3), T-09 (1), W-03 (1), W-04 (1.5), X-01 (2.5), X-02 (2), X-03 (0.5) | K-05 (3.5), T-09 (4), W-04 (2.5), X-01 (8), X-02 (2.5), X-03 (4) | **X-01** and **W-03** close (J01 P0, J11 P0); **W-04** and **G-03** start; API and MCP delta pen test (Jul) | 82% / **181%** |
| S70 | Jun 25 – Jul 6, 2029 | PH7 | G-03 (5.5), I-04 (1), K-05 (1), T-09 (0.5), X-02 (3), X-03 (3) | G-03 (2.5), I-04 (4), K-05 (4.25), T-09 (4), W-04 (5), X-02 (2), X-03 (4) | **I-04** practice economics starts; **T-09** closes (J08, J15 full) | 78% / **190%** |
| S71 | Jul 9 – Jul 20, 2029 | PH7 | G-03 (6), I-04 (3.25), W-04 (0.5), X-02 (0.5), X-03 (2) | G-03 (2), I-04 (3), K-05 (4), W-04 (5), X-02 (1), X-03 (1.5) | Build and hardening sprint for the PH7 leaf modules | 68% / **122%** |
| S72 | Jul 23 – Aug 3, 2029 | PH7 | G-03 (5), I-04 (2), K-05 (0.5), W-04 (2.5), X-02 (0.5) | G-03 (1), I-04 (5.5), K-05 (2), W-04 (5), X-02 (1), X-03 (4) | **K-05** and **X-02** close (J24, J25, J27 full) | 58% / **137%** |
| S73 | Aug 6 – Aug 17, 2029 | PH7 | G-03 (1), I-04 (1), W-04 (1.25) | G-03 (1), I-04 (2), W-04 (1), X-03 (2) | **M23 Fri Aug 17** all 28 journeys walkable in production; **X-03**, **W-04**, **G-03**, **I-04** and **Q-03** close | 18% / 44% |
| S74 | Aug 20 – Aug 31, 2029 | PH7 | — | — | **M24 Fri Aug 31** GA: 30 days within SLO, runbooks rehearsed; **Q-04** closes | 0% / 0% |

---

## 7.5 Load chart, over-allocation and re-balancing

### 7.5.1 Capacity model

Available capacity per founder per sprint is chapter 01 §1.8.1's formula, applied to every sprint:

`planned = 2 weeks × 14 tasks × 0.85 (two-founder factor) × holiday factor × learning gain × coding share × 0.775 (after the 22.5% reserve) × (1 − pilot support)`

| Input | Value |
|---|---|
| Coding share | N 100%; AY 60% in S0–S6, 75% from S7 (Jan 25, 2027) |
| Holiday factor | ×0.9 in the Thanksgiving sprints (S2, S28, S54); ×0.6 in the Christmas and New Year sprints (S4, S5, S30, S31, S57) |
| Learning gain | +10% from S19; +15% (replacing it) from S39, only if ADR-086 auto-merge is earned |
| Pilot support | 0% to S13; 10% S14–S15; 15% S16–S20; 25% S21–S25 (Aug 9 – Oct 15, 2027); 12% S26–S30; 30% S31–S38; 15% S39–S48; 25% S49–S51; 15% S52–S56; 30% S57–S65; 15% S66–S74 |
| Reserve pool | 22.5% of gross coding; funds Q-03, F-01 and 20 tasks of N's Q-01 (pro rata over S0–S5) |
| AY non-code pool | the complement of AY's coding share; funds F-09 to S30, then partners, sales and assurance paperwork |

The model reproduces chapter 01's per-sprint excerpt (S0–S21) exactly and its phase capacities within 1% (PH5 228 against 226; PH6 216 against 215; PH7 162 against 160, the last including the GA sprint S74). Demand is the CSV size of every task in the sprint, by the founder in its `lead` column, in the pool its epic is funded from.

### 7.5.2 Load chart per founder per sprint

**Over-allocated sprints (planned demand >100% of planned capacity):**
- **N:** S1–S8, S10, S12–S13, S31, S47, S52 (14 sprints).
- **AY:** S1–S12, S14–S55, S58–S72 (69 sprints).

Reserve, support and non-code pools are shown for completeness: Q-03 fits the reserve over the horizon (N 384 of 428, AY 276 of 316), Q-04 fits pilot support (N 245 of 247, AY 186 of 186), and F-09 fits AY's non-code time to Dec 2027 (189 of the horizon's 535; the rest is chapter 01's other 21 FW of non-code work). The reserve overruns materially only in S0–S1 (F-01 front-loaded: N by 5.4 and 2.8 tasks); elsewhere it overruns by at most 1.3 tasks, in about two dozen sprints. An overrun eats planned capacity, which §7.5.4 accounts for.

| Sprint | Dates | Phase | Support | N avail | N demand | N load | AY avail | AY demand | AY load | Flag | Reserve N / AY (demand of avail) | Support demand / avail | AY non-code demand / avail | Notes |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| S0 | Oct 19 – Oct 30, 2026 | PH0 | 0% | 18.4 | 13.5 | 73% | 11.1 | 10.5 | 95% |  | 10.7 of 5.4 / 3.5 of 3.2 | 0.0 / 0.0 | 10.8 / 11.2 | N reserve over by 5.4; AY reserve over by 0.3 |
| S1 | Nov 2 – Nov 13 | PH1 | 0% | 18.4 | 24.8 | 135% | 11.1 | 14.5 | 131% | **over: N + AY** | 8.2 of 5.4 / 1.0 of 3.2 | 0.0 / 0.0 | 11.0 / 11.2 | N reserve over by 2.8 |
| S2 | Nov 16 – Nov 27 | PH1 | 0% | 16.6 | 21.0 | 127% | 10.0 | 14.2 | 143% | **over: N + AY** | 3.7 of 4.8 / 0.0 of 2.9 | 0.0 / 0.0 | 9.5 / 10.1 | Thanksgiving ×0.9 |
| S3 | Nov 30 – Dec 11 | PH1 | 0% | 18.4 | 27.8 | 151% | 11.1 | 19.8 | 178% | **over: N + AY** | 4.0 of 5.4 / 0.0 of 3.2 | 0.0 / 0.0 | 10.0 / 11.2 |  |
| S4 | Dec 14 – Dec 25 | PH1 | 0% | 11.1 | 17.8 | 161% | 6.6 | 20.0 | 301% | **over: N + AY** | 2.7 of 3.2 / 0.0 of 1.9 | 0.0 / 0.0 | 5.5 / 6.7 | holiday ×0.6 |
| S5 | Dec 28 – Jan 8, 2027 | PH1 | 0% | 11.1 | 15.5 | 140% | 6.6 | 16.2 | 245% | **over: N + AY** | 0.7 of 3.2 / 0.0 of 1.9 | 0.0 / 0.0 | 5.0 / 6.7 | holiday ×0.6 |
| S6 | Jan 11 – Jan 22, 2027 | PH1 | 0% | 18.4 | 22.0 | 119% | 11.1 | 21.2 | 192% | **over: N + AY** | 5.0 of 5.4 / 4.5 of 3.2 | 0.0 / 0.0 | 9.2 / 11.2 | AY reserve over by 1.3 |
| S7 | Jan 25 – Feb 5 | PH2 | 0% | 18.4 | 21.0 | 114% | 13.8 | 26.0 | 188% | **over: N + AY** | 4.8 of 5.4 / 5.0 of 4.0 | 0.0 / 0.0 | 5.5 / 7.0 | AY reserve over by 1.0; AY 75% coding from here |
| S8 | Feb 8 – Feb 19 | PH2 | 0% | 18.4 | 21.0 | 114% | 13.8 | 25.5 | 184% | **over: N + AY** | 5.0 of 5.4 / 3.5 of 4.0 | 0.0 / 0.0 | 6.0 / 7.0 |  |
| S9 | Feb 22 – Mar 5 | PH2 | 0% | 18.4 | 17.2 | 94% | 13.8 | 23.8 | 172% | **over: AY** | 5.5 of 5.4 / 4.5 of 4.0 | 0.0 / 0.0 | 6.2 / 7.0 | N reserve over by 0.1; AY reserve over by 0.5 |
| S10 | Mar 8 – Mar 19 | PH2 | 0% | 18.4 | 21.5 | 117% | 13.8 | 20.2 | 146% | **over: N + AY** | 6.0 of 5.4 / 4.5 of 4.0 | 0.0 / 0.0 | 6.0 / 7.0 | N reserve over by 0.6; AY reserve over by 0.5 |
| S11 | Mar 22 – Apr 2 | PH2 | 0% | 18.4 | 18.0 | 98% | 13.8 | 17.0 | 123% | **over: AY** | 6.0 of 5.4 / 3.5 of 4.0 | 0.0 / 0.0 | 5.0 / 7.0 | N reserve over by 0.6 |
| S12 | Apr 5 – Apr 16 | PH2 | 0% | 18.4 | 21.0 | 114% | 13.8 | 17.2 | 125% | **over: N + AY** | 5.2 of 5.4 / 2.0 of 4.0 | 0.0 / 0.0 | 4.8 / 7.0 |  |
| S13 | Apr 19 – Apr 30 | PH2 | 0% | 18.4 | 21.2 | 115% | 13.8 | 13.0 | 94% | **over: N** | 6.2 of 5.4 / 3.5 of 4.0 | 0.0 / 0.0 | 5.5 / 7.0 | N reserve over by 0.9 |
| S14 | May 3 – May 14 | PH2 | 10% | 16.6 | 13.0 | 78% | 12.5 | 17.5 | 141% | **over: AY** | 6.2 of 5.4 / 5.2 of 4.0 | 6.8 / 3.2 | 5.0 / 7.0 | N reserve over by 0.9; AY reserve over by 1.2 |
| S15 | May 17 – May 28 | PH2 | 10% | 16.6 | 12.0 | 72% | 12.5 | 14.0 | 112% | **over: AY** | 4.8 of 5.4 / 4.2 of 4.0 | 3.0 / 3.2 | 5.0 / 7.0 | AY reserve over by 0.2 |
| S16 | May 31 – Jun 11 | PH3 | 15% | 15.7 | 11.8 | 75% | 11.8 | 23.0 | 196% | **over: AY** | 5.2 of 5.4 / 4.0 of 4.0 | 4.8 / 4.8 | 5.5 / 7.0 |  |
| S17 | Jun 14 – Jun 25 | PH3 | 15% | 15.7 | 14.0 | 89% | 11.8 | 23.0 | 196% | **over: AY** | 4.0 of 5.4 / 3.5 of 4.0 | 4.8 / 4.8 | 6.0 / 7.0 |  |
| S18 | Jun 28 – Jul 9 | PH3 | 15% | 15.7 | 15.2 | 97% | 11.8 | 23.8 | 202% | **over: AY** | 5.5 of 5.4 / 4.2 of 4.0 | 4.8 / 4.8 | 6.0 / 7.0 | N reserve over by 0.1; AY reserve over by 0.2 |
| S19 | Jul 12 – Jul 23 | PH3 | 15% | 17.2 | 13.0 | 75% | 12.9 | 22.2 | 172% | **over: AY** | 6.0 of 5.9 / 5.2 of 4.4 | 5.2 / 5.3 | 5.0 / 7.0 | N reserve over by 0.1; AY reserve over by 0.8; +10% learning gain |
| S20 | Jul 26 – Aug 6 | PH3 | 15% | 17.2 | 13.8 | 80% | 12.9 | 21.2 | 164% | **over: AY** | 4.2 of 5.9 / 4.0 of 4.4 | 5.2 / 5.3 | 5.8 / 7.0 |  |
| S21 | Aug 9 – Aug 20 | PH3 | 25% | 15.2 | 14.8 | 97% | 11.4 | 13.0 | 114% | **over: AY** | 5.8 of 5.9 / 3.8 of 4.4 | 8.8 / 8.9 | 5.5 / 7.0 |  |
| S22 | Aug 23 – Sep 3 | PH3 | 25% | 15.2 | 3.0 | 20% | 11.4 | 12.2 | 107% | **over: AY** | 5.8 of 5.9 / 4.5 of 4.4 | 8.8 / 8.9 | 5.8 / 7.0 | AY reserve over by 0.1 |
| S23 | Sep 6 – Sep 17 | PH3 | 25% | 15.2 | 8.5 | 56% | 11.4 | 12.0 | 105% | **over: AY** | 5.0 of 5.9 / 3.8 of 4.4 | 8.8 / 8.9 | 5.2 / 7.0 |  |
| S24 | Sep 20 – Oct 1 | PH3 | 25% | 15.2 | 10.5 | 69% | 11.4 | 14.8 | 129% | **over: AY** | 5.8 of 5.9 / 3.5 of 4.4 | 8.8 / 8.9 | 5.5 / 7.0 |  |
| S25 | Oct 4 – Oct 15 | PH3 | 25% | 15.2 | 11.0 | 72% | 11.4 | 15.8 | 138% | **over: AY** | 5.0 of 5.9 / 3.5 of 4.4 | 8.8 / 8.9 | 5.5 / 7.0 |  |
| S26 | Oct 18 – Oct 29 | PH3 | 12% | 17.9 | 14.0 | 78% | 13.4 | 19.5 | 146% | **over: AY** | 5.0 of 5.9 / 3.8 of 4.4 | 4.2 / 4.3 | 6.0 / 7.0 |  |
| S27 | Nov 1 – Nov 12 | PH3 | 12% | 17.9 | 12.2 | 69% | 13.4 | 25.0 | 187% | **over: AY** | 6.5 of 5.9 / 5.0 of 4.4 | 4.2 / 4.3 | 5.2 / 7.0 | N reserve over by 0.6; AY reserve over by 0.6 |
| S28 | Nov 15 – Nov 26 | PH3 | 12% | 16.1 | 12.8 | 79% | 12.1 | 22.8 | 189% | **over: AY** | 5.5 of 5.3 / 3.0 of 4.0 | 4.0 / 3.8 | 4.0 / 6.3 | Thanksgiving ×0.9; N reserve over by 0.2 |
| S29 | Nov 29 – Dec 10 | PH3 | 12% | 17.9 | 17.2 | 97% | 13.4 | 23.8 | 177% | **over: AY** | 5.0 of 5.9 / 4.0 of 4.4 | 4.2 / 4.3 | 6.0 / 7.0 |  |
| S30 | Dec 13 – Dec 24, 2027 | PH3 | 12% | 10.7 | 10.5 | 98% | 8.0 | 10.0 | 124% | **over: AY** | 3.0 of 3.5 / 3.2 of 2.7 | 2.5 / 2.6 | 2.0 / 4.2 | holiday ×0.6; AY reserve over by 0.6 |
| S31 | Dec 27 – Jan 7, 2028 | PH4 | 30% | 8.5 | 9.5 | 111% | 6.4 | 10.8 | 168% | **over: N + AY** | 2.5 of 3.5 / 2.5 of 2.7 | 6.5 / 6.4 | 0.0 / 4.2 | holiday ×0.6 |
| S32 | Jan 10 – Jan 21 | PH4 | 30% | 14.2 | 11.0 | 77% | 10.7 | 14.2 | 134% | **over: AY** | 6.2 of 5.9 / 4.8 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 | N reserve over by 0.4; AY reserve over by 0.3 |
| S33 | Jan 24 – Feb 4 | PH4 | 30% | 14.2 | 12.5 | 88% | 10.7 | 20.2 | 190% | **over: AY** | 4.5 of 5.9 / 5.5 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 | AY reserve over by 1.1 |
| S34 | Feb 7 – Feb 18 | PH4 | 30% | 14.2 | 11.2 | 79% | 10.7 | 17.0 | 160% | **over: AY** | 5.8 of 5.9 / 4.0 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 |  |
| S35 | Feb 21 – Mar 3 | PH4 | 30% | 14.2 | 12.8 | 90% | 10.7 | 21.2 | 199% | **over: AY** | 5.0 of 5.9 / 3.2 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 |  |
| S36 | Mar 6 – Mar 17 | PH4 | 30% | 14.2 | 9.0 | 63% | 10.7 | 17.0 | 160% | **over: AY** | 4.2 of 5.9 / 4.2 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 |  |
| S37 | Mar 20 – Mar 31 | PH4 | 30% | 14.2 | 7.0 | 49% | 10.7 | 13.5 | 127% | **over: AY** | 6.0 of 5.9 / 3.2 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 | N reserve over by 0.1 |
| S38 | Apr 3 – Apr 14 | PH4 | 30% | 14.2 | 9.5 | 67% | 10.7 | 15.2 | 143% | **over: AY** | 5.8 of 5.9 / 3.8 of 4.4 | 10.5 / 10.7 | 0.0 / 7.0 |  |
| S39 | Apr 17 – Apr 28 | PH5 | 15% | 18.0 | 6.8 | 37% | 13.5 | 14.5 | 107% | **over: AY** | 5.5 of 6.2 / 4.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 | AY reserve over by 0.1; +15% gain (if auto-merge earned) |
| S40 | May 1 – May 12 | PH5 | 15% | 18.0 | 9.0 | 50% | 13.5 | 21.5 | 159% | **over: AY** | 4.2 of 6.2 / 4.2 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S41 | May 15 – May 26 | PH5 | 15% | 18.0 | 8.2 | 46% | 13.5 | 19.5 | 144% | **over: AY** | 5.5 of 6.2 / 4.0 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S42 | May 29 – Jun 9 | PH5 | 15% | 18.0 | 7.5 | 42% | 13.5 | 15.0 | 111% | **over: AY** | 5.8 of 6.2 / 4.0 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S43 | Jun 12 – Jun 23 | PH5 | 15% | 18.0 | 7.0 | 39% | 13.5 | 13.8 | 102% | **over: AY** | 5.5 of 6.2 / 4.0 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S44 | Jun 26 – Jul 7 | PH5 | 15% | 18.0 | 7.2 | 40% | 13.5 | 15.8 | 116% | **over: AY** | 5.8 of 6.2 / 3.0 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S45 | Jul 10 – Jul 21 | PH5 | 15% | 18.0 | 12.8 | 71% | 13.5 | 20.8 | 153% | **over: AY** | 7.0 of 6.2 / 3.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 | N reserve over by 0.8 |
| S46 | Jul 24 – Aug 4 | PH5 | 15% | 18.0 | 13.0 | 72% | 13.5 | 23.0 | 170% | **over: AY** | 5.8 of 6.2 / 4.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 | AY reserve over by 0.1 |
| S47 | Aug 7 – Aug 18 | PH5 | 15% | 18.0 | 19.5 | 108% | 13.5 | 25.8 | 190% | **over: N + AY** | 4.5 of 6.2 / 3.5 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S48 | Aug 21 – Sep 1 | PH5 | 15% | 18.0 | 11.2 | 62% | 13.5 | 19.2 | 142% | **over: AY** | 5.0 of 6.2 / 4.0 of 4.6 | 9.2 / 5.6 | 0.0 / 7.0 |  |
| S49 | Sep 4 – Sep 15 | PH5 | 25% | 15.9 | 14.0 | 88% | 11.9 | 26.8 | 224% | **over: AY** | 5.0 of 6.2 / 4.2 of 4.6 | 9.2 / 9.3 | 0.0 / 7.0 |  |
| S50 | Sep 18 – Sep 29 | PH5 | 25% | 15.9 | 13.8 | 86% | 11.9 | 31.2 | 262% | **over: AY** | 4.5 of 6.2 / 4.0 of 4.6 | 9.2 / 9.3 | 0.0 / 7.0 |  |
| S51 | Oct 2 – Oct 13 | PH5 | 25% | 15.9 | 12.0 | 75% | 11.9 | 26.0 | 218% | **over: AY** | 5.5 of 6.2 / 4.5 of 4.6 | 9.2 / 9.3 | 0.0 / 7.0 |  |
| S52 | Oct 16 – Oct 27 | PH6 | 15% | 18.0 | 19.0 | 105% | 13.5 | 28.8 | 213% | **over: N + AY** | 5.5 of 6.2 / 3.8 of 4.6 | 4.5 / 5.6 | 0.0 / 7.0 |  |
| S53 | Oct 30 – Nov 10 | PH6 | 15% | 18.0 | 13.0 | 72% | 13.5 | 29.8 | 220% | **over: AY** | 5.5 of 6.2 / 4.5 of 4.6 | 4.5 / 5.6 | 0.0 / 7.0 |  |
| S54 | Nov 13 – Nov 24 | PH6 | 15% | 16.2 | 11.8 | 72% | 12.2 | 26.0 | 214% | **over: AY** | 5.5 of 5.5 / 3.5 of 4.2 | 4.0 / 5.0 | 0.0 / 6.3 | Thanksgiving ×0.9 |
| S55 | Nov 27 – Dec 8 | PH6 | 15% | 18.0 | 9.8 | 54% | 13.5 | 25.0 | 185% | **over: AY** | 5.0 of 6.2 / 3.5 of 4.6 | 4.8 / 5.6 | 0.0 / 7.0 |  |
| S56 | Dec 11 – Dec 22, 2028 | PH6 | 15% | 18.0 | 8.5 | 47% | 13.5 | 7.8 | 57% |  | 3.0 of 6.2 / 2.5 of 4.6 | 2.5 / 5.6 | 0.0 / 7.0 |  |
| S57 | Dec 25 – Jan 5, 2029 | PH6 | 30% | 8.9 | 5.2 | 59% | 6.7 | 6.2 | 94% |  | 2.5 of 3.7 / 3.2 of 2.8 | 6.5 / 6.7 | 0.0 / 4.2 | holiday ×0.6; AY reserve over by 0.5 |
| S58 | Jan 8 – Jan 19 | PH6 | 30% | 14.8 | 5.5 | 37% | 11.1 | 11.8 | 106% | **over: AY** | 5.5 of 6.2 / 5.5 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 | AY reserve over by 0.9 |
| S59 | Jan 22 – Feb 2 | PH6 | 30% | 14.8 | 10.2 | 69% | 11.1 | 21.2 | 191% | **over: AY** | 4.5 of 6.2 / 3.8 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 |  |
| S60 | Feb 5 – Feb 16 | PH6 | 30% | 14.8 | 12.5 | 84% | 11.1 | 18.8 | 168% | **over: AY** | 6.0 of 6.2 / 4.5 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 |  |
| S61 | Feb 19 – Mar 2 | PH6 | 30% | 14.8 | 9.8 | 66% | 11.1 | 20.2 | 182% | **over: AY** | 5.0 of 6.2 / 4.0 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 |  |
| S62 | Mar 5 – Mar 16 | PH6 | 30% | 14.8 | 10.2 | 69% | 11.1 | 20.5 | 184% | **over: AY** | 6.2 of 6.2 / 3.2 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 | N reserve over by 0.1 |
| S63 | Mar 19 – Mar 30 | PH6 | 30% | 14.8 | 10.2 | 69% | 11.1 | 22.8 | 204% | **over: AY** | 5.5 of 6.2 / 4.5 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 |  |
| S64 | Apr 2 – Apr 13 | PH6 | 30% | 14.8 | 12.2 | 83% | 11.1 | 16.8 | 150% | **over: AY** | 5.0 of 6.2 / 3.8 of 4.6 | 11.0 / 11.1 | 0.0 / 7.0 |  |
| S65 | Apr 16 – Apr 27 | PH6 | 30% | 14.8 | 13.5 | 91% | 11.1 | 19.2 | 173% | **over: AY** | 5.0 of 6.2 / 4.2 of 4.6 | 5.8 / 11.1 | 0.0 / 7.0 |  |
| S66 | Apr 30 – May 11 | PH7 | 15% | 18.0 | 11.0 | 61% | 13.5 | 17.2 | 128% | **over: AY** | 5.5 of 6.2 / 4.5 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S67 | May 14 – May 25 | PH7 | 15% | 18.0 | 12.0 | 67% | 13.5 | 18.5 | 137% | **over: AY** | 5.8 of 6.2 / 4.5 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S68 | May 28 – Jun 8 | PH7 | 15% | 18.0 | 12.2 | 68% | 13.5 | 26.0 | 192% | **over: AY** | 6.0 of 6.2 / 4.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 | AY reserve over by 0.1 |
| S69 | Jun 11 – Jun 22 | PH7 | 15% | 18.0 | 14.8 | 82% | 13.5 | 24.5 | 181% | **over: AY** | 5.0 of 6.2 / 3.0 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S70 | Jun 25 – Jul 6 | PH7 | 15% | 18.0 | 14.0 | 78% | 13.5 | 25.8 | 190% | **over: AY** | 4.8 of 6.2 / 3.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S71 | Jul 9 – Jul 20 | PH7 | 15% | 18.0 | 12.2 | 68% | 13.5 | 16.5 | 122% | **over: AY** | 5.5 of 6.2 / 3.8 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S72 | Jul 23 – Aug 3 | PH7 | 15% | 18.0 | 10.5 | 58% | 13.5 | 18.5 | 137% | **over: AY** | 5.2 of 6.2 / 4.5 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S73 | Aug 6 – Aug 17 | PH7 | 15% | 18.0 | 3.2 | 18% | 13.5 | 6.0 | 44% |  | 5.5 of 6.2 / 4.5 of 4.6 | 5.8 / 5.6 | 0.0 / 7.0 |  |
| S74 | Aug 20 – Aug 31, 2029 | PH7 | 15% | 18.0 | 0.0 | 0% | 13.5 | 0.0 | 0% |  | 0.0 of 6.2 / 0.0 of 4.6 | 9.2 / 5.6 | 0.0 / 7.0 |  |

### 7.5.3 Phase view and the two readings of a test row

| Phase | Sprints | Ch. 01 N demand / cap | CSV N demand / cap | N load | Ch. 01 AY demand / cap | CSV AY demand / cap | AY load | CSV team load | Team load without ADR-078 TEST rows | Residual after re-balance (as sized): N / AY | Residual (TEST rows covered by the velocity discount): N / AY |
|---|---|---|---|---:|---|---|---:|---:|---:|---|---|
| PH0 | S0 | 14 / 18 | 14 / 18 | 73% | 9 / 11 | 10 / 11 | 95% | 81% | 76% | 0 / 0 | 0 / 0 |
| PH1 | S1–S6 | 93 / 94 | 129 / 94 | 137% | 64 / 56 | 106 / 56 | 188% | 156% | 130% | 30 / 37 | 19 / 23 |
| PH2 | S7–S15 | 177 / 162 | 166 / 162 | 102% | 131 / 122 | 174 / 122 | 143% | 120% | 94% | 8 / 54 | 4 / 5 |
| PH3 | S16–S30 | 248 / 238 | 182 / 238 | 77% | 192 / 178 | 282 / 178 | 158% | 111% | 90% | 0 / 62 | 0 / 5 |
| PH4 | S31–S38 | 110 / 108 | 82 / 108 | 76% | 79 / 81 | 129 / 81 | 160% | 112% | 91% | 0 / 22 | 0 / 0 |
| PH5 | S39–S51 | 201 / 226 | 142 / 228 | 62% | 165 / 169 | 273 / 171 | 159% | 104% | 89% | 0 / 48 | 0 / 26 |
| PH6 | S52–S65 | 215 / 215 | 152 / 216 | 70% | 171 / 161 | 275 / 162 | 170% | 113% | 93% | 0 / 54 | 0 / 19 |
| PH7 | S66–S74 | 129 / 160 | 90 / 162 | 55% | 91 / 120 | 153 / 122 | 126% | 86% | 71% | 0 / 8 | 0 / 0 |
| **Total** | S0–S74 | 1,187 / 1,221 | 957 / 1227 | 78% | 902 / 898 | 1402 / 903 | 155% | 111% | 91% | 39 / 285 | 23 / 78 |

**Reading the table.**
- *As sized* counts every CSV row at its size. The team is at 111% over the horizon, 156% in PH1 and 120% in PH2.
- *Without ADR-078 TEST rows* drops the 423 planned-pool rows whose type is TEST. Chapter 01 §1.8.1 derives 14 tasks/FW from the measured rate "minus ~25% for restored independent tests and cross-review", and its sizing (§1.8.2) has no separate test tasks. On that reading the test rows are already paid for, and the team is at 91%.
- The truth is between the two and is measurable: in S1–S2, log the session time of TEST rows separately from feature rows (§7.7, gate M3).
- The *residual* columns are what is left after the moves of §7.5.4, by phase. They are the amounts the cut tiers, date fallbacks, hires and spill list must cover.

**Epic sizing against chapter 01.** CSV size exceeds chapter 01's epic size (FW × 14) by 20% or more in 26 epics: **A-01** (+29%), **A-03** (+39%), **A-04** (+25%), **A-06** (+23%), **A-09** (+21%), **A-11** (+23%), **F-03** (+21%), **G-01** (+21%), **G-02** (+22%), **G-04** (+25%), **I-01** (+21%), **I-02** (+23%), **K-02** (+23%), **N-03** (+24%), **P-01** (+23%), **P-03** (+24%), **P-05** (+23%), **P-06** (+24%), **P-08** (+21%), **Q-05** (+29%), **R-02** (+24%), **R-03** (+21%), **T-03** (+21%), **W-03** (+23%), **W-04** (+24%), **X-02** (+21%). Across the build epics the CSVs carry 2,388 tasks against chapter 01's ≈2,120 (+13%), close to chapter 01's own "+12% scope" pessimistic scenario (§1.8.8). The per-epic table is in §7.5.5.

### 7.5.4 Re-balancing moves

The moves follow chapter 01's order for absorbing slip (§1.8.6) and its lane rules (§1.3.1). None changes a chapter 01 date. They were simulated sprint by sprint over S0–S74, and the per-sprint candidates appear in §7.3. Each is confirmed or rejected at that sprint's Contract Monday and recorded in the capacity ledger.

| # | Move | Rule it follows | Simulated effect (as sized) | Simulated effect (TEST rows covered) |
|---|---|---|---|---|
| 1 | **Unused reserve pays for same-sprint ADR-078 test rows.** Where a founder's reserve is not used by Q-03 in a sprint (notably AY in S1–S5, before back-fill starts), it funds that founder's independent-test rows | Reserve "never spent on features"; tests are its purpose (§1.8.1) | 82 tasks | n/a |
| 2 | **Lane swaps AY → N (and amber N → AY) in the same sprint.** Eligible: AY's amber backend, data, docs, ops, agent and admin-screen frontend (ADM-*, G-*, Q-*). Never: test rows (ADR-078 needs the non-author), design, vendor, red-zone work to AY | Chapter 01 lanes: N ≈ 1,190 tasks including admin and ops frontend on established kits; red stays with N | 93 tasks (98) | 130 tasks (144) |
| 3 | **Pull earlier inside the chapter 01 window** when predecessors are placed and the founder (or an eligible other founder) has room | Epic windows are build windows (§1.4) | 27 tasks (22) | 39 tasks (29) |
| 4 | **Defer inside the chapter 01 window**, never past a successor or the window end | Same | 147 tasks (128) | 104 tasks (89) |
| | **Residual after 1–4** | | **N 39, AY 285** | **N 23, AY 78** |

A wider lane change (N also building AY's non-admin screens on established kits from S11) was simulated and buys only about 4 more tasks, so it is not recommended. The residual is a timing problem, not a lane-rule problem: in every sprint where AY is still over after the moves (S4–S10, S14–S20, S27–S35, S47–S55, S62–S65), N is full too, and N's remaining room, about 100 tasks, sits in sprints (S21–S26, S36–S45, S56–S59, S66–S74) that AY's over-capacity work cannot reach inside its epic windows.

**What covers the residual, in chapter 01's order.**

| Order | Lever (chapter 01) | Capacity it frees | Where it applies | Covers |
|---|---|---|---|---|
| 5 | **Cut tier 1** at M3 or M5, deferred into PH5 slack, not dropped | ≈32 tasks | PH1–PH2 | With tier 2 pulled forward, the PH1–PH2 residual on the "TEST rows covered" reading (51 tasks) |
| 6 | **Cut tier 2** at M8 or M14 | ≈29 tasks | PH2–PH3 | PH3 residual |
| 7 | **Unplanned Saturdays** before M8 and M13 only, measured | — | S13–S15, S20–S22 | Not planned capacity |
| 8 | **Tier 3 date moves** (shadow Jun 1 → Jun 15; R3 Jul 13 → Jul 27; 8879 record mode) | ≈1 sprint of team capacity | PH2–PH3 | Needed on the "as sized" reading |
| 9 | **Tax pilot NO-GO at M8** | ≈110 tasks in S16–S21 | PH3 | Needed on the "as sized" reading if tier 3 is not enough |
| 10 | **Hires at M12** (two engineers from Oct 4, 2027) | ≈200 by S38, ≈440 by S51 | PH4–PH6 | Covers PH4–PH6 on either reading |
| 11 | **PH6–PH7 spill list** (I-04, G-03, X-02, W-04, K-05, X-03, T-09, R-03, I-03, Q-05 depth) | ≈207 tasks | PH6–PH7 | Covers PH6–PH7 on either reading; GA keeps Aug 31, 2029 |

**Tier 1 and tier 2 mapped to CSV tasks.** The savings are chapter 01's; the task IDs are the CSV rows that carry the cut scope.

| Tier | Cut (chapter 01 §1.8.4) | Saves | CSV tasks carrying the cut scope |
|---|---|---:|---|
| 1 | CLI-07 and CLI-08 record-only (no questionnaire, NAS engine or AI pre-screen) | 6 | P-07-T35 (S9), P-07-T41 (S10), P-07-T46 (S10), P-07-T48 (S11) |
| 1 | ENG-13 roll-forward re-skin after S31 | 4 | P-07-T55 (S13), P-07-T60 (S14) |
| 1 | AUD-06 read-only from file import; live ledger read to Sep 2027 | 6 | A-02-T26 (S13), A-02-T30 (S14), A-02-T23 (S12) |
| 1 | HOME-01 lite; SHL-07 without the lineage tab | 5 | I-01-T06 (S11), I-01-T10, I-01-T11 (S12), I-01-T13 (S14); SHL-07 tasks of P-03 |
| 1 | ADM-07 minimal explorer; KNW-01 read-only catalog over imports | 6 | G-02-T09, G-02-T10 (S10); K-01-T03, K-01-T04 (S11) |
| 1 | POR-20 editor replaced by admin import; ADM-10 logo, name and sender only | 5 | R-01-T23, R-01-T25 (S11); R-01-T26, R-01-T28 (S12) |
| 2 | AUD-10 SOC 1 reliance to Q2 2028 | 6 | A-04-T37 (S28) and its A-04 service rows |
| 2 | AUD-18 EQR and POR-15 governance room to Q2 2028 | 8 | A-07-T17 (S29), A-07-T18 (S30); R-02-T12 (S32), R-02-T21 (S34) |
| 2 | EBP-08 participant accounts to Q1 2028 | 3 | A-05-T46 (S29), A-05-T52 (S30) |
| 2 | KNW-02 methodology versions and import review to 2028 | 8 | K-01-T07 (S12), K-01-T14 (S18), K-01-T19 (S22), K-01-T23 (S24) |
| 2 | BND-03 organizer editor replaced by organizer import | 4 | T-03-T05, T-03-T09 (S27), T-03-T10 (S28) |

**Recommended sequence.**
1. **S1 Contract Monday:** adopt moves 1–4 for S1–S2 (§7.3.1–7.3.2 list them). They cost nothing in scope.
2. **M3 (Fri Nov 20):** measure kit-task throughput, red-lane throughput and the cost of a test row. If throughput is below 85% of plan, or test rows cost their full size, invoke **tier 1 now** (chapter 01 already allows tier 1 at M3) and re-run this simulation for S3–S15.
3. **M5 (Fri Jan 22):** apply chapter 01's thresholds to measured S1–S5 throughput. PH1's overflow carries into S7–S10, where the tier-1 cuts (mostly S9–S14 scope) make room; M5 itself is protected by the S6 steps in §7.6.1. On the "as sized" reading the PH1 residual (N 30, AY 37) exceeds tier 1, so expect tier 2 to be pulled forward and tier 3 to be prepared.
4. **M8 (May 28):** the tax GO needs S7–S14 throughput ≥95%. On the "as sized" reading this fails unless PH2 lands nearly on plan; the NO-GO is then the planned lever, not a surprise.
5. **M12 (Aug 20):** if ≥2 partners convert, the hires absorb AY's PH4–PH6 residual; if not, pre-schedule spill items 1–3 at M15.

### 7.5.5 Conflicts found

**CSV sprints against chapter 01 epic windows.** Seven epics have tasks outside their window. All are small and deliberate (ADR drafting a phase ahead, a design board a phase ahead, a wire-up after a freeze). No milestone is affected. Recommendation: note them in chapter 01 §1.4.3 rather than move the windows.

| Epic | Chapter 01 window | CSV sprints | Tasks outside the window (sprint, size) | Size outside | Effect |
|---|---|---|---|---:|---|
| **A-03** | S20–S23 | S18–S23 | A-03-T23 (S18, 0.5), A-03-T24 (S18, 0.5) | 1 | Pre-window ADR drafting (P-57 by AY, P-63 by N) charged to A-03 by F-02; adds 0.5 to each founder in S18, where AY is already at 202% |
| **A-05** | S23–S31 | S21–S31 | A-05-T03 (S21, 0.5) | 0.5 | Pre-window ADR P-58 drafting by N, charged to A-05; N is at 97% in S21 |
| **I-01** | S10–S35 | S10–S39 | I-01-T27 (S39, 0.25) | 0.25 | Post-freeze wire-up deliberately merged in the first train after Apr 20, 2028; 0.25 outside the window |
| **T-02** | S16–S21 | S14–S21 | T-02-T36 (S14, 0.5) | 0.5 | Pre-window ADR P-68 drafting before the M8 tax go/no-go; harmless on NO-GO (the ADR is still needed for T-04) |
| **T-05** | S35–S44 | S33–S44 | T-05-T02 (S33, 0.5) | 0.5 | Pre-window ADR P-69 drafting inside the 2028 season (S33), so T-05 opens unblocked in S35 |
| **T-06** | S49–S55 | S44–S55 | T-06-T68 (S44, 0.5) | 0.5 | CLI-03 design board a phase ahead (chapter 01 §1.4.3 says design by S44); the task says AY non-code share but carries a planned size |
| **T-07** | S44–S47 | S43–S47 | T-07-T02 (S43, 0.5) | 0.5 | Pre-window ADR amendment (citation kind 11) drafted by N in S43 |

**Merge-train dates after the task's sprint.** Twelve tasks (thirteen mentions) name a train date after their own sprint: flag retirements, rollbacks, "merges first in the next batch". Five fall outside the chapter 01 window of their epic:

| Task | Sprint | Train named | Epic window end | Note |
|---|---|---|---|---|
| T-01-T48 | S21 (ends Aug 20, 2027) | Thu Aug 26, 2027 | S21 | Last live-path merge before the Sep 1 window; still before the freeze, but one week past the window |
| A-03-T20 | S23 (ends Sep 17, 2027) | Thu Oct 21, 2027 | S23 | Flag retirement after the Oct 20 window |
| Q-05-T30 | S54 (ends Nov 24, 2028) | Thu Dec 14, 2028 bundle | S54 | Entitlement switch in the December bundle |
| T-08-T43 | S55 (ends Dec 8, 2028) | Thu Dec 14, 2028 bundle | S55 | Flag renewal in the December bundle |
| I-04-T27 | S73 (ends Aug 17, 2029) | Tue Aug 28, 2029 | S73 | Flag retirement in the GA sprint |

The others (A-04-T40, C-01-T43, C-01-T57, G-03-T25, I-04-T23, N-04-T01, Q-05-T31) stay inside their epic windows.

**Other CSV-against-chapter-01 conflicts.**

| # | Conflict | CSV | Chapter 01 | Proposed resolution |
|---|---|---|---|---|
| K-1 | Lane split | N 957, AY 1,402 planned | N ≈ 1,190, AY ≈ 900 (§1.8.2) | Moves 1–4 of §7.5.4 at each Contract Monday |
| K-2 | Total size | 2,388 build-epic tasks; 2,359 planned demand | ≈2,120 tasks; ≈2,090 planned (§1.4) | Measure at M3; cut tiers by the §7.5.4 sequence |
| K-3 | Unit of a test row | 423 separate ADR-078 TEST rows | 14 tasks/FW already nets ~25% for independent tests and review (§1.8.1) | Settle at M3 by measurement (§7.7) |
| K-4 | PH1 demand | 235 planned tasks in S1–S6 (156%) | 157 (104%) | Moves 1–4, then tier 1 at M3 or M5 |
| K-5 | C6 v1 provider | Q-02-T45 stubs C6 v1 in S11, "conditional on the C6 v1 owner change being recorded" | Register: provider P-09/P-10 (N), v1 frozen S12 (§1.3.2) | Record the owner change in the decision log before S11 (Q-02 provides C6 v1 in S11–S12; P-09/P-10 provide v2 in S30). Without it C6 v1 cannot freeze in S12, because chapter 01's named providers open their windows in S29 (P-10) and S31 (P-09) |
| K-6 | Pre-window tasks | 7 epics (table above) | Windows in §1.4.1 | Note in §1.4.3; no date change |
| K-7 | Non-code task carrying planned size | T-06-T68 (CLI-03 design board, "AY's non-code share") has size 0.5 in S44 | Design tasks for CLI-03 and WB-05 are non-code (§1.8.1) | Count it in AY's non-code time |
| K-8 | N's vendor share | F-09-T11 and F-09-T17 (N, 1.25 in S0); N's F-09 rows total 7.8 tasks | F-09 is funded from AY's non-code time | Accept as N overhead outside planned capacity, or charge to N's reserve outside S0–S1 |
| K-9 | Contracts at the PH1 exit | Register freezes followed by the CSVs (C13 in S10; C3 services and C6 v1 in S12) | §1.2.1 PH1 exit says "contracts C1–C6, C13, C16 frozen" by M5, while §1.3.2's register freezes C3 services and C6 v1 in S12 and C13 in S10 | Follow the register; amend the PH1 exit wording in chapter 01 |

**Conflicts between chapters (not CSV).**

| Item | Where | Resolution in this chapter |
|---|---|---|
| Sprint 0 length (one week vs two) | Chapter 02 §2.3.2 vs chapter 01 | Two weeks (chapter 01) |
| AWS decision date (Oct 19 vs Decision Day) | Chapter 02 §2.3.3 vs chapter 01 §1.9 DEC-03 | Decision Day; landing zone from Mon Oct 26 |
| Back-fill tranches 1–3 in S0–S2 vs Q-03 from S6 | Chapter 02 S0-10 vs chapter 01 and Q-03 | Q-03 from S6 |
| Production weekday after M9 (Thursday vs Tuesday) | Chapter 01 §1.3.3 vs chapter 06 §2.4 | Thursday from M9; chapter 06 to be amended or chapter 01 to adopt Tuesday at S16 Contract Monday |
| Mid-sprint sync day (Thursday vs Wednesday) | Chapter 01 §1.3.2 vs this chapter's brief | Wednesday sync; Thursday windows kept |

**Per-epic size, CSV against chapter 01.**

| Epic | Lead (ch. 01) | Ch. 01 size (tasks) | CSV size (tasks) | Delta | CSV N / AY split | Of which ADR-078 TEST rows |
|---|---|---:|---:|---:|---|---:|
| A-01 | N | 18.2 | 23.5 | +29% | 10.8 / 12.8 | 5.0 |
| A-02 | N | 26.6 | 31.0 | +17% | 16.0 / 15.0 | 7.0 |
| A-03 | AY | 14.0 | 19.5 | +39% | 7.0 / 12.5 | 4.0 |
| A-04 | AY | 36.4 | 45.5 | +25% | 16.5 / 29.0 | 8.5 |
| A-05 | AY | 51.8 | 52.0 | +0% | 15.0 / 37.0 | 7.5 |
| A-06 | N | 28.0 | 34.5 | +23% | 17.5 / 17.0 | 9.5 |
| A-07 | N | 47.6 | 52.5 | +10% | 29.0 / 23.5 | 10.0 |
| A-08 | AY | 32.2 | 37.0 | +15% | 10.8 / 26.2 | 5.5 |
| A-09 | N | 32.2 | 39.0 | +21% | 19.0 / 20.0 | 6.0 |
| A-10 | AY | 39.2 | 47.0 | +20% | 8.5 / 38.5 | 9.5 |
| A-11 | N | 15.4 | 19.0 | +23% | 8.5 / 10.5 | 3.5 |
| C-01 | AY | 54.6 | 60.0 | +10% | 15.0 / 45.0 | 7.5 |
| C-02 | N | 44.8 | 51.5 | +15% | 22.0 / 29.5 | 9.0 |
| F-01 | N | 12.6 | 14.5 | +15% | 10.0 / 4.5 | 4.5 |
| F-02 | shared | 5.6 | 6.5 | +16% | 3.2 / 3.2 | 0.8 |
| F-03 | N | 29.4 | 35.5 | +21% | 25.8 / 9.8 | 6.2 |
| F-04 | AY | 28.0 | 32.2 | +15% | 9.0 / 23.2 | 11.0 |
| F-05 | AY | 58.8 | 65.0 | +11% | 12.5 / 52.5 | 10.0 |
| F-06 | AY | 19.6 | 22.8 | +16% | 2.8 / 20.0 | 5.0 |
| F-07 | AY | 21.0 | 23.5 | +12% | 2.0 / 21.5 | 4.0 |
| F-08 | AY | 36.4 | 39.5 | +9% | 6.5 / 33.0 | 7.5 |
| G-01 | N | 14.0 | 17.0 | +21% | 12.0 / 5.0 | 3.5 |
| G-02 | N | 22.4 | 27.2 | +22% | 20.0 / 7.2 | 5.0 |
| G-03 | N | 26.6 | 27.2 | +2% | 20.8 / 6.5 | 5.0 |
| G-04 | N | 15.4 | 19.2 | +25% | 11.8 / 7.5 | 3.5 |
| I-01 | AY | 19.6 | 23.8 | +21% | 4.2 / 19.5 | 4.2 |
| I-02 | N | 14.0 | 17.2 | +23% | 7.0 / 10.2 | 3.0 |
| I-03 | AY | 30.8 | 32.8 | +6% | 8.0 / 24.8 | 5.5 |
| I-04 | AY | 21.0 | 21.8 | +4% | 7.2 / 14.5 | 3.8 |
| K-01 | AY | 19.6 | 23.2 | +19% | 4.5 / 18.8 | 3.8 |
| K-02 | AY | 15.4 | 19.0 | +23% | 4.0 / 15.0 | 3.5 |
| K-03 | N | 61.6 | 63.5 | +3% | 31.0 / 32.5 | 10.5 |
| K-04 | N | 50.4 | 54.5 | +8% | 23.0 / 31.5 | 10.5 |
| K-05 | AY | 30.8 | 28.8 | -7% | 9.5 / 19.2 | 4.0 |
| N-01 | N | 23.8 | 28.0 | +18% | 16.8 / 11.2 | 4.2 |
| N-02 | N | 50.4 | 49.5 | -2% | 26.5 / 23.0 | 10.2 |
| N-03 | AY | 32.2 | 40.0 | +24% | 19.8 / 20.2 | 6.5 |
| N-04 | AY | 22.4 | 26.8 | +19% | 6.8 / 20.0 | 4.0 |
| P-01 | AY | 11.2 | 13.8 | +23% | 4.2 / 9.5 | 3.0 |
| P-02 | N | 9.8 | 11.5 | +17% | 6.5 / 5.0 | 2.2 |
| P-03 | N | 23.8 | 29.5 | +24% | 18.0 / 11.5 | 6.5 |
| P-04 | N | 50.4 | 59.2 | +18% | 33.5 / 25.8 | 14.8 |
| P-05 | AY | 11.2 | 13.8 | +23% | 2.5 / 11.2 | 3.0 |
| P-06 | N | 21.0 | 26.0 | +24% | 13.2 / 12.8 | 4.2 |
| P-07 | N | 49.0 | 56.2 | +15% | 27.5 / 28.8 | 11.2 |
| P-08 | N | 18.2 | 22.0 | +21% | 10.2 / 11.8 | 4.8 |
| P-09 | N | 15.4 | 18.0 | +17% | 7.5 / 10.5 | 4.0 |
| P-10 | N | 54.6 | 55.8 | +2% | 37.2 / 18.5 | 10.5 |
| P-11 | N | 28.0 | 33.5 | +20% | 23.5 / 10.0 | 7.5 |
| Q-01 | N | 50.4 | 53.5 | +6% | 42.8 / 10.8 | 8.8 |
| Q-02 | N | 40.6 | 48.2 | +19% | 38.0 / 10.2 | 9.2 |
| Q-05 | AY | 22.4 | 29.0 | +29% | 12.8 / 16.2 | 3.5 |
| R-01 | AY | 22.4 | 26.8 | +19% | 9.5 / 17.2 | 4.2 |
| R-02 | AY | 16.8 | 20.8 | +24% | 3.5 / 17.2 | 3.5 |
| R-03 | AY | 14.0 | 17.0 | +21% | 7.0 / 10.0 | 1.8 |
| T-01 | N | 54.6 | 50.5 | -8% | 25.8 / 24.8 | 10.0 |
| T-02 | AY | 28.0 | 32.2 | +15% | 6.5 / 25.8 | 5.2 |
| T-03 | AY | 14.0 | 17.0 | +21% | 3.5 / 13.5 | 3.0 |
| T-04 | AY | 49.0 | 58.0 | +18% | 19.5 / 38.5 | 9.5 |
| T-05 | AY | 71.4 | 72.2 | +1% | 19.2 / 53.0 | 12.0 |
| T-06 | AY | 57.4 | 54.2 | -5% | 12.2 / 42.0 | 8.2 |
| T-07 | AY | 22.4 | 26.8 | +19% | 7.2 / 19.5 | 4.2 |
| T-08 | AY | 33.6 | 38.5 | +15% | 9.0 / 29.5 | 5.0 |
| T-09 | AY | 19.6 | 23.5 | +20% | 4.0 / 19.5 | 3.0 |
| W-01 | N | 15.4 | 17.8 | +15% | 9.8 / 8.0 | 2.5 |
| W-02 | N | 25.2 | 29.0 | +15% | 10.0 / 19.0 | 4.5 |
| W-03 | N | 25.2 | 31.0 | +23% | 14.5 / 16.5 | 4.0 |
| W-04 | AY | 19.6 | 24.2 | +24% | 5.8 / 18.5 | 4.5 |
| X-01 | AY | 56.0 | 65.5 | +17% | 23.5 / 42.0 | 10.5 |
| X-02 | N | 14.0 | 17.0 | +21% | 8.5 / 8.5 | 2.5 |
| X-03 | AY | 21.0 | 25.0 | +19% | 6.0 / 19.0 | 4.0 |

---

## 7.6 Critical path and slack

### 7.6.1 Task level, S0–S12

**Method.** Slack is counted in sprints. Each task's latest sprint is the earliest of its epic's window end, the milestone sprint for tasks whose title or acceptance names a milestone (M1 S0, M2 S1, M3 S2, M4 S3, M5 S6, M6 S9, M7 S12), and the latest sprint of every successor. Slack = latest sprint − CSV sprint. Over S0–S12 (F-09 excluded): 0 sprints: 112 tasks, 1 sprint: 110 tasks, 2 sprints: 83 tasks, 3 sprints: 63 tasks, ≥4 sprints: 292 tasks.

**The chains with zero slack.**

| Chain | Path (sprint) | Ends at | Slack |
|---|---|---|---|
| **Governance → model → portal identity → portal PBC** (chapter 01 CP-B/CP-C) | F-01-T01 → F-01-T03 → F-01-T04 → F-01-T09 (S0) → F-03-T07 → F-03-T08 → F-03-T05 → F-03-T12 (S1) → F-03-T23 → F-03-T24 → F-03-T26 (S2) → F-03-T27 → F-03-T30 (S3) → P-08-T01 (S4) → P-08-T05 (S5) → P-08-T10 (S6) → P-08-T17 (S7) → P-08-T21 (S8) → R-01-T13 → R-01-T14 (S9) → R-01-T21 (S10); branch P-08-T26 (S9) → P-08-T28 (S10) → P-08-T29 (S11) | M5 (portal sign-in), then the J12 and PBC portal paths for M7 and M8 | No gap: one dependency hop in each consecutive sprint from S0 to S11, ending on P-08's window end (S11). A one-sprint slip anywhere lands P-08-T29 outside its window unless two links finish in the same sprint |
| **Production readiness** (CP-A) | F-01-T01 → F-01-T03 → F-01-T04 → F-01-T06 → Q-01-T03 → Q-01-T07 (S0) → Q-01-T14 → T15 → T18 → T20 (S1) → Q-01-T26 → T27 (S2) → Q-01-T35 (S3) → Q-02-T35 (S7) → Q-02-T42 → Q-03-T034 (S9) → Q-03-T041 (S10) → Q-03-T054 (S11) → Q-03-T060 → Q-02-T49 (S12) | M2, M4, M6, M7 | 0 in S0–S3; about 3 sprints between R1 and the pen-test environment (S3 → S7), then 0 to M7 |
| **Review grammar** (CP-B) | F-03 (S0–S3) → P-04-T01 ADRs (S3) → P-04-T03…T08 migrations and C3 stubs (S3) → P-04-T11 stub 3 (S4) → P-04-T14, T15 hashing (S6) → P-04-T16 projector (S8) → P-04-T18, T19 sign-off service (S10) → P-04-T21…T23 (S11) → P-04-T24, P-04-T27 C3 services freeze (S12) | M4 (schemas), M7 (services) | 0 at S3 and S12; 1–2 sprints between |
| **M5 assembly** | F-05 tiers 0–1 (S0–S6) → F-05-T49 lock; P-07-T19…T22 record cores and J02 steps; P-08-T10…T16 portal sign-in and home; F-04-T26, T27 journey specs and WorkOS fake (all S6) | M5 | 0: 22 tasks (20.5) sit in S6, the M5 sprint |

**Zero-slack tasks by sprint (those that feed a milestone).**

| Sprint | Zero-slack tasks feeding a milestone (first milestone fed) | Count | Size |
|---|---|---:|---:|
| S0 | F-01-T01 (M1), F-01-T02 (M1), F-01-T03 (M1), F-02-T01 (M1), F-02-T02 (M1), F-02-T03 (M1), F-02-T04 (M1), F-02-T05 (M1), F-02-T06 (M1), F-02-T13 (M1), F-03-T02 (M1), F-03-T03 (M1), Q-01-T01 (M1), Q-01-T04 (M1), Q-01-T10 (M1) | 15 | 9.75 |
| S1 | F-01-T13 (M2), F-01-T14 (M2), F-01-T15 (M6), F-02-T11 (M2), F-03-T07 (M2), F-03-T09 (M2), F-03-T18 (M2), F-03-T19 (M2), Q-01-T14 (M2), Q-01-T15 (M2), Q-01-T16 (M2), Q-01-T17 (M2), Q-01-T18 (M2), Q-01-T19 (M2), Q-01-T20 (M2), Q-01-T21 (M2), Q-01-T22 (M2) | 17 | 16 |
| S2 | F-02-T12 (M3), F-05-T26 (M3) | 2 | 1 |
| S3 | P-04-T01 (M4), P-04-T03 (M4), P-04-T04 (M4), P-04-T05 (M4), P-04-T06 (M4), P-04-T07 (M4), P-04-T08 (M4), P-04-T09 (M4), P-06-T01 (M4), P-06-T02 (M4), Q-01-T34 (M4), Q-01-T35 (M4), Q-01-T36 (M4), Q-01-T37 (M4), Q-01-T38 (M4), Q-01-T39 (M4), Q-01-T40 (M4), Q-02-T15 (M4), Q-02-T19 (M4) | 19 | 17.25 |
| S4 |  | 0 | 0 |
| S5 |  | 0 | 0 |
| S6 | F-04-T26 (M5), F-04-T27 (M5), F-05-T38 (M5), F-05-T45 (M5), F-05-T46 (M5), F-05-T49 (M5), P-01-T13 (M5), P-01-T16 (M5), P-06-T13 (M5), P-06-T14 (M5), P-06-T16 (M5), P-07-T19 (M5), P-07-T20 (M5), P-07-T21 (M5), P-07-T22 (M5), P-08-T10 (M5), P-08-T11 (M5), P-08-T12 (M5), P-08-T13 (M5), P-08-T14 (M5), P-08-T15 (M5), P-08-T16 (M5) | 22 | 20.5 |
| S7 |  | 0 | 0 |
| S8 |  | 0 | 0 |
| S9 | A-01-T15 (M6), A-01-T16 (M6), P-03-T15 (M6), P-03-T16 (M6), Q-02-T42 (M6), Q-03-T030 (M6), Q-03-T034 (M6) | 7 | 8.75 |
| S10 |  | 0 | 0 |
| S11 |  | 0 | 0 |
| S12 | G-02-T17 (M7), G-02-T18 (M7), G-02-T21 (M7), P-04-T24 (M7), P-04-T27 (M7), Q-02-T48 (M7), Q-02-T49 (M7), Q-03-T056 (M7), Q-03-T058 (M7), Q-03-T060 (M7) | 10 | 9.5 |

**Resource-adjusted.** Slack in sprints assumes the work fits. It does not: S1–S8 are over capacity for at least one founder, so the zero-slack chains run with *negative* effective slack until re-balanced. The schedule simulation puts 4 milestone-feeding zero-slack tasks beyond capacity in their sprint: P-07-T19 (S6 → M5), P-07-T20 (S6 → M5), P-07-T21 (S6 → M5), P-07-T22 (S6 → M5). They are the J02 half of M5. In S6 AY's zero-slack rows alone come to 15.75 tasks against 11.1 of planned capacity (N's come to 4.75 against 18.4), so the S6 Contract Monday should protect M5 in three steps:
1. Lane-swap AY's amber M5 rows to N: F-04-T27 (WorkOS fake), P-08-T12 (client stage projection), P-08-T13 (portal home read model) and P-08-T14 (scenario slice), 3.0 tasks.
2. Let AY's S6 reserve pay for the three M5 test rows (F-04-T26 journey specs, F-05-T49 Tier A lock, P-01-T16 wire-up and journeys, 3.0 tasks), and start AY's Q-03 back-fill rows (Q-03-T006…T008, T010) in S7; chapter 01 puts the back-fill in S6–S13, so this stays inside its window.
3. Defer every S6 row with slack ≥1 inside its window: N's P-07-T10, P-07-T15, P-07-T16, G-01-T04, Q-02-T29 and P-04-T15; AY's F-05-T47, F-04-T25, F-04-T09, F-05-T32, G-01-T01, G-01-T03, Q-02-T31 and F-05-T62.

After these steps the M5 set is AY 9.75 of 11.1 and N 7.75 of 18.4. N keeps the S6 contract stubs (G-01-T02, P-07-T17, P-06-T15) in its remaining room so that no consumer is blocked.

### 7.6.2 Epic level, S13–S74

Chapter 01's chains (§1.8.5) checked against the CSV epic windows. Slack is from the CSV's last sprint of the gating epic to the milestone.

| Chain | Gating epics (CSV sprints) | Milestone | Slack | Watch |
|---|---|---|---|---|
| **CP-A** production readiness | Q-02 (S0–S13), Q-03 back-fill | M7 Apr 16, 2027 (S12); M9 Jun 1 | ≈6 weeks to M9 (chapter 01) | Type I report timing; fallback May 14 |
| **CP-B** model and trust spine | P-04 (S3–S26) → A-06 (S24–S30) → A-07 (S27–S36) | M16 Mar 21, 2028 (S37) | 0 (A-07 ends Mar 17) | A-07 schema by Dec 24, 2027 (freeze contract) |
| **CP-C** audit MVP to client-facing | A-01 (S7–S13), A-02 (S8–S17), R-01 (S7–S18), N-01 (S13–S18) | M8 May 28 (S15); M10 Jul 13 (S19) | 0 to M10 (R-01 and N-01 end Jul 9) | Live ledger read (A-02) is a tier-1 cut candidate |
| **CP-D** tax extension pilot | T-01, T-02, N-02 (S16–S21; T-02 pre-window ADR in S14) | M11 Aug 17 (S21), M13 Aug 31 (S22) | 0 to M11; 1 sprint to M13 | Tax GO at M8; delta #2 Aug 2–11 |
| **CP-E** 2028 season readiness | A-06 (S30), T-03 (S29), N-04 (S29) | M15 Dec 10, 2027 (S29); schemas by Dec 24 (S30) | 0 | Pen test #2 (Nov) |
| **CP-F** 2028 extension-season tax | P-10 (S29–S38), P-11 (S17–S34) → T-04 (S32–S39) → T-05 (S33–S44) | M17 May 2, 2028 (S40); M18 Aug 1 (S46) | 0 to M17; 2 sprints to M18 | T-04 shadow from Mar 20 inside the freeze |
| **CP-G** CAS | C-01 (S44–S51) → C-02 (S49–S55) | M20 Oct 31, 2028 (S53); M21 Dec 8 (S55) | ≈1 sprint to M20; 0 to M21 | Intuit production keys; AY at 218–262% in S49–S51 |
| **CP-H** group audit | A-03 (S18–S23), A-04 (S22–S28) → A-09 (S45–S50) | M19 Sep 29, 2028 (S50) | 0 | Component-auditor room pen test |
| **CP-I** engine-based journeys | F-08 (S50–S55) → K-03 (S52–S60) → K-04 (S59–S65) → X-01 (S62–S69), X-03 (S68–S73), A-11 (S65–S68) | M22 Apr 27, 2029 (S65); M23 Aug 17 (S73) | 0 to M22 and M23; 1 sprint to GA | Spill list protects GA |

The epic-level slack matches chapter 01's within a sprint. The binding constraint after S12 is AY's lane (§7.5.2), which crosses CP-C (R-01), CP-D (T-02), CP-E (T-03, N-04), CP-F (T-04, T-05), CP-G (C-01) and CP-I (X-01). Every chain with zero calendar slack and an AY-led gating epic is effectively negative until §7.5.4 is applied.

---

## 7.7 Re-planning triggers and calibration gates

Chapter 01 §1.8.7's gates, dated on this calendar, with the measurements this chapter adds.

| Gate | Date (sprint) | Measured | Thresholds and actions (chapter 01) | Added by this chapter |
|---|---|---|---|---|
| **M3** | Fri Nov 20, 2026 (S2) | Frontend tasks per day on the Accrued kits (S1–S2); red-lane throughput | <85% of plan → cut tier 1 now | **Test-row cost:** session time of ADR-078 TEST rows against feature rows. If a test row costs ≥0.75 of its size, adopt the "as sized" reading: invoke tier 1 now and prepare tier 3. If ≤0.25, adopt the "covered" reading and re-run §7.5.4. Also: did moves 1–4 in S1–S2 bring each founder ≤100%? |
| **M5** | Fri Jan 22, 2027 (S6) | Planned-epic throughput S1–S5 per founder against the ledger | ≥90% hold; 80–90% tiers 1–2; <80% tier 3 (shadow Jun 15, R3 Jul 27) | Carry-over count of milestone-feeding zero-slack tasks (§7.6.1); AY's PH1 residual against tier 1 |
| **M8** | Fri May 28, 2027 (S15) | Throughput S7–S14; red-review latency | ≥95% and partner and counsel ready → tax GO; otherwise NO-GO | On the "as sized" reading, plan the NO-GO lever explicitly (≈110 tasks in S16–S21) |
| **M14** | Fri Oct 15, 2027 (S25) | Throughput S16–S25 including support; conversion result | Re-plan PH4–PH5; add the hires' capacity if M12 passed | Re-run the load chart with the hires; AY's S27–S29 peak (A-07, A-05, T-03, N-04) |
| **M15** | Fri Dec 10, 2027 (S29) | Escaped-defect log; auto-merge earned? | If not earned, drop the +15% gain from S39 and pre-schedule spill items 1–3 | Without the +15% gain, PH5–PH7 capacity falls about 4%; re-check CP-G and CP-I |
| **Every phase exit** | S0, S6, S15, S30, S38, S51, S65, S74 | Per-founder ledger; red-review queue age | Queue >2 working days for 2 sprints → move amber work to AY, or bring the hire forward | With the CSV lanes the opposite usually applies: AY's queue is the long one. Measure both founders' queues; move eligible amber work to N |

**Standing triggers (any Contract Monday).**

| Trigger | Action |
|---|---|
| A founder above 110% of planned capacity for two consecutive sprints after moves 1–4 | Invoke the next unused lever in §7.5.4's order and record it in the decision log |
| Any milestone-feeding zero-slack task marked ▲ at Contract Monday | It moves to the top of that founder's list; non-critical rows with slack leave the sprint |
| Reserve overrun in a sprint (Q-03 above the reserve pool) | The overrun is taken from planned capacity in that sprint, never deferred as "debt" |
| A contract stub later than 3 working days after its request | Raised at the Wednesday sync; consumer work stays in fixture mode, provider work re-ordered |
| Red main for more than one batch window | Merging stops; the next batch fixes it before any feature PR |
| A CSV task found outside its chapter 01 window, or a new task added | Added to §7.5.5's list at the next Contract Monday; chapter 01 dates do not move without both founders |
| Type I report late, pen-test highs open after Apr 9, or Bedrock evals failing at S11 | Chapter 01's M7 fallback (gate May 14; shadow Jun 15; R3 Jul 27) |

**How this chapter is kept current.** `backlog.csv` is regenerated from the epic CSVs whenever a CSV changes; the load chart, the batch simulation and the re-balancing are re-run on the Friday of week 2 from the velocity log, and the result becomes the next Contract Monday's input. The plan's dates change only through chapter 01.
