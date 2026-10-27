---
id: TASK-1463
title: C3 services v1 freeze (P-04-T27)
spec: SPEC-360
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
epic: P-04
plan_key: P-04-T27
branch: s12-review
created: 2026-10-27
updated: 2026-10-27
---

## Objective
`docs/contracts/review-grammar.md` complete for the services (callers, status words, human-only
actions, audit events), the new codes in `docs/architecture/error-codes.yaml`, a frozen OpenAPI
snapshot and the register updated. Acceptance: "The register marks C3 services v1 frozen by Fri
Apr 16, 2027, and removing a field fails the snapshot diff."

## Plan
- `abacus_tools/contracts.py`: `MODELS["review_grammar"]` lists the C3 request and response
  models of parts 1 to 3; `python -m abacus_tools.contracts --freeze review_grammar v1` writes
  `backend/tests/contracts/review_grammar/v1.json`.
- A test that drops a field from `AgentProposalOut` and finds the break.
- Contract doc: "Live (P-04-T24, T25, T26)" paragraphs, the refusal order, the adapters, the
  error rows, the human-only list (0231), the notification kinds, the version row; register row
  C3 `frozen`.
- Error codes: `suggestion_changed`, `proposal_invalid`, `proposal_changed`, `uncited_change`
  and the rest checked with `error_codes --write`.
- **Rollback**: revert (a frozen snapshot is never rewritten; a later change ships v2).

## Progress log
- 2026-10-27: planned.
- 2026-10-27: built (acceptance tests first; run in the end-of-batch targeted pass). Claude Code restarted mid-build; the worktree was saved as WIP commit 743d43fa and the build resumed from it. Decisions DEC-600 to DEC-608; migrations 0230, 0231; SPEC-360 gains AC-4 to AC-7.
