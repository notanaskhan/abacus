---
id: TASK-2618
title: N-02-T45 C7 v1.1 frozen, signatures README, W7 notes, envelope-source skill, hand-off notes
spec: SPEC-381
acceptance_criteria: []
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T45
branch: s21-n02-t45
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Each consumer owner acknowledges the hand-off note and the contract register shows C7 v1.1
frozen." (N-02 §8, §10.)

## Scope
**In**: `docs/contracts/c7-envelopes.md` v1.1 frozen (status, version, consumers, the N-02-T38
additions and a Freeze section with the additive-only rule and what v1.2 adds); the register row
(`docs/contracts/README.md`: v1.1, frozen); `modules/signatures/README.md` rewritten (files,
interface, flags, runbook); W7 notes on `esignature_envelope_send` in `write-capabilities.yaml`;
`.claude/skills/backend-module` "Registering an envelope source and a gate"; `docs/handoffs/N-02/`
(README with an acknowledgement column, A-07, N-04, T-01, T-02, I-01, R-02, W-01, X-01).
**Not frozen (DEC-1666)**: the countersignature session (N-02-T28) and POR-06 part 2 (N-02-T29),
not built; they arrive as v1.2 additions. **Human**: each consumer owner acknowledges their note
(the README's last column). Red only by its zone: no code changes.

## Progress log
- 2026-10-31: written.
