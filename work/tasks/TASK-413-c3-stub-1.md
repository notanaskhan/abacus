---
id: TASK-413
title: C3 stub PR 1 - sign-off, review-note and human-gate models and 501 routes behind review.grammar_api (P-04-T07)
spec: SPEC-308
acceptance_criteria: [AC-5]
risk_zone: amber
status: done
epic: P-04
plan_key: P-04-T07
branch: p04-t07-c3-stub-1
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"The generated client exposes every sign-off and review-note operation returning 501 behind the flag, with Brightwater Hale example payloads in the contract doc."

## Plan (amber)
- **Files:** `review/contract.py` (models and stub routes), `review/api.py` (routers), `docs/contracts/review-grammar.md` part 1, the register row, DEC-135.
- **Flag:** `docs/architecture/feature-flags/review.yaml`, `review.grammar_api` (new file).
- **Matrix:** new `review.yaml` rows. The SPEC-041 note rows move there from `fieldwork.yaml`; their cells are unchanged.
- **Migrations:** none.
- **Tests:** none new. The consumer tests are P-04-T09. The generated matrix tests cover the new actions.
- **Rollback:** revert the commit. Nothing reads the stubs yet.

## What changed
- **Routes.** `review/contract.py` holds the C3 part 1 models, each field classification-tagged, and their stub routes. Off, every route answers 404. On, it answers 501 `not_implemented`.
  - `GET /v1/sign-offs` (ladder) and `GET /v1/sign-offs/eligibility`, both `sign_off.read`.
  - `POST /v1/sign-offs` (`sign_off.create`).
  - `POST /v1/sign-offs:bulk` (`sign_off.bulk`), which requires `Idempotency-Key`.
  - `GET /v1/review-notes`, the list envelope, and `GET /v1/review-notes/{id}`, both `review_note.read`.
  - `POST /v1/review-notes` (`review_note.raise`).
  - `POST …/{id}/respond`, `/clear` and `/withdraw`.
  - `GET /v1/human-gates` (`human_gate.read`), the list envelope with per-kind counts.
- **Matrix.** New rows: `sign_off.read`, `sign_off.create`, `sign_off.bulk`, `review_note.read`, `review_note.withdraw` and `human_gate.read`. Every write denies `agent` (and `system`).
  - The existing `review_note.raise`, `respond` and `clear` rows moved from `fieldwork.yaml` to `review.yaml`, since ADR-160 clause 6 gives notes to review. Their cells are unchanged.
- **Decision DEC-135.** The level actions L1 to L5 are the existing `sign_off.prepare`, `review`, `manager`, `partner` and `eqr` rows, not new `sign_off.l1` to `l5` aliases.
- **Decision (contract §11).** Note bodies are sealed and Restricted, so list rows carry no body, and a detail route returns it. This route is beyond the plan's table.
- **Flag.** `review.grammar_api`: owner ayushkbhatia, created 2026-10-22, expires 2027-01-20.
- **Contract doc.** `docs/contracts/review-grammar.md` part 1, with the SHL-12 a, a′, b, c, e, f and g examples: Trial Balance v1, `sha256:9f4c…e21a`, 14 of 14 cited, run #4127. The C3 register row moves to `stub`.
- **Generated files.** `make regenerate` and `make generate` were run.

## Progress log
- 2026-10-22: built per the S3 batch rules, static checks only. ruff, pyright, banned_patterns, validate_docs and `make check-generated` are clean, and the generated matrix tests for the new actions pass.
