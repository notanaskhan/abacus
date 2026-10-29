---
id: TASK-2039
title: N-02-T17 Record-mode readiness for M8 and M10
spec: SPEC-381
acceptance_criteria: [AC-19]
risk_zone: amber
status: blocked
epic: N-02
plan_key: N-02-T17
branch: s15c-n02-t17
created: 2026-10-30
updated: 2026-10-30
---

## Objective
`signatures.envelopes` on for synthetic firms and the canary, the M10 row "letters at least in
record mode", the onboarding note for importing a firm's existing signed letters, first RB-18
notes; record mode walkable on the production canary by Fri May 28, 2027 and the M10 row green.

## Built
- `signatures.envelopes` in the Brightwater Hale scenario's `FLAGS_ON` (staging, local and the
  synthetic fleet).
- `docs/ops/pilot/import-signed-letters.md`: who, where, the import sheet's fields, the order for a
  pilot firm, failures.
- `docs/runbooks/RB-18-esign-vendor-outage.md` (first notes: what keeps working, the draft outage
  steps from M11, what N-02-T18/T22 complete); the runbook index row.
- `docs/ops/gates/M10-client-facing.md` with the signatures rows (M10-SIG-1 to 4).
- SPEC-381 AC-19. Docs and one flag line: no new tests.

## Blocked on
The production stack and the canary tenant (flag on for the canary, the M8 canary walk), and a PW2
firm (M10-SIG-1, 2).

## Progress log
- 2026-10-30: flag, onboarding note, RB-18 first notes, M10 gate rows and AC built.
