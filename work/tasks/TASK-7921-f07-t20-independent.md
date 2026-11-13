---
id: TASK-7921
title: F-07-T20 Independent AC tests for T14/T17 and the portal kit boundary
plan_key: F-07-T20
spec: SPEC-652
acceptance_criteria: [AC-6, AC-7, I3]  # unmasked TIN, reveal without capability, inputs on the face, Download in the bar, portal import of a firm-only kit
risk_zone: amber
status: in-review
branch: f07-t20-independent
worktree: /Users/ayushkbhatia/Accrued/abacus-s42
created: 2026-11-13
updated: 2026-11-13
---

## Objective
ADR-078 tests for the T14 inspector and the T17 form renderer, and the portal import-boundary
lint forbidding agent/chat, graph and forms-gov.

## Plan
- `packages/ui/src/templates/f07t20.ac.test.tsx`, `apps/web/src/lint/f07t20-portal-kits.test.ts`,
  `apps/web/eslint.config.js` (`PORTAL_FORBIDDEN_KITS`).

## Partial
- "A trace not from a manifest match_id" is held by the type (`MatchId` only from
  `contractMatchId`) and the no-match diagnostic test; a trace-outline test against the TPL-17
  manifest lands with the specimen (F-07-T19, S43).

## Progress log
- 2026-11-13: written, not run (S42 end pass).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4922 | portal refuses firm-only kits by name and path | no |
