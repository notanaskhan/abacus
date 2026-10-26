---
id: TASK-1328
title: CLI-07 Acceptance and continuance screen with the decision dock (P-07-T46)
spec: SPEC-332
acceptance_criteria: [AC-2, AC-6, AC-7, AC-11]
risk_zone: green
status: in-review
epic: P-07
plan_key: P-07-T46
branch: s10b-independence-intake
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Build CLI-07 (docs/screens/CLI-07.md) on T2 with a local DecisionDock in SHL-11 grammar over the
live acceptance routes (P-07-T35): states a, b, d, e, f live, c and g fixture-only; manual checks,
human flags with sources (SHL-08 planned), conditions, the risk-partner review, the rationale
rule, the MFA step-up and the locked view. Acceptance: "Scenarios a to g pass with axe and only
the engagement partner sees an enabled Decide control."

## Plan
- **Fixtures:** `fixtures/seed/acceptance.ts` (Thornbury, Meridian, Granite Peak records,
  engagements and teams as the live API shapes them), `fixtures/handlers/acceptance.ts` (the
  record, engagement, team, candidates and every write with the live refusals; `allowed_actions`
  by the persona's team role), `fixtures/scenarios/CLI-07.ts` (a–g with viewers and clocks).
- **Domain:** `domain/engagements/acceptance.ts` (query and write hooks over the generated
  client), `domain/engagements/DecisionDock.tsx` (the SHL-11-grammar dock body and footer).
- **Screen:** `screens/CLI-07/{index.tsx, copy.ts, scenarios.ts, CLI-07.test.tsx}`.
- **Registries:** route `/clients/$clientId/acceptance/$engagementId` in `routes/firm/clients.tsx`
  behind `engagements.acceptance_v2`; manifest CLI-07 planned → live with the path; the gallery
  artboard; `e2e/screens/CLI-07.spec.ts` (axe at 1440×900).
- **Docs:** the screen contract (status, code, copy, deviations, gaps); DEC-431.
- **Rollback:** remove the route and the gallery entry and set the manifest entry back to
  planned with `path: null`; no backend, migration or flag change.

## Progress log
- 2026-10-26: Built fixtures, domain hooks, DecisionDock, the screen, route, manifest (live),
  gallery and the axe spec; contract and DEC-431 recorded. Only frontend files touched; no
  generated file or backend file edited. Playwright (axe) not run (chromium mismatch, per the
  sprint brief); the vitest file covers a–g, the revision's acceptance bullets, the decision
  flow, the step-up and the partner-only Decide.
