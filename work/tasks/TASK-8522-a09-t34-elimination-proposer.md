---
id: TASK-8522
title: "A-09-T34: Capability consolidation.elimination_proposer"
spec: SPEC-658
acceptance_criteria: [AC-4]
risk_zone: red
status: in-review
branch: a09-t34-elimination-proposer
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T34
---

## Objective
Spec section: docs/plan/epics/A-09.md §6, §4.4 (EliminationProposal). Workflow, medium tier: code extracts intercompany pairs and computes every amount and margin; the model writes descriptions and notes and locates the evidence cell; C4 cell citations verified and number provenance checked; proposals land as kind elimination, status proposed, with proposed_by_run_id; propose route; dark behind the variant flag.

## Plan (red)
1. `assurance/elimination_proposer.py`: candidates by code from each mapped entity's FS lines and the structure (E1 investment vs contributed capital by the parent's level; E4 equal receivable/payable; E2 IC sales vs the buyer's COGS; E3 unrealized profit = cited cell × the seller's gross margin; E5 IC rent), the elimination's level = the common parent's; one-sided pairs never proposed. Model input carries no E3 amount; settle keeps a candidate only with valid words, every number from code, and (E3) a cell whose value code read.
2. Tool `assurance.propose_eliminations` (propose; action elimination.agent_propose, agent task_scope only): records the E3 cell through C4 `sheet_cell` with code's value, blocks it unless verified, then `adjustments.eliminations.propose_by_agent` writes the proposed entry (created_by agent, on behalf of the initiator, source_ref run/computation/citations).
3. EliminationView carries proposed_by_run_id, computation and citation ids; AUD-33's group contract shows them.
4. `evidence.api.sheet_rows_for` (the masked cells an agent reads; public wrappers in citations/verifiers).
5. Spec `consolidation.elimination_proposer.yaml`, prompts, codegen (_specs_v2, _eval_suites); route POST /v1/consolidations/{cid}/eliminations/propose live (synthetic firms, variant flag on; else 409 capability_unavailable).
6. Fixes found by banned_patterns here: C12's router moved from ledger to tax (BOUND-002: ledger may not depend on identity); the T-06 seed slices import contract models through each module's api (BOUND-001).
7. Tests `tests/unit/assurance/test_a09t34_elimination_proposer.py` (6 pass).

## Progress log
- `2026-11-17` — Built in the S49 sequential stack (DEC-5522). Ruff, pyright, import contracts and banned_patterns clean; 6 unit tests pass (run once: pure). The C4 anchor type 'consolidation' and the live run are exercised at the end pass; the eval runs are A-09-T41. Gates and tests run once at the S49 end pass (build first, test last).
