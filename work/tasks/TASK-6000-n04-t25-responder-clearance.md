---
id: TASK-6000
title: "N-04-T25 the responder's real runs, clearance per mode and the live rule"
spec: SPEC-000  # row (N-04-T25)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: N-04
plan_key: N-04-T25
branch: s29l-n04-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-07
updated: 2026-11-07
---

## Objective
Clearance is recorded only for modes that pass every threshold on Bedrock, and no pilot firm is above shadow stage at M15.

## Plan
abacus_tools/evals/notices_responder_real.py: `--route direct|bedrock` on a throwaway stack, each case `repeats` times through the gateway with the spec's prompts, tiers and budgets; graded by the fake run's graders (`run(attempts=...)`); per-mode `clearance` (Bedrock only, every frozen threshold of the mode, no errored attempt, median cost within 10 % of baselines.yaml, analyze only once label_review is reviewed); report signed HMAC-SHA256 with ABACUS_EVAL_SIGNING_KEY. evals/baselines.yaml rows (spec budgets 0.25 medium, 0.08 small). evals/notices_responder/clearance.yaml (empty: no real run yet) and a test that client_data turns cleared only with every mode recorded. agents/shadow_score: responder shadow pairs (notices registers `decided_shadows`, run's recommended option against the signer's position; option `partial` is `partially_agree`) and `responder_criterion` (28 days, 10 compared notices, no number-without-provenance refusal); stage_admin.check_live applies it to notices.responder. ShadowScore's shape unchanged, so stored digests still recompute. docs/ops/pilot/notices-responder-shadow-plan.md: clearance, per-firm shadow records, live rule, PF-X1 row. ExtractCase gains optional document_lines (a real run refuses extract cases without them). Rollback: revert; no migration.

## Progress log
- 2026-11-07: built. tests/unit/agents/test_n04t25_responder_shadow.py, tests/unit/evals/test_n04t25_clearance.py written; run at the end pass. Not run: the real direct and Bedrock runs (no evaluation account run, label review pending).

## Decisions made during this task
DEC-2600
