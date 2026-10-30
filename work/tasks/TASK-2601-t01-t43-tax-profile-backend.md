---
id: TASK-2601
title: T-01-T43 Tax profile backend (authorizations, elections, transcripts, comparisons)
spec: SPEC-501
acceptance_criteria: [AC-30, AC-31, AC-32, AC-33, AC-34]
risk_zone: red
status: in-review
epic: T-01
plan_key: T-01-T43
branch: s21-t01-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s21
created: 2026-10-30
updated: 2026-10-30
---

## Objective
CLI-05's tax profile on live routes: migration `0550_tax_profile`, the tax-profile composite,
elections, authorizations with sealed CAF numbers, transcript upload as retrieved evidence through
the scanner, and the comparison against the return as filed, computed by code.

Acceptance: "The Whitley TY2024 comparison returns 2 differences totalling 3,120.00 computed by
code, and the profile never returns a full CAF number or SSN."

## Scope
**In**: migration 0550 (tax-owned: `tax_profile_files`, `tax_authorizations`, `tax_elections`,
`transcripts`, `transcript_lines`, `transcript_comparisons`); `tax/tax_profile.py` (red) and
`tax/tax_profile_repository.py`; `organisations/tax_profile.py` (red: routes, order of checks,
consents and identity band, the backend slot); additive C19 contract fields and four routes
(staging x2, transcript list, latest comparison); `review.api.approved_values`;
`evidence.api.file_retrieved_copy`, `pdf_text`; generated client, error codes, tenant-isolation
table list; SPEC-501 AC-30–34; DEC-1651; C19 contract doc; protected paths.
**Out**: 8821/2848 drafts through C7 (request route stays a stub until P-11 form templates);
`TranscriptCompareWorkflow` (in-request compare, DEC-1651); open notices (N-04); the frontend
(T-01-T50); the ADR-078 suite (T-01-T49).

## Plan
Ownership and seams per DEC-1651. Migration 0550 revises 0406 (main's head at branch time; re-chain
after S18/S20 migrations merge: 0460–0465, 0520–0521). Registry: tax `TABLES`, `INSERT_ONLY`,
`INSERT_COLUMNS`, `UPDATE_COLUMNS`. Flags: `clients.tax_profile` (exists, default off).
Tests: `tests/integration/test_t01t43_tax_profile.py` (AC-30 to AC-34). Security review at the
S21 end review (red diff). Rollback: revert the PR; downgrade drops the six tables.

1. [x] Migration and registry. 2. [x] Review and evidence seams. 3. [x] Tax service and
repository. 4. [x] Organisations routes and composite. 5. [x] Contract, generated client, docs.
6. [ ] End review (tests, gates, security).

## Progress log
- `2026-10-30` — Built on `s21-t01-t43` (stacked on `s21-t01-t45`). pyright and ruff clean on the
  touched modules; app imports; `make regenerate` and the error-code catalogue rebuilt. The
  integration suite ran once: 5 passed (after re-chaining 0550 onto 0406 and identifier-only audit refs). Moved the live routes out of
  `consents_contract.py` into `organisations/tax_profile.py` to avoid an import cycle.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-1651 | tax owns the tables; `ir.*` return-as-filed keys; in-request compare; staging routes; request drafts deferred | no |

## Handoff
- **Current state:** built, PR open, held for the batch.
- **Exact next step:** end review; T-01-T19 must write `ir.<form>.<n>` fields for live imports;
  T-01-T50 swaps CLI-05 onto these routes.
