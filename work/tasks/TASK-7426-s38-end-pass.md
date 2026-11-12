---
id: TASK-7426
title: "S38 end pass: regenerated client, gates, tests, security review of the red diffs, one fix round, restack and batch merge"
spec: SPEC-647
acceptance_criteria: [AC-T7]  # the sprint's gates; one review, one fix round
risk_zone: amber
status: in-progress
branch: s38-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: S38-end-pass
---

## Objective
Every S38 PR passes the gates together on fresh main, the red diffs are reviewed once, the fixes
land in one round, and the PRs merge as independent squash commits with CI on the last.

## Progress log
- 2026-11-12: stack rebased cleanly on main 256f5c13f; client and generated tests regenerated;
  check-fast gates fixed (validate_docs, banned patterns, secrets scan, ui lint); security review
  of the red diffs: no blocking finding. Heavy suites run under the test lock.
- 2026-11-12: suites run under the test lock (shared with S36 twice). Unit: pinned sets plus
  real defects: audit Refs carrying text or a bool (would 500), audit targets, AnalystModeWorkflow
  histories. Integration found: approve 503 for adapter kinds and no caller of `apply_proposal`
  (DEC-4415), the residency row uncited, a second confirm raising MissingAuditEvent, gate reads
  filtering on `spec_version` (engagement runs record 1), the materiality step's generic raise
  (DEC-4416, strict xfail), TXI-02 agent text outside AgentText; plus test bugs (uow nesting, hold
  insert, flags, ECDSA signature bytes, TRI capability set, nested run JSON). T52 budgets set from
  measurement. Pre-existing on main, left: `test_screening_contract` alone fails collection
  (order-dependent spec load); WeasyPrint needs libgobject locally (CI has it).
