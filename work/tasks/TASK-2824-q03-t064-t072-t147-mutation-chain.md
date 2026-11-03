---
id: TASK-2824
title: Q-03-T064 part 2, Q-03-T072 and Q-03-T147 (identity/authz survivors, ai_gateway and audit_trail floors, the quarterly sweep)
spec: SPEC-000  # chapter 10 §10.4.4 and the three Q-03 rows
acceptance_criteria: [AC-1]
risk_zone: red
status: in-progress
epic: Q-03
plan_key: Q-03-T064, Q-03-T072, Q-03-T147
branch: q03-mutation-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-03
updated: 2026-11-03
---

## Objective
- **Q-03-T064 (S13):** identity/authz reaches its M8 target (85%), or every survivor has an approved equivalence note. Part 1 was #705.
- **Q-03-T072 (S14):** ai_gateway and audit_trail meet their floors, or carry approved equivalence notes.
- **Q-03-T147 (S23):** no red module is below its floor at the sweep, and the floors are ratcheted.

## Starting point
- Every weekly run since Oct 28 measured nothing (all mutants `not_run`): mutmut's clean test run failed. Each fix surfaced the next blocker, because mutmut stops at the first failing test:
  1. The compute import contract test (`test_a03t21`) read mutmut's own `trampoline` import, which mutmut adds to every mutated file in `mutants/`, as a forbidden dependency.
  2. The ledger dependency test had the same trampoline problem.
  3. `test_coverage_floors` and `test_q03t088_independent` resolve `Path(__file__).parents[n]` to `backend/` inside mutmut's copy, then look for `REPO / "backend" / ...`.
  4. mutmut 3.8 generated invalid Python for `evidence/files.py` (a parenthesised `return (~select…)`).
- Two S23-batch reds were also on main: `section_draft.run` granted to `system`, and the dispatch test's work-class count.
- Local identity/authz run on the rebased branch (2026-11-01/02; 1,585 of 2,020 mutants before it stalled on hanging mutants):
  - 1,110 killed, 23 timed out, 342 survived, 110 with no covering unit test.
  - That is about 71% so far; the Oct 28 baseline was 62.2%.

## Plan
- **Weekly-run blockers:**
  - Skip mutmut's `trampoline` import only inside `mutants/`; the real tree still refuses it.
  - `prepare` links `backend/backend` to `backend/`. `rglob` and `os.walk` follow no directory symlinks, so nothing walks the loop.
  - Name the withdrawal subquery in `evidence/files.py` before negating it.
- **The two S23 reds:** `section_draft.run` becomes the agent's only. That is least privilege: no system path records drafts, so the system-actions test's set drops it. The dispatch count was already fixed on main.
- **Kill tests (identity/authz):**
  - `test_q03t064_condition_facts.py`: `_condition_facts`, `_consents_held`.
  - `test_q03t064_visible.py`: `_visible_by_role`, `visible_scope`, `visible_clients`, `visible_items`, `_member_of`, `holds_engagement_role`, `_g2_blocks_reads`, `_not_walled_client`.
  - `test_q03t064_authorise.py`: `authorise`'s role layer.
  - `test_q03t064_helpers.py`: `authorise_on_condition`, `authorise_with_scope`, `allowed_actions`, the levels, `_in_scope`, `_holds_reserved`, `_engagement_roles_in_firm`, `engagement_client`, `_who`.
- **Measure:** the weekly workflow dispatched on this branch, for every scope. Then:
  - Q-03-T072 against the ai_gateway and audit_trail floors.
  - Q-03-T147: ratchet `backend/mutation-thresholds.yaml` up to the measured scores, rounded down (floors only rise).

## Equivalence notes (for approval)
- **`x_authorise__mutmut_122` and `x_authorise__mutmut_123`:** they rename the `task_scope` removed from an agent's decisions. `allow` is added either way, and the set is only asked whether it holds `deny` or `allow`, so the outcome is identical.

## Progress log
- `2026-11-01`:
  - Found the weekly-run blockers; fixed 1 to 4 and both reds.
  - First CI dispatch (41330062578) died on blockers 2 to 4.
- `2026-11-03`:
  - Rebased on main (b5bd84f79).
  - Wrote 137 kill tests; all pass.
  - Dispatched the weekly run on the branch (41638107797).
