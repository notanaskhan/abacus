---
id: TASK-966
title: Independent AC tests for the audit hash chain — tamper, late commit, anchor mismatch, restored snapshot (Q-02-T27)
spec: SPEC-304
acceptance_criteria: [AC-1]
risk_zone: red
status: done
epic: Q-02
plan_key: Q-02-T27
branch: s5-compliance
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"Each tamper scenario makes the verifier fail with the checkpoint number, and a clean restore verifies."

Q-02 AC-26 has no SPEC yet: it lives in `docs/plan/epics/Q-02.md` §3; SPEC-304 (the audit log) is the nearest spec.

## Plan (red zone, tests plus one verifier function)
- **Tests:** `tests/integration/test_q02t27_chain_independent.py`, written against the public verifier only. A tampered target and a back-dated business time each name their checkpoint; a late commit inside a closed range (a burnt sequence value, inserted afterwards) flags its checkpoint; an anchor fails when it is forged, when its checkpoint is missing, or when a change sits below it; and a logical restore into a freshly migrated database verifies clean.
- **Code:** `kernel/uow/chain.py` `verify_anchor` (DEC-157).
- **Rollback:** revert the commit.

## Progress log
- 2026-10-23: 5 tests, passing. COMPLIANCE-mode anchor writes are Q-02-T24's.
