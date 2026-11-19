---
id: TASK-8742
title: "C-01-T44: Copperleaf plan v1 as the Close Planner's draft; a person's draft supersedes the planner's"
spec: SPEC-655
acceptance_criteria: [AC-21]
risk_zone: amber
status: in-review
branch: s51q-c01-t44-planner-v1
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-01-T44
---

## Objective
Finish C-01-T44's v1 (TASK-8700, DEC-5722 carried): Copperleaf's plan v1 is the Close Planner's draft started by Raj (a synthetic planner run through the agents recorder), and Raj's own v2 draft supersedes it, so CLS-09's history lists v1 drafted via the agent and v2/v3 published.

## Plan (amber)
1. closes/plans.create_draft: an unpublished agent-drafted version is discarded (audited close_plan.draft_discarded) when a person drafts; a person's open draft still answers 409 draft_exists.
2. closes api exports new_agent_draft; loader _cas_planner_draft records run #1 of close.agent (synthetic recorder) and drafts v1 with its id; cas_slice v1 unpublished.
3. test_c01t44_cas_loaded expects v1 discarded with no rows.

## Progress log
- `2026-11-19` — Built; the CAS load and slice tests pass (9). The planner's drafted rows (its suggestions) are not seeded: v1 is an empty planner draft, as the slice runs no model. Gates and tests run once at the S51 end pass (build first, test last).
