---
id: TASK-1317
title: F-03-T09 status serialisation - propose ADR-190 (bare codes) instead of {code, context}
spec: SPEC-306
acceptance_criteria: [AC-2]
risk_zone: amber
status: in-review
epic: F-03
plan_key: F-03-T09
branch: s10-f03-t09-status-context
created: 2026-10-26
updated: 2026-10-26
---

## Objective
Close the reconcile's F-03-T09 gap ("every API status field serialises as {code, context}")
without breaking the frozen contracts.

## Plan
- ADR-190 (proposed): API status fields stay bare codes; the SPA picks the label context; a
  server-known discriminator is its own field. Amends ADR-138's one sentence.
- DEC-413 records why the clause is not built and that it stays open until ADR-190 is accepted.
- No code. Rollback: revert.

## Progress log
- 2026-10-26: drafted (AGENTS.md "How you work" item 9: contradicting an accepted ADR means a
  new ADR, not a workaround).
