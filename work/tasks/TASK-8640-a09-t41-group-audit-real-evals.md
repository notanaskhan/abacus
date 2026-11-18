---
id: TASK-8640
title: "A-09-T41: Real eval runs for ledger.tb_mapper and consolidation.elimination_proposer (harness)"
spec: SPEC-658
acceptance_criteria: []
risk_zone: amber
status: in-review
branch: a09-t41-real-evals
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: A-09-T41
---

## Objective
The direct and Bedrock real-run harness for the two group-audit capabilities: per-capability rates against the frozen thresholds, per-case cost and median against evals/baselines.yaml (small and medium tiers), route parity freshness, an HMAC-signed report, and clearance that never covers a firm until it opts in.

## Plan (amber)
1. backend/src/abacus_tools/evals/group_audit_real.py: SUITES and TIERS, below_thresholds, capability_clearance, report (signed), real_main (refuses without ABACUS_EVAL_STACK).
2. __main__.py: --agent group_audit --route direct|bedrock.
3. tests/unit/evals/test_a09t41_group_audit_real.py: clears on Bedrock at every threshold; direct, a missed threshold, no baseline and stale parity never clear; zero-tolerance and errors never clear; the report reads each tier and verifies; refuses without the stack.

## Progress log
- `2026-11-18` — Built in the S50 completion round (DEC-5640). Partial (human): the real Bedrock and direct runs in the evaluation account and the baselines.yaml cost rows from a signed report are a person's step (protected file); the stack-bound loop refuses until it is wired there. The variant flags (on for Dev and PF-X1 only) are not added: no variant flag for these capabilities exists in agents.yaml yet, and adding one waits on the first signed report. Gates and tests run once at the S50 end pass (build first, test last).
