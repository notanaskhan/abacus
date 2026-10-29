---
id: TASK-2124
title: P-04-T40 E7 human-gate kit and useGate
spec: SPEC-000  # P-04-T40 row; SPEC-360 holds the gates' ACs, the kit's own is the backlog row
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: P-04
plan_key: P-04-T40
branch: s16-p04-t40
created: 2026-10-29
updated: 2026-10-29
---

## Objective
The E7 kit in `packages/ui/src/gates`: ApprovalCard (reasoning, diff rows, evidence rows, policy
note, set link), SignOffSlots (C-25), DecisionCard (sheet and inline), ChecksList; `useGate` in
`apps/web/src/domain/review`; the `e7-gates` specimen.

Acceptance (backlog row): "The specimens render in /components with axe clean, and no gate verb
renders through anything but HumanAction."

## Plan (amber)
- Files: `packages/ui/src/gates/*`, `packages/ui/src/specimens/gates.tsx` and its SPECIMENS row,
  `packages/ui/src/index.ts` export, `apps/web/src/domain/review/useGate.ts`.
- No migration, registry or flag edit. Rollback: revert the commit; no screen imports the kit yet.
- Tests: `packages/ui/src/gates/gates.test.tsx` (every gate verb through HumanAction, none for the
  agent, uncited blocks Approve, failing check holds Sign off, Decide held until a choice),
  `apps/web/src/domain/review/useGate.test.ts` (busy until the answer, 409 to blocked with
  identifier facts, 403 to step-up). Axe: `e2e/components.spec.ts` covers every specimen.

## Progress log
- 2026-10-29: built (S16 block; full test pass at the batch's end review). DEC-1171.
