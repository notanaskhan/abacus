---
id: TASK-2006
title: F-06-T07 Independent AC tests for the signing kit
spec: SPEC-400
acceptance_criteria: [Story 1.1, 1.2, 1.4, 1.6, 1.7, 1.8]
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T07
branch: s15n-f06-t07
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADR-078 independent tests for the T16 kit, from F-06 §3 and the row: one spouse cannot act on the
other's fields, no agent element, no full TIN, the provider frame titled and sandboxed with return
parameters never trusted, DF-11 copy, no native identity export, and every state axe clean with
the 390 geometry (no sideways scroll, 44 targets, the bar never over the active field).

## Acceptance
- `packages/ui/src/signing/f06t07-independent.test.tsx` (jsdom).
- `apps/web/e2e/screens/TPL-16.spec.ts` (Playwright: axe on b, d, e, f, pending; 390 on TPL-16g and
  TPL-19 frame 9).

## Progress log
- 2026-10-29: written from the spec on its own data (Ann and Ben Lee, Harbor Lane), stacked on
  s15n-f06-t05. Not run yet (end review).
