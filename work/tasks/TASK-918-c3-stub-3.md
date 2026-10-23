---
id: TASK-918
title: C3 stub PR 3 - issue, fix-instruction, checkpoint and field-provenance models and 501 routes behind review.grammar_api (P-04-T11)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T11
branch: p04-t11-c3-stub-3
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The generated client covers every SHL-09, SHL-15 and SHL-16 operation behind the flag before the Fri Dec 18 train."

## Plan (amber)
- **Files.**
  - `review/contract.py`: part 3 appended (issues and fix instructions, checkpoints, field provenance). New models and routes beside the old; no part 1 or part 2 model changes.
  - `review/api.py`: the three new routers.
  - `docs/contracts/review-grammar.md`: part 3 in §2 to §8, §10 and §11.
  - `docs/product/decision-log.md`: DEC-145.
- **Flag.** `review.grammar_api`, reused. Only its description gains part 3. Its expiry stays 2027-04-21 (DEC-137).
- **Matrix.** `review.yaml` gets the `issue.*`, `fix_instruction.set`, `checkpoint.*` and `field.*` rows. Every write and resolution denies `agent` and `system`. `checkpoint.propose` is service-only (agent `task_scope`); its system cell for engine imports lands with P-04-T32. No row is marked `independence: required` (DEC-145), so `test_independence.py` is unchanged.
- **Migrations.** None. The tables are migrations 0093 and 0094.
- **Tests.** `tests/unit/api/test_app_gates.py` lists the new POSTs (201, 202, or 200 for state changes). The generated matrix and introspection tests cover the new actions. The consumer tests are P-04-T12.
- **Rollback.** Revert the commit.

## What changed
- **Issues** (SHL-15), 12 routes (23 in all):
  - `GET /v1/issues` (list envelope, no titles) and `GET /v1/issues/{id}`, both `issue.read`;
  - `POST /v1/issues` (`issue.create`) and `PATCH /v1/issues/{id}` (`issue.update`);
  - `POST …/resolve` and `…/mark-not-applicable` (`issue.resolve`), `…/verify` (`issue.verify`) and `…/reopen` (`issue.reopen`);
  - `POST …/send-to-client` (`issue.send_to_client`, with an `Idempotency-Key`);
  - `POST …/fix-instructions` and `POST /v1/issues/fix-instructions:bulk` (`fix_instruction.set`, 202);
  - `POST …/explanations` (`issue.explain`, 202), which is beyond the plan's table, for SHL-15 d.
- **Checkpoints** (SHL-16), 7 routes:
  - `GET /v1/checkpoints`, one target's history (`CheckpointHistoryOut`), and `GET /v1/checkpoints/{id}?compare=`, both `checkpoint.read`;
  - `POST /v1/checkpoints` (`checkpoint.create`, 201);
  - `POST …/approve` (`checkpoint.approve`), `…/reject` (`checkpoint.reject`) and `…/restore` (`checkpoint.restore`, 201);
  - `PATCH /v1/checkpoints/{id}` (`checkpoint.rename`).
- **Field provenance** (SHL-09), 4 routes under `/v1/fields/{target_type}/{target_id}/{field_key}`:
  - `GET …/provenance` (`field.read`) and `PUT …/value` (`field.edit`);
  - `POST …/references` (`field.add_reference`, 201) and `POST …/ticks` (`field.sign_off`, 201).
- **Status words.** The generated `IssueStatus`, `IssueSeverityStatus` (priority), `CheckpointStatus` and `AgentRunStatus` (the fix run). `current`, `stale` and `unsupported` are computed booleans. No vocabulary row was added.
- **Examples** (contract §8 part 3):
  - Halvard interest 2,190 → 2,310, with Kevin Osei's tick stale and Samuel Ito's flag;
  - the 48,000 estimate (4 × 12,000) linked to its issue;
  - Feld Checkpoints 1 to 6, Checkpoint 6's steps and diff (net change 0, a tie), and approve, reject, restore (Checkpoint 7), rename and the empty Calloway 1041;
  - the K-1 box 18A issue with its suggestion, fix instructions and explanation;
  - the Northwind opt-out issue with client wording, and the Ridgeline field-flag issue.
- **Names.** Every new component name is unique. The OpenAPI diff is additive only: 49 schemas added, none removed or changed, and no operation id is duplicated. Only the six existing `abacus__` names remain.

## Progress log
- 2026-10-23: built. ruff, pyright, banned_patterns, validate_docs, secrets_scan, scope_guards and `make check-generated` are clean, and the listed unit, security and contract suites pass.
