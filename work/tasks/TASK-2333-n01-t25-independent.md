---
id: TASK-2333
title: N-01-T25 independent AC tests for T17 and T22
spec: SPEC-380
acceptance_criteria: [AC-10, AC-12, AC-17]
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T25
branch: s18-n01-t25
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
ADR-078 independent AC tests for N-01-T17 and N-01-T22: flag computation and its interplay with
T18 (forced Hold, bulk refusal on flagged rows), TRI fail-closed, cross-client containment and the
matcher never filing, ignoring, holding or superseding. Acceptance: "Suites are merged and green,
the 2024 Feld 1095-C is flagged wrong year and duplicate through the public API, and no matcher
output path files, ignores, holds or supersedes."

## Plan
Red zone, tests only (no production code, migrations, registry or flag edits; rollback = revert).
- `backend/tests/integration/backfill/test_n01t25_flags_independent.py`: over HTTP as a firm
  person — the 2024 1095-C's `wrong_year` and `duplicate_hash` on `GET /v1/inbox/threads/{id}`
  (facts masked); a TIN mismatch forces Hold on the triage card and filing answers 409
  `flag_requires_hold`; bulk filing answers `has_flags`; filing to another client's request is
  refused and writes nothing.
- `backend/tests/integration/backfill/test_n01t25_matcher_independent.py`: the fake model on the
  real route (T22's stub, ADR-076) — a completed run decides nothing and writes no version; no
  agents code reaches triage apply (AST); the matrix denies agent and system the three inbox
  decisions; TRI without consent makes no model call and no proposal; a reference never given is
  discarded and the other client never reaches the model.
- DEC-1379.

## Progress log
- `2026-10-31` — written from the acceptance text and SPEC-380; ruff and pyright clean. The suites
  run at the end review (integration, testcontainers). `[skip ci]`.

## Handoff
- **Current state:** written, PR open, held for the batch.
- **Exact next step:** N-01-T26.
