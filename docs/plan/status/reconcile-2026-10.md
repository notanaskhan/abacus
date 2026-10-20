# Reconcile the repo with the plan, 2026-10

Repo main at caeb5df, 2026-10-20. Read-only run: no code, test, migration or spec changed. Method: each acceptance split into clauses, each clause grepped in backend/src, apps/web/src, packages/ui and tests. A clause that cannot be judged from code (timings, green-run counts, rulesets, design-fidelity sign-off) counts as partial.

## Summary

- 32 status.csv rows: **0 done, 31 partial, 1 not started** (plan said 6 done, 26 partial).
- Five "done" rows are downgraded: F-01-T05 (no dated ADR exception), F-01-T06 and F-01-T07 (run counts and timings unmeasured), F-01-T09 (fixture mode absent), Q-02-T07 (no route tests, no make agent-stage). F-01-T10 is obsolete (SU-06), so not started.
- Nine extra rows in status-verified.csv are proposed matches from the repo items with no status row: 7 partial, 2 not started.
- The shipped code is real but narrower than the plan rows: it is the screens and fieldwork first, the kit and contracts later.

## Verified status table

| task_id | plan | verified | evidence |
|---|---|---|---|
| F-01-T05 | done | partial | Green main + 73% recorded (work/tasks/TASK-077); no dated ADR-116 exception in docs/adr; backend/pyproject.toml:136 still fail_under=95 |
| F-01-T06 | done | partial | .github/workflows/ci.yml has merge_group, draft gating, changes job, frontend job; Makefile check-heads/check-generated; 5 green runs and ruleset not judgeable |
| F-01-T07 | done | partial | abacus_tools/ci/paths.py + tests/unit/tools/test_paths.py; ci.yml frontend and evals-fast gates; 6-minute clause unmeasured (frontend job timeout 10) |
| F-01-T09 | done | partial | tools/local/db_guard+worktree_env tests, .claude/hooks (test_hooks generated-file test), Makefile dev-fixtures; VITE_FIXTURES read nowhere in apps/web/src |
| F-01-T10 | done | not-started | Obsolete: SU-06 removed number blocks (test_validate_docs.py "any free number, any deciders"); no .github/ISSUE_TEMPLATE; only duplicate-id check remains (validate_docs.py:133) |
| Q-02-T06 | partial | partial | Matrix rows firm.ai_client_data, engagement.ai_exclude in docs/architecture/permission-matrix.yaml:55-56; no agent_stage.set row, flag agents.client_data_optin, glossary rows or fresh-mfa/human-only yaml |
| Q-02-T07 | done | partial | Migration 0056, identity/routes.py:633-644, engagements/routes.py:903, ai_gateway/boundary.py, abacus_tools/agent_stage.py, tests/unit/ai_gateway/test_client_data_boundary.py; no make agent-stage, no route integration tests |
| Q-02-T08 | partial | partial | Shadow hidden in agents/{screenings,upload_review,inbox_match,guidance_draft}.py; test_board_reads_api.py:138; no re-opt-in on register change, no outbox cache clear |
| F-05-T03 | partial | partial | packages/ui/src/theme.css (plain @theme, Geist); no tokens.ts, contrast.css or tokens.test.ts |
| F-05-T04 | partial | partial | Geist via @fontsource imports in theme.css:9-12, no googleapis; no fonts-doc.css (Arimo, Gelasio); unused newsreader/source-sans-3 deps in packages/ui/package.json |
| F-05-T09 | partial | partial | apps/web/src/gallery/Gallery.tsx at DEV-only /_ds (router.tsx:313-343); no VITE_UI_GALLERY, /components/tokens or /components/screens/:id |
| F-05-T12 | partial | partial | packages/ui/src/status.tsx STATUS/Status/statusWord; no StatusDisc, SubLine, SyncChip, Tick, TallyPill, RETIRED map or generated C2 data |
| F-05-T14 | partial | partial | packages/ui/src/components/button.tsx (7px radius), workspace.tsx Count/StatusPill/AiTag; no Pill, Tick, Tag, Person, Monogram, Pulse, Reveal, useReducedMotion |
| F-05-T15 | partial | partial | components/field.tsx Input/Label; popover.tsx Menu/Tooltip; overlays.tsx Fieldset; shell/Tabs.tsx; no Segmented, SearchField, Picker, Toggle, Radio, Checkbox |
| F-05-T18 | partial | partial | screens/Layout.tsx:96 h-[46px] toolbar, EngagementLayout.tsx:23 42px header, shell/Tabs.tsx; no AppShell/Toolbar components, overflow order or Tier D specimens |
| F-05-T19 | partial | partial | components/surfaces.tsx EmptyState/Skeleton/Alert; no ViewState, OfflineBanner, AgentRunningRow, restricted/flag-off states |
| F-05-T20 | partial | partial | components/overlays.tsx Drawer/Sheet, popover.tsx Popover, dialog.tsx Dialog; no OverlayStack, ?ov= codec, FullSheet, CommandPalette, ConfirmDialog |
| F-05-T21 | partial | partial | components/toast.tsx: 4 s toast, UNDO_MS=10_000, max 3 (slice(-2)); gallery/components.test.tsx undo tests; no hover pause or running pill |
| F-05-T23 | partial | partial | Layout.tsx toolbar replaces rail (Rail unused by screens); screens not under legacy/, shell/ClientBell.tsx still used, wordmark reads Abacus not Accrued |
| F-05-T27 | partial | partial | components/data-table.tsx sort, selection, bulk bar; gallery/components.test.tsx:60-73; no MoneyCell, TickCell, role=grid or arrow/Enter model |
| P-01-T02 | partial | partial | Layout.tsx hard-codes two nav links + bell with unread (useUnreadCount); no nav.ts, DF-39 overflow, Go/Cmd-K chords or flag-off frames |
| P-07-T20 | partial | partial | EngagementLayout.tsx 42px header, Tabs, Archived/Active pill; no G3 banner, record-signed-letter sheet or prospect banner |
| P-07-T27 | partial | partial | screens/Engagements.tsx search + status filter + counts, Engagements.test.tsx; no service-line segmented, seven tiles or G3 banner |
| G-01-T07 | partial | partial | screens/AdminLayout.tsx grouped section list at /admin/*; no /settings subtree, dirty/Save with step-up, leave guard or legacy redirects |
| I-01-T06 | partial | partial | apps/web/src/home/WaitingOnYou.tsx + queue.test.ts; no greeting subbar, Home segmented, tile row or Approvals badge |
| P-04-T21 | partial | partial | fieldwork/notes.py raise_note/respond/clear/NotesOpen, tests/unit/fieldwork/test_notes.py; no withdraw, sealed bodies, notification or workpaper anchors |
| A-03-T04 | partial | partial | sampling/selection.py seeded_v1 (random.random partial Fisher-Yates), test_selection.py:129-137; no v2.3 getrandbits, strata, attribute_size, udl, project, versions |
| A-03-T07 | partial | partial | sampling/population.py build_population/tie_out from gl_entries, test_selection.py:148; no upload source, column map, check-number gaps or population routes |
| A-04-T08 | partial | partial | fieldwork/service.py set_materiality/MaterialityInvalid, models engagement_materiality; no pure engine, benchmarks, rounding policy or versions |
| A-08-T10 | partial | partial | sampling/selection.py rules_for: large, round, near_year_end, manual, rare_account, weekend, keywords with reasons; no holiday, post-close, score or inputs_hash |
| A-08-T12 | partial | partial | fieldwork/{service,selecting,workflows,workpaper}.py, models procedures/selected_items/item_results; no je_tests/je_scores tables, JeScoringWorkflow or 412k run |
| A-08-T27 | partial | partial | screens/Fieldwork.tsx + spec037fieldwork.test.tsx (tie-out, exception, support, sign); states a-h and Open in Excel not mapped one to one |

Proposed matches (CSV only): P-06-T14, R-01-T08, A-06-T04, A-06-T07, A-06-T11, P-04-T18, P-08-T15 partial; F-03-T15, F-03-T16 not started.

## Obsolete or reduced tasks

- **F-01-T10** obsolete: number blocks and reservation forms were built (TASK-082), then removed by SU-06. Leave: duplicate-id check. Mark cut.
- **F-01-T05** reduced to one document: the dated exception ADR (plan ID ADR-116, free in the repo) and the 73% to 95% path by 2026-12-01. Main is green; the coverage job still fails.
- **F-01-T06** reduced: the ruleset clause is cut by solo mode; five green runs is the only open evidence.
- **F-01-T09** reduced to fixture mode (VITE_FIXTURES), which belongs with F-04.
- **F-05-T03, T04** reduced: theme.css and Geist are in. Left: tokens.ts with its equality test, contrast.css, fonts-doc.css; remove unused newsreader and source-sans-3 packages.
- **F-05-T12** reduced: STATUS vocabulary and the TASK-105 request words exist. Left: C2 codegen, RETIRED map, StatusDisc, SubLine, SyncChip, Tick, TallyPill.
- **F-05-T20, T21** reduced: Drawer, Sheet, Popover, Dialog and deferred-undo Toast exist. Left: OverlayStack, ?ov=, FullSheet, palette frame, ConfirmDialog, hover pause, running pill.
- **F-05-T23** reduced: rail gone, toolbar in. Left: wordmark, retire ClientBell, move screens under legacy/ (or drop that clause by DEC).
- **F-05-T27** reduced: DataTable core is in. Left: MoneyCell, TickCell, grid roles, 30px ledger rows.
- **Q-02-T07** reduced to: make agent-stage, platform.agent_stage.set matrix row, route integration tests. **Q-02-T08** left: re-opt-in on register change, outbox cache clear.
- **P-06-T14** reduced: agent send path removed, drafts per contact built. Left: follow_ups_v2 migration, template drafts, notification kinds, P-4 replay. **F-03-T16** untouched.
- **R-01-T08** reduced by TASK-106 (reason, undo, mark done). Left: shared-comment storage and mark-done undo.
- **A-06-T04/T07/T11** reduced by TASK-107 (findings, misstatements, summary). Left: deficiencies, issue linkage, rollover and iron curtain, severity bands.
- **A-08-T12** should be rewritten: shipped as procedures, selected_items, item_results (ADR-132), not je_tests/je_scores. Keep the 412k-line performance clause.
- **A-03-T04, A-04-T08, A-08-T10, A-03-T07** each reduced to a first version (see table); the frozen sampler v2.3 and materiality engine are still whole tasks.
- **P-04-T21** reduced to: withdraw, sealed bodies, notification, anchors outside fieldwork rows, migration of review_notes onto the P-04 engine.

## Features with no plan row

| Repo item | Proposal |
|---|---|
| TASK-086, TASK-087, SPEC-038 unrecorded liabilities search | New A-08 row "Search for unrecorded liabilities: subsequent ledger import, payments, timing bands, workpaper", S45 window, status done on ship. No nearer title exists (only A-07-T23 subsequent events, different). |
| TASK-085 entry assessor | New A-08 row "Entry assessor agent: proposal with code-verified citations", beside A-08-T23 (which is section_drafter modes, not this). Sprint 47. |
| TASK-100, SPEC-040 sample approval, one request per sample, row sign-off, staleness | Absorb into P-04-T18/T19 (wrap, do not duplicate) and K-03-T03; add A-08 row "Sample approval and request per sample", S46. |
| TASK-099 portal white-label and needs-you-first home | Absorb into P-08-T15; F-05-T39 keeps the isolation tests. No new row. |
| TASK-104 follow-ups v2 | P-06-T14 (DEC-74). |
| TASK-105 requests screen v2 | New P-06 row "Requests status counts and quick-view drawer" (S5); data side stays F-03-T15. |
| TASK-106, SPEC-042 client responses | R-01-T08, plus R-01-T06 for the portal words. |
| TASK-107, SPEC-043 findings, misstatements, SUM | A-06-T04, T07, T11; new A-06 row "Raise finding from a fieldwork exception row", S25. |
| TASK-108 walk-through fix | No row (verification). |
| TASK-089, TASK-090, TASK-094 to TASK-097 | Fixes and re-skin; fold into F-05-T23. |

## Contradictions and the default decision

Write each as a DEC in docs/product/decision-log.md. That file does not exist; F-02-T01 (S0) creates it, so write them first into that task's change.

1. **Squared controls vs pills.** Plan: control radius 999px pill (--radius-pill). Repo: 7px squares (button.tsx; TASK-093, founder 2026-10-19); the toast Undo and dots are still round. Decided 2026-10-20: pills (the plan default). Record in docs/product/decision-log.md with F-02-T01; restyle controls back to --radius-pill in F-05-T14. If squares stay: DEC "controls are 7px; chips, counts and avatars stay pills", and amend F-05-T14 and the radius tokens.
2. **Fieldwork sign-off, review notes and workpaper vs P-04 review grammar.** Repo: item_signoffs, review_notes, workpaper_signatures (ADR-131, ADR-132). Plan: one P-04 engine (T18, T21). Default: P-04 is the single engine; fieldwork is its first consumer. Write ADR-134 "Fieldwork review rides the P-04 grammar": no new sign-off tables, migrate at S10 to S11, keep the TASK-100 rules (preparer differs from reviewer, staleness).
3. **Numbering.** Plan names 0056 to 0059 and SPEC-1NN, ADR from 116: taken or moved. Heads: 0064_findings. Next free: TASK-109, SPEC-044, ADR-134 (ADR-133 is product naming, SU-08), migration 0065. ADR-116 to 130 stay reserved for the plan programme; ADR-131/132 are fieldwork. SPEC-039 and TASK-088 are gaps. TASK-104 says it supersedes the shelved SPEC-039. Default: "next free on main" (AMENDMENT-solo item 8).
4. **Brand.** Toolbar wordmark and aria-label read "Abacus"; plan F-05-T23 says Accrued wordmark. Default: plan. Portal shows the firm name only (TASK-099), as the plan wants.
5. **Gallery route.** Repo: DEV-only /_ds. Plan: /components, VITE_UI_GALLERY, absent from production dist. Default: plan; rename in F-05-T09.
6. **Settings route.** Repo: /admin/* with grouped list. Plan G-01-T07: /settings subtree with legacy redirects. Default: plan, redirect at G-01-T07.
7. **Coverage.** Floor 95, actual 73%. Default: dated ADR-116 exception, floor stays 95, back by 2026-12-01.
8. **Process cuts.** F-01-T10 built then removed; mark cut in backlog.csv.

## Blockers for S0 to S2 tasks

- **F-05-T03** (tokens.ts, contrast.css) blocks F-05-T04 to T07, T09, T10, T12, T13.
- **F-05-T09** blocks F-05-T14 and T16. **F-05-T12** blocks F-05-T14.
- **F-05-T14** (missing primitives) blocks F-05-T15, T18, T19, T24, T26. **F-05-T15** (Segmented and inputs) blocks T18 and T20.
- **F-05-T18** (real Toolbar, RecordHeader) blocks F-05-T20, T23 and **P-01-T02**; **F-05-T19** also blocks P-01-T02. **F-05-T20** blocks T21, T22; T21 blocks T22.
- **Q-02-T06** blocks Q-02-T07, which blocks Q-02-T08 and Q-02-T09; T08's re-opt-in gap blocks T09.
- **F-01-T09** (fixture mode) blocks F-03-T07 (S1). **F-01-T06** (green-run evidence) gates F-01-T07, Q-01-T03, Q-01-T11, F-03-T05, F-03-T18. **F-01-T05** gates F-01-T06.
- **F-02-T01** (decision-log.md) is not built and blocks writing every DEC above.
- Not blocking: F-05-T23, P-01-T02, P-07-T20, P-07-T27, G-01-T07, I-01-T06 have no S0 to S2 dependents.
