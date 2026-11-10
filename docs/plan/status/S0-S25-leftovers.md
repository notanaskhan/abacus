# S0-S25: the skipped non-code rows, decided (DEC-4200)

Recorded 2026-11-10 on main 3e4935e86. Scope: the 785 rows of `docs/plan/backlog.csv` with type
OPS, VENDOR, DOC or TEST and sprint 0 to 25. Evidence for each row was found in this order:
a commit body on main naming the row, the `work/tasks/TASK-*.md` file whose `plan_key` names it,
a test or doc file named after it, then `status-verified.csv` and the deferral files. A row counts
as done only with evidence; where its acceptance needs a staging, production or live-firm run
that the repo cannot show, it is partial and the open clause is written beside its row in
`status-verified.csv`.

| Bucket | Rows | Backlog `status` |
|---|---|---|
| Built, with evidence | 420 (337 done, 83 partial) | done / partial |
| Deferred before (DEC-1389, DEC-1391) | 29 | deferred (unchanged) |
| Deferred by Ayush, 2026-11-10 | 28 | deferred |
| Solo rituals, closed | 95 | cut |
| Pilot-firm rows (the PF-X1 session owns them) | 87 | unchanged |
| Human and ops rows (this file) | 126 (7 partly built) | todo, or partial where partly built |

No gate is treated as met by this record (DEC-1389 rule 4, DEC-1391 rule 4, DEC-2227).

## Human and ops rows, by owner and what unblocks them

### Ayush: vendors and applications

**Unblocked by:** A vendor account, application or contract in the company's name. N-02-T44 also waits on F-09-T08 (DocuSeal), deferred.

| Row | S | What |
|---|---|---|
| F-09-T05 | 0 | Intuit developer account, production-keys app assessment and App Partner Program tier |
| F-09-T10 | 0 | Commercial terms for WorkOS |
| F-09-T11 | 0 | notanaskhan's S0 vendor share |
| Q-01-T04 | 0 | Technical vendor set-up after F-09 contracts |
| F-09-T18 | 1 | Xero app and NetSuite SDN no-fee registrations or enquiries |
| F-09-T28 | 1 | Application follow-ups |
| F-09-T64 | 5 | Intuit production keys (target Jan 29) follow-ups |
| F-09-T65 | 5 | Technical answers for the Intuit app assessment and any DocuSeal security questionnaire |
| F-09-T67 | 5 | Second-wave vendors only on discovery evidence |
| F-09-T81 | 7 | Intuit production keys (Jan 29) close-out or fallback |
| N-02-T44 | 21 | Production enablement |
| Q-03-T160 | 25 | Provider quota increases requested one month before the x100 test |

### Ayush: SOC 2 programme

**Unblocked by:** A compliance tool and an auditor. F-09-T13 (the tool) is deferred, so every row here waits on that decision. Q-02-T42 and Q-02-T49 also carry pen-test clauses, deferred under DEC-1389.

| Row | S | What |
|---|---|---|
| F-09-T24 | 1 | SOC 2 auditor RFP |
| F-09-T25 | 1 | SOC 2 policy set |
| F-09-T35 | 2 | SOC 2 vendor and sub-processor register |
| F-09-T36 | 2 | SOC 2 auditor selected after an independence check, with both founders approving the spend |
| F-09-T44 | 3 | SOC 2 auditor engagement letter signed by Fri Dec 11 (M4) |
| Q-02-T19 | 3 | Controls operating by Fri Dec 11 |
| F-09-T71 | 6 | Auditor relationship during readiness |
| F-09-T87 | 8 | SOC 2 readiness gap fixes for ayushkbhatia-owned policies, the vendor register and HR |
| F-09-T91 | 9 | SOC 2 system description sections |
| Q-02-T42 | 9 | Pen test #1 |
| F-09-T98 | 10 | Type I fieldwork support |
| F-09-T104 | 11 | Type I report receipt (about Apr 2) and the NDA distribution process |
| Q-02-T49 | 12 | M7 gate dossier and vendor-diligence pack |
| Q-03-T070 | 13 | SOC 2 Type II readiness for the May 1 - Jul 31 window |
| Q-03-T074 | 14 | SOC 2 Type II window operation, May |
| F-09-T133 | 16 | Type II observation window |
| Q-03-T110 | 18 | SOC 2 Type II window operation, June |
| Q-03-T115 | 19 | SOC 2 Type II window operation, July, and window close on Sat Jul 31 with the N-owned |
| F-09-T160 | 20 | Type II window close |
| F-09-T172 | 22 | Type II fieldwork logistics (Aug-Sep) |
| F-09-T176 | 23 | Type II report receipt |
| Q-03-T144 | 23 | SOC 2 Type II fieldwork support |
| Q-03-T150 | 24 | SOC 2 Type II exceptions remediated and management responses written |

### Ayush: discovery, LOIs, pricing and the 2028 pipeline

**Unblocked by:** Conversations with real firms and Ayush's commercial choices (DEC-2098: never inferred). F-09-T41 (the e-signature go/no-go) also needs DocuSeal's answers and counsel's view, both deferred.

| Row | S | What |
|---|---|---|
| F-09-T15 | 0 | Partner profile and named target lists per window |
| F-09-T16 | 0 | Non-binding LOI template |
| F-09-T20 | 1 | Discovery interviews wave 1 |
| F-09-T21 | 1 | Wave-1 notes anonymised |
| F-09-T26 | 1 | Pricing hypothesis instrument for proposed DEC-100 |
| F-09-T27 | 1 | LOI outreach wave 1 |
| F-09-T30 | 2 | Discovery interviews wave 2 |
| F-09-T31 | 2 | M3 discovery read |
| F-09-T32 | 2 | M3 LOIs |
| F-09-T33 | 2 | Google Workspace check across LOI and target firms and the Google OAuth and CASA go/no-go |
| F-09-T41 | 3 | E-signature go/no-go on Fri Dec 4 |
| F-09-T45 | 3 | Proposed DEC-100 decided at M4 |
| F-09-T51 | 3 | December discovery interviews with LOI firms on ledger, tax-engine and e-signature |
| F-09-T52 | 3 | Founding-partner agreement term sheet |
| F-09-T55 | 4 | LOI wave 2 |
| F-09-T62 | 5 | PW1-PW2 thresholds W4-W8 recorded in thresholds.md before Pilot 0 |
| F-09-T75 | 6 | Discovery synthesis docs/product/discovery/summary-2026.md |
| F-09-T134 | 16 | 2028 pipeline target list |
| F-09-T173 | 22 | 2028 pipeline outreach wave 1 to new firms, demonstrated on the staging demo tenant |
| F-09-T177 | 23 | 2028 pipeline demos and discovery for new firms on synthetic sandboxes |
| F-09-T183 | 24 | 2028 pipeline proposals and LOIs for new firms at the DEC-100 price |
| F-09-T187 | 25 | M14 formal wedge-decision inputs |
| F-09-T189 | 25 | 2028 pipeline contracts for committed new firms |

### Ayush: insurance

**Unblocked by:** A broker and a carrier.

| Row | S | What |
|---|---|---|
| F-09-T39 | 2 | Insurance broker engaged for cyber and tech E&O |
| F-09-T57 | 4 | Cyber and tech E&O applications submitted through the broker with SOC 2 programme evidence |
| F-09-T80 | 7 | Insurance quotes compared and a carrier selected for binding by Mar 31 |
| F-09-T96 | 10 | Cyber and tech E&O bound; certificate filed for the vendor-diligence pack |
| F-09-T140 | 17 | Insurance coverage check for client-facing use and tax data, with endorsements if needed |

### Ayush: spend and diligence packs

**Unblocked by:** Spend facts from Ayush (DEC-2098); committed Bedrock eval runs and the SOC 2 report for the packs. F-09-T102 and F-09-T181 list the pen test as not yet tested (DEC-1389).

| Row | S | What |
|---|---|---|
| F-09-T48 | 3 | Technology Resource Pack v1 draft |
| F-09-T59 | 4 | Year-end spend review against the DEC-03 envelope (RK-05) and Q1 commitments |
| F-09-T102 | 11 | Technology Resource Pack v2 for the M7 vendor-diligence pack |
| F-09-T129 | 15 | Mid-year spend and runway review (RK-05) |
| F-09-T181 | 24 | Technology Resource Pack v3 for firms' 2027 SQMS 1 evaluations |

### Ayush: hiring (conditional on M12, proposed DEC-101)

**Unblocked by:** The M12 gate and a decision to hire.

| Row | S | What |
|---|---|---|
| F-09-T149 | 18 | Hiring prep for proposed DEC-101 |
| F-09-T161 | 20 | Hiring |
| F-09-T164 | 21 | M12 conversion and hiring gate on Fri Aug 20 |
| F-09-T167 | 21 | If M12 passes, roles opened and first-round interviews |
| F-09-T169 | 22 | Hiring loops: technical exercises and interviews (conditional on M12) |
| F-09-T170 | 22 | notanaskhan's backend interview loop (conditional on M12) |
| F-09-T175 | 23 | Offers, references, background checks |
| F-09-T180 | 24 | Hire onboarding prep for Mon Oct 4 |
| F-09-T188 | 25 | Hires start Mon Oct 4: onboarding and the 6-week ramp plan (conditional) |

### Ayush: advisor and rules content

**Unblocked by:** A CPA advisor engaged (F-09-T34); K-02-T20's TY2026 rules content loads through the import path once reviewed. K-01-T26 waits on K-02-T20.

| Row | S | What |
|---|---|---|
| F-09-T34 | 2 | CPA advisor with audit and tax experience engaged |
| K-02-T20 | 19 | TY2026 production rules content and runbook |

### Ops runs on AWS: landing zone, staging and the canary

**Unblocked by:** AWS credentials and the staging and production accounts. Q-01-T41 also needs the Better Stack account (F-09-T10).

| Row | S | What |
|---|---|---|
| Q-01-T01 | 0 | AWS landing zone |
| Q-01-T20 | 1 | R0 bring-up on staging |
| Q-01-T35 | 3 | Production canary tenant through an ops request |
| Q-01-T41 | 3 | Status page and on-call |
| Q-01-T55 | 4 | Synthetic tenants for consumers through TenantProvisioningWorkflow |
| F-04-T24 | 5 | Staging demo tenant |
| P-08-T16 | 6 | M5 journey steps on staging |
| F-04-T35 | 9 | Canary profile: self-provisioning journeys with the real clock and no loader |
| G-02-T27 | 14 | Rollout, security review and docs |
| A-02-T33 | 15 | Live-ledger production cutover |
| Q-04-T019 | 15 | Rollback rehearsal on the production canary |
| A-02-T37 | 17 | Rollout |

### Ops runs: drills, game days and rehearsals

**Unblocked by:** Staging or the production drill subnet, one operator. The second-person part of these drills is closed (Q-01-T54, Q-03-T133); the drills stay.

| Row | S | What |
|---|---|---|
| Q-01-T39 | 3 | First production restore drill and kill-switch game day |
| Q-03-T053 | 11 | 2027 Q1 restore drill by Fri Mar 26 |
| Q-03-T057 | 12 | 2027 Q1 kill-switch game day on staging |
| Q-03-T058 | 12 | Regional failover tabletop before R2 |
| Q-04-T016 | 14 | Onboarding rehearsal on staging, part N |
| Q-03-T102 | 17 | 2027 Q2 restore drill by Fri Jun 25 |
| Q-03-T103 | 17 | 2027 Q2 kill-switch game day, adding the per-firm portal sign-in disable before |
| Q-03-T116 | 19 | Regional failover game day on staging |
| Q-03-T124 | 20 | 2027 Q3 restore drill before the Sep 1 window |
| Q-03-T125 | 20 | 2027 Q3 kill-switch game day before the Sep 1 window |
| Q-04-T057 | 21 | RB-16, RB-18 and RB-19 rehearsed on staging with both founders |
| T-01-T48 | 21 | M13 readiness for Tue Aug 31 |

### Ops runs: load tests on the perf stack

**Unblocked by:** The perf stack (Q-03-T036) up in the staging account.

| Row | S | What |
|---|---|---|
| Q-03-T036 | 9 | Perf stack |
| Q-03-T052 | 11 | x25 load test before M7 on the perf stack |
| Q-03-T056 | 12 | x25 findings fixed as a reliability-only batch |
| Q-03-T100 | 17 | x25 portal-heavy load test before M10 with the upload burst and portal sign-in wave |
| Q-03-T101 | 17 | Portal front-end performance under the x25 run |
| Q-03-T106 | 18 | x25 portal findings fixed before M10 |
| Q-03-T131 | 21 | x25 tax-surge load test before M13 |
| Q-03-T136 | 22 | Tax-surge findings fixed before the Thu Aug 26 last live-path merge |

### Ops runs: Bedrock and production-canary checks

**Unblocked by:** An approved Bedrock provider-terms entry (needs counsel, deferred) and AWS eval credentials; three green production-canary runs.

| Row | S | What |
|---|---|---|
| Q-03-T089 | 16 | AI assurance upkeep |
| N-01-T26 | 18 | Matcher v3 Bedrock rerun at the protected thresholds, evals/baselines.yaml entry |
| Q-03-T137 | 22 | AI assurance upkeep before the Sep 1 window |
| Q-03-T139 | 22 | Pre-window hardening before Sep 1, 2027 |
| Q-03-T140 | 22 | Pre-window front-end hardening before Sep 1, 2027 |

### Builder: buildable now, not built

**Unblocked by:** Nothing outside the repo; a session can build these. Q-03-T060 and Q-03-T138 carry a pen-test evidence line, recorded as deferred (DEC-1389). Q-03-T147 follows Q-03-T072.

| Row | S | What |
|---|---|---|
| Q-03-T060 | 12 | M7 quality evidence for Q-02-T49's dossier |
| Q-03-T072 | 14 | Mutation survivors part 2 for ai_gateway and audit_trail |
| Q-04-T035 | 17 | Firm exit runbook docs/runbooks/firm-exit.md |
| N-01-T30 | 18 | Docs |
| Q-04-T348 | 18 | Thu Jul 8 train |
| R-01-T36 | 18 | Docs and rollout |
| Q-04-T349 | 19 | Thu Jul 22 train |
| Q-03-T138 | 22 | M11/M13 quality evidence |
| Q-03-T147 | 23 | Quarterly mutation sweep |
| Q-03-T148 | 23 | Supply-chain hygiene 2027 Q3 |

## Deferred by Ayush, 2026-11-10

Ayush deferred the vendor applications F-09-T06 (CCH partner programme), F-09-T07 (Microsoft
partner programme and publisher verification), F-09-T08 (DocuSeal account) and F-09-T13 (SOC 2
compliance tool), and the counsel asks. Each waits for a decision that books it. A row that only
follows one of them is deferred with it. Nothing here is done; F-09-T08's sandbox account stays
as it is.

| Row | S | What |
|---|---|---|
| F-09-T06 | 0 | Wolters Kluwer CCH partner programme application |
| F-09-T07 | 0 | Microsoft AI Cloud Partner Program enrolment and publisher verification of the |
| F-09-T08 | 0 | DocuSeal account |
| F-09-T13 | 0 | SOC 2 compliance tool chosen and contracted |
| Q-02-T03 | 0 | Draft the Bedrock provider-terms entry for counsel |
| F-09-T22 | 1 | Counsel early answers due Nov 13 |
| F-09-T38 | 2 | Counsel answers due Nov 27 |
| F-09-T47 | 3 | Counsel review of the draft Bedrock provider-terms entry as the second approver |
| F-09-T58 | 4 | Counsel M7 brief |
| F-09-T66 | 5 | Founding-partner agreement first draft with counsel from the term sheet |
| F-09-T78 | 7 | Counsel M7 drafts received by Fri Jan 29 and reviewed |
| F-09-T86 | 8 | Founding-partner agreement round 2 with counsel's redlines |
| F-09-T92 | 9 | Counsel M8 tax brief |
| F-09-T99 | 10 | Counsel M7 finals |
| F-09-T107 | 12 | Counsel's second approval of the Bedrock provider-terms entry, current for real data |
| F-09-T111 | 12 | Section 7216 consent text draft reviewed with notanaskhan |
| F-09-T115 | 13 | Counsel-approved content pack handed to owning epics as admin-import files, never |
| F-09-T119 | 14 | Counsel-approved section 7216 consent text by Fri May 14 |
| F-09-T139 | 17 | Season-2 agreement counsel review |
| F-09-T141 | 17 | Counsel M13 Pub 1345 brief |
| F-09-T142 | 17 | PWT consent-collection support |
| F-09-T156 | 20 | Season-2 negotiation round 2 with counsel's redlines |
| F-09-T159 | 20 | Counsel M13 Pub 1345 answers |
| P-11-T18 | 25 | Counsel review for OCR |

**Follows a deferred row:**

| Row | S | What |
|---|---|---|
| Q-02-T10 | 1 | Compliance tool connected |
| F-09-T53 | 3 | Microsoft publisher verification close-out |
| F-09-T63 | 5 | DocuSeal KBA enablement from Jan 4 |
| F-09-T97 | 10 | DocuSeal KBA accepted for the 8879 family |

## Solo rituals, closed

Closed as DEC-2259 closed S27's rituals, under `docs/plan/AMENDMENT-solo.md` and chapter 08. Each row is `cut` in the backlog. The work underneath each one keeps its own row.

| Kind | Rows | Why it closes |
|---|---|---|
| Programme cadence (Contract Monday note, tracker and spend refresh) | F-09-T19, F-09-T29, F-09-T40, F-09-T54, F-09-T60, F-09-T68, F-09-T76, F-09-T83, F-09-T88, F-09-T94, F-09-T100, F-09-T106, F-09-T112, F-09-T118, F-09-T124, F-09-T130, F-09-T136, F-09-T143, F-09-T150, F-09-T155, F-09-T162, F-09-T168, F-09-T174, F-09-T179, F-09-T185 | Contract Monday is a two-founder meeting, removed by chapter 08. Each vendor or partner row keeps its own status here; the spend refresh waits on Ayush's figures (F-09-T59, F-09-T129). F-09-T124's note tool (#765) stays on main. |
| notanaskhan's independent checks and verifications | F-09-T12, F-09-T17, F-09-T23, F-09-T46, F-09-T49, F-09-T79, F-09-T103, F-09-T108, F-09-T165, F-09-T182 | A second person checks the first one's work. One builder has no second person (AMENDMENT-solo §1, §3). The work being checked keeps its own row. |
| Decision Day | F-02-T05 | Removed by chapter 08; decisions are made in the session and logged (AMENDMENT-solo §7). |
| Support reserves, N and AY lanes | Q-04-T017, Q-04-T030, Q-04-T036, Q-04-T037, Q-04-T041, Q-04-T042, Q-04-T046, Q-04-T047, Q-04-T051, Q-04-T052, Q-04-T058, Q-04-T059, Q-04-T060, Q-04-T067, Q-04-T068, Q-04-T069, Q-04-T073, Q-04-T074, Q-04-T075, Q-04-T076, Q-04-T080, Q-04-T081, Q-04-T082, Q-04-T083 | As DEC-2259 closed Q-04-T098 and T099: no on-call rota, no live firms and no SEV1/2 to run. Live-path defects go through the next batch. The S25 rows that were rehearsed on PF-X1 (Q-04-T089 to T091) keep their partial status. |
| Escaped-defect and in-window defect lanes | Q-03-T063, Q-03-T071, Q-03-T080, Q-03-T098, Q-03-T105, Q-03-T118, Q-03-T120, Q-03-T135, Q-03-T145, Q-03-T146, Q-03-T149 | No live firm and no live window. A defect found later is fixed in the next batch with a recurrence test, as every task already does. |
| Integration and conflict lanes | Q-03-T020, Q-03-T076, Q-03-T078, Q-03-T079, Q-03-T087, Q-03-T117, Q-03-T119, Q-03-T126, Q-03-T127, Q-03-T142 | Each batch PR resolves its own conflicts. register_ids (Q-03-T087) catches duplicate register rows. |
| ADR-078 catch-up lanes not built | Q-03-T077, Q-03-T128, Q-03-T134, Q-03-T141, Q-03-T143 | The ADR-078 split (tests by the other founder) is void (AMENDMENT-solo §3). Tests are written first, from the spec, in each task. |
| Quarterly reserve reviews | Q-03-T062, Q-03-T113 | The reserve was two-founder capacity. The S25 review (Q-03-T162, TASK-3042) took its place. |
| Conditional call-offs | Q-03-T005, Q-03-T075 | They run only if a cut list was applied. None was. |
| ADR-086 earned auto-merge | Q-03-T045, Q-03-T049 | Merge governance is void (AMENDMENT-solo §4). |
| ADR-100 second-person drills | Q-01-T54, Q-03-T133 | An ADR-100 drill needs a second operator. The drills themselves stay open as ops rows. |
| Back-fill defect lane | Q-03-T069 | Taken over by Q-03-T065, the back-fill close-out (#701). |

## Pilot-firm rows (not touched here)

These 87 rows need a pilot firm. They run on the synthetic firm PF-X1 (Brightwater Hale,
DEC-1530, widened by Ayush on 2026-11-10). A separate session runs them and owns their status:

F-09-T50, F-09-T56, F-09-T61, F-09-T69, F-09-T70, F-09-T72, F-09-T73, F-09-T74, F-09-T77, F-09-T82, F-09-T84, F-09-T85, F-09-T89, F-09-T93, F-09-T95, F-09-T101, F-09-T105, F-09-T109, F-09-T110, F-09-T113, F-09-T114, F-09-T117, F-09-T120, F-09-T121, F-09-T122, F-09-T126, F-09-T127, F-09-T128, Q-03-T084, Q-04-T021, Q-04-T022, F-09-T131, F-09-T132, F-09-T135, Q-04-T024, Q-04-T025, Q-04-T026, Q-04-T027, Q-04-T028, Q-04-T029, R-01-T34, F-09-T138, Q-04-T031, Q-04-T032, Q-04-T033, Q-04-T034, F-09-T144, F-09-T145, F-09-T146, F-09-T148, Q-03-T111, Q-03-T112, Q-04-T038, Q-04-T039, Q-04-T040, F-09-T151, F-09-T152, F-09-T154, Q-04-T043, Q-04-T044, Q-04-T045, T-01-T28, F-09-T158, Q-04-T048, Q-04-T049, Q-04-T050, F-09-T163, F-09-T166, Q-04-T053, Q-04-T054, T-01-T47, F-09-T171, Q-04-T061, Q-04-T062, Q-04-T063, Q-04-T064, Q-04-T065, F-09-T178, Q-04-T070, Q-04-T071, Q-04-T072, F-09-T184, Q-03-T151, Q-04-T077, Q-04-T078, Q-04-T079, F-09-T186.

## Fixed on the way

A-01-T28's row in `backlog.csv` had unquoted commas in its acceptance, so its `status` field read
part of the acceptance. It is quoted now and reads `done`.
