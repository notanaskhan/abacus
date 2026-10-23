---
id: TASK-923
title: C3 consumer tests for stub 3 (SHL-09 a-f, SHL-15 a-e, SHL-16 a-f); stub 3 recorded as an additive extension of C3 v1 (P-04-T12)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T12
branch: p04-t12-c3-stub-3-tests
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The register records stub 3 as additive by Fri Dec 18, 2026 with the consumer tests green in the provider CI."

## Plan (amber)
- **Files.**
  - `backend/tests/contracts/review_grammar/`: `test_c3_stub3.py`, `test_c3_shl09_field_provenance.py`, `test_c3_shl15_issues.py` and `test_c3_shl16_checkpoints.py`, all new. `_c3.py` gains `example_where`.
  - `apps/web/src/fixtures/contracts/review-grammar.test.ts`: stub 3 frames appended. This file is already on the secrets-scan allowlist for `field_key` line codes.
  - Docs: `docs/contracts/README.md` (the C3 row and the additive note) and `review-grammar.md` (§2 roles, §9 and §10).
- **Migrations and flags.** None. The tests read migrations 0093 and 0094 as text.
- **Additive rule.** New models and operations sit beside stubs 1 and 2, and no existing shape changes, so the frozen-snapshot check (`tests/contracts/test_frozen_snapshots.py`) stays green.
- **Defects.** A contract defect is fixed in the stub, or else gets a strict xfail. A test is never weakened.
- **Rollback.** Revert the commit.

## What changed
- **Pytest** (378 new tests; 763 in `tests/contracts/review_grammar` in all):
  - `test_c3_stub3.py`:
    - routes and actions, with 404 and 501 per handler, the 202s and 201s, and `Idempotency-Key` on send to client;
    - an explicit `agent: deny` and `system: deny` on every part 3 write, and `checkpoint.propose` as the agent's only cell;
    - the QC `reviewer` cells;
    - the registry enums and the derived words;
    - the CHECK lists of migrations 0093 and 0094 against the wire, and the human-only constraints;
    - classification, unique names, and parts 1 and 2 untouched.
  - The SHL-09, SHL-15 and SHL-16 files hold the per-artboard field tables with their tags, and every part 3 §8 example conforms. The figures foot as `Decimal`:
    - 2,190 → 2,310;
    - 4 × 12,000 = 48,000;
    - Checkpoint 6's diff is SHL-10 a's rows, with a net change of 0;
    - the fix run's 1,550 is the line 2a suggestion's;
    - F12:F15 is four participants.
- **Vitest.** 20 new frames and tests (44 in the file). They are typed with the generated client and checked against `openapi.json`, and the same figures foot in bigint.
- **Register.** Stub 3 is recorded as an additive extension of C3 v1 (handshake rule 5). It stays v1 and is gated by these suites for the Dec 11 freeze.

## Findings
1. **The QC `reviewer` role had write cells on part 3** (fixed here, DEC-145 amended).
   - TASK-918 gave the repo's `reviewer` role `issue.update`, `.verify` and `.reopen`, `fix_instruction.set`, `checkpoint.approve`, `.reject`, `.restore` and `.rename`, and `field.add_reference`.
   - DEC-21 makes Tax Reviewer a work-item function, and keeps `reviewer` a read-only QC role.
   - Those cells are removed. `reviewer` keeps the reads, `issue.create` and `issue.explain` (as it raises review notes and asks for analysis), and `field.sign_off` (as it holds `sign_off.create`).
   - `test_c3_part3_the_qc_reviewer_role_writes_only_what_it_writes_elsewhere` holds this.
2. **Route count.** TASK-918 said 13 issue routes. There are 12 (23 in all), and its task file is corrected.

## Progress log
- 2026-10-23: built.
  - pytest `tests/contracts/review_grammar`: 763 passed.
  - vitest on `review-grammar.test.ts`: 44 passed. eslint, prettier and tsc (`apps/web`) are clean.
  - ruff, pyright, banned_patterns, validate_docs, scope_guards and `make check-generated` are clean, and the listed unit, security and contract suites pass.
