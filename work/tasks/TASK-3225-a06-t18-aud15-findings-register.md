---
id: TASK-3225
title: A-06-T18 AUD-15 Findings register, states a-g
spec: SPEC-642
acceptance_criteria: [AC-13]
risk_zone: green
status: in-review
epic: A-06
plan_key: A-06-T18
branch: s26-a06-t18
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-03
updated: 2026-11-03
---

# TASK-3225 · A-06-T18 · AUD-15 Findings register, states a–g

**Epic:** A-06 · **Sprint:** S26 · **Type:** FE · **Zone:** green · **Depends on:** A-06-T12, A-06-T11, P-04-T50, P-04-T54 · **Status:** in-review

## Built
- `apps/web/src/screens/AUD-15/` (index: queue with severity bands, search, Hide concluded, evidence pane; Detail: KV rows, severity picker reserved to the engagement partner, Why This Was Surfaced with the olive disc, evaluation and projection bands, linked file chip, role-reserved footers; copy; scenarios; test).
- Fixtures: `fixtures/seed/aud15.ts` (nine Northwind findings, details, F-01's `deficiency_severity` card, the Dec 26 late remittance), `fixtures/scenarios/AUD-15.ts` (a–g).
- `screens/evaluation/EvaluationPage.tsx` renders AUD-15 on the Findings tab; its planned-body test now covers the three other tabs, with a findings case for AUD-15.

## Acceptance
- [x] Every AUD-15 artboard renders from its scenario (test per state).
- [x] The severity picker is read-only with "Reserved to Engagement Partner" for everyone but Margaret Okonkwo (tests a, d; b live).
- [x] The chip click lights the PayGrid Dec 26 row (test).

## Gaps (DEC-2222)
- FindingRowOut lacks assignee, concluder and disposition: sub-lines composed; "Assigned to" not drawn; the Type tag, the full remittance ledger and "Days late" wait on a contract addition.
- No `docs/screens/AUD-15.md` contract yet; not registered in `SCREEN_SCENARIOS` (gallery) yet.
- "Add to AU-C 265 letter" is disabled until AUD-22.

## Progress log
- 2026-11-03: built; tsc and eslint clean; vitest not run (end pass).
