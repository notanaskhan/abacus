---
id: TASK-1338
title: AUD-06 remaining states in fixture mode, b, d, e, g and h (A-02-T14)
spec: SPEC-333
acceptance_criteria: [AC-14]
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T14
branch: s10b-ledger-integrations
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Each state matches its scenario, the agent never shows initials, and Hand off to tax and the
entity strip are absent from production builds."

## Plan
- `screens/AUD-06/TrialBalance.tsx`: b's header pill "Draft · Accrued Agent" when every mark is
  the agent's (outlined ticks, no initials, titled "Accrued Agent"); g's chip "TB: Interim ·
  8/31/2026", one "Interim 8/31/2026" column (no BOY without a prior year); e's area picker;
  `PlannedFacts` for g's entity strip and h's "Hand off to tax…" (disabled, tooltip), both behind
  `PLANNED_VISIBLE`; d already drew the AJE column and tag from data.
- `copy.ts` (handoff words), `artboard.tsx` (passes area and planned facts), fixtures:
  `HARLOW_ENTITIES`, `harlowChecks` ("Balances to 0"), `GRANITE_HAND_OFF`, `OPENS[...].planned`.
- Tests: `States.test.tsx` (b, d, e, g, h and the guards), `Production.test.tsx` (with
  `PLANNED_VISIBLE` false: no strip, no hand-off). No agent-authored text on this screen, so no
  `AgentText` use; agent marks carry the agent's name only.
- `docs/screens/AUD-06.md` states and deviations D6, D7.

## Progress log
- 2026-10-26: built; tests at the end of the wave.
- 2026-10-26: one targeted pass at the end of the wave (brief step 7): 1,520 backend tests in the
  touched and covering files (unit integrations, assurance, ledger, workpapers ties, audit
  targets, release and deploy workflows; C9 and C20 contract suites; the three new schema files,
  test_tb_versions, test_schema_check_db, test_retrieval; security a02t10, c09 authz, route
  introspection, tenant isolation, audit targets): 5 failed, fixed, re-run green (expected-map
  and consumer 501 updates; the a02t10 test now turns on `g2_blocks_view` on an attest
  engagement, since G2 binds reads only there, ADR-164; fieldwork registers the adjustment
  source, so all four layers exist in the app). Vitest AUD-06, AUD-02, C9 and C20 fixture
  contracts: 73 passed. Gates: ruff format/check, pyright, lint-imports, banned_patterns,
  error_codes, validate_docs, scope_guards, fresh_mfa, secrets_scan, check-heads,
  check-generated; tsc, eslint, prettier on touched files. Playwright not run.
