---
id: TASK-8320
title: "A-09-T22: AUD-35 Component auditors a-g in fixture mode"
spec: SPEC-658
acceptance_criteria: [AC-0]
risk_zone: green
status: in-review
branch: a09-t22-aud35-fixtures
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: A-09-T22
---

## Objective
Spec section: handoff AUD-35 spec.md.
AUD-35 Component auditors a-g in fixture mode.

## Plan (green)
1. `apps/web/src/screens/AUD-35/`: `ComponentAuditors` (the T9 queue and detail: KV rows, competence and independence, instructions tracker with §5 Needs input, deliverables, questions thread, drafted follow-up, Make reference banner, flag-off g), `copy.ts` (every word from the handoff), `scenarios.ts` (a to g), `AUD-35.test.tsx`.
2. Registered in `screens/gallery.tsx`; `routes/manifest/aud.ts` marks AUD-35 `fixture`.

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. Prettier, eslint, tsc and the screen tests (14) clean while building. Partial: the Tier C parity run, the T2 cockpit chrome and rail, the T10 letter preview, the Send instructions O3 with the invitation preview, the C-38 timeline and the toast are not composed (the design-system pieces are plain markup on tokens here). Gates and
  tests run once at the S47 end pass (build first, test last).
