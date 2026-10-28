---
id: TASK-1710
title: P-04-T32 Checkpoints service
spec: SPEC-360
acceptance_criteria: [AC-8]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T32
branch: s14-p04-t32
created: 2026-10-28
updated: 2026-10-28
---

## Objective
SHL-16's checkpoints live behind `review.grammar_api`: one target's list (agent, named, all), a
code-computed diff against the previous checkpoint or Current, save, approve, reject with a reason,
restore as a new checkpoint, rename and star; author kinds agent, person and import; approving a
proposal's checkpoint is approving the proposal (one decision both SHL-16 and SHL-10 show);
`checkpoint.approved` lets T-01 and N-02 relock a signed 8879 (DEC-85); CHECKPOINT-001.

Acceptance (backlog row): "Restoring Checkpoint 3 creates Checkpoint 7 and deletes nothing, and
approving Checkpoint 6 records one decision that SHL-16 and SHL-10 both show."

## Plan (red)
- `review/models.py`, `events.py`, `repository.py`: ORM for `checkpoints`, `checkpoint_diffs`,
  `checkpoint_decisions` (0094); events `checkpoint.recorded`, `.approved`, `.rejected`
  (identifiers only); reads (LIST-001 exempt: one target, after `checkpoint.read`) and writes.
- `review/checkpoints.py`: the service (DEC-804). `review/contract.py` routes `_stub` → `_live`.
- `review/slots.py`: `register_checkpoint_proposal_hooks`; `agents/proposals.py` registers them and
  calls `follow_proposal_decision` inside approve and reject.
- Migration `0290` (down `0252`): `abacus_human_only_actions()` + `checkpoint.approved`,
  `.rejected`, `.restored` (60 entries). `human-only-actions.yaml` + codegen.
- Matrix: `checkpoint.propose` + `system: allow` (engine imports) + codegen. Error codes
  `checkpoint_changed` (409), `checkpoint_invalid` (422). Activity catalogue entries.
- CHECKPOINT-001 rule; PROPOSAL-001 exemptions for the two hook functions.
- Rollback: revert the branch and downgrade 0290; the routes return to 501 behind the flag.

## Acceptance
| Check | Test |
|---|---|
| Restoring 3 creates 7, deletes nothing; 7's diffs take Current back to 3 | `backend/tests/integration/backfill/test_p04t32_checkpoints.py::test_ac_restoring_checkpoint_3_creates_checkpoint_7_and_deletes_nothing` |
| Approving 6 records one decision SHL-16 and SHL-10 both show | `…::test_ac_approving_checkpoint_6_records_one_decision_shl16_and_shl10_both_show` |
| Current, filters, allowed actions; diff and totals by code | `…::test_current_is_…`, `…::test_the_diff_and_totals_are_code_computed` |
| 409 `checkpoint_changed`, 422 `checkpoint_invalid`, rename/star only | three tests in the same file |
| SHL-10 decisions move the checkpoint; SHL-16 reject rejects the proposal | two tests |
| Agent and system never decide; staff without a reviewer function cannot approve | `…::test_agent_and_system_never_decide_and_staff_cannot_approve` |
| Flag off 404; other firm 404; deltas through `checkpoint_deltas` only | two tests |
| C3 contract: checkpoint routes live, `checkpoint.propose` system cell | `backend/tests/contracts/review_grammar/test_c3_stub3.py` |

## Progress log
- `2026-10-28` — Built. `test_p04t32_checkpoints.py` 12 passed; `tests/contracts/review_grammar`
  806 passed; ruff, pyright, banned patterns, error-code catalogue, `make generate` (descriptions
  only). Two mistakes caught by the tests: domain events refuse Restricted fields (deltas moved to
  `checkpoint_deltas`); the app role has no INSERT grant on `checkpoints.id` (the link flips to the
  checkpoint naming its proposal). Both recorded in DEC-804.
- Migration 0290 sits on 0252 like any S14 migration; if S13 lands 0253+ on 0252 first, the batch
  adds a merge revision (DEC-06), as 0252 did for 0225.

## Handoff
- **Current state:** PR open, held for the S14 batch (stacked on #567).
- **Open:** SHL-16 b steps (C6 run steps), field labels from owners (P-04-T35), T-01's import
  checkpoints call `propose_checkpoint(author_kind="import", cause="engine_import")` as the system.
