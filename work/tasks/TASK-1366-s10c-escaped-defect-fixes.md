---
id: TASK-1366
title: Fix ED-116 to ED-118 (closed-binder client writes, intake commit race, independence conclusion race)
spec: SPEC-323
acceptance_criteria: [AC-3]
risk_zone: red
status: in-review
epic: R-01
plan_key: R-01-T20
branch: s10c-fixes
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Turn the three strict xfails S10 wave C's independent suites hold green without editing their
assertions: a closed binder takes no client act (ED-118), and the losers of two races answer the
contract instead of 500 (ED-116, ED-117).

## Plan
- **ED-118 (red):** `requests/closed_binders.py`: `BinderClosed` (409 `binder_closed`,
  `facts.binder_id`) and `refuse_closed` for client principals only (`ctx.client`); a binder not
  published when it closed answers 404 (DEC-333). Called after authorisation in every client
  write: `lifecycle.ignore_item`, `undo_ignore`, `announce_upload`; `binders.mark_done`,
  `undo_mark_done`; `comments.post_comment`;
  `client_responses.respond`; `evidence.uploads.authorise_upload` and `attach` (upload, unlock);
  `evidence.withdrawals.check_withdraw`. Routes newly declaring 409: upload intents, both comment
  posts, both SPEC-042 responses. A drop on a closed binder keeps its 404 (R-01-T15 asserts it). `make generate` (additive 409s).
- **ED-117:** `conclude_independence` runs its unit of work in `_conclude`; an `IntegrityError`
  on `independence_conclusions_first` or `independence_conclusions_tenant_id_supersedes_id_key`
  is 409 `stale_version` (`ConclusionSuperseded`).
- **ED-116:** `commit_intake` runs its unit of work in `_commit`; an `IntegrityError` on
  `client_entities_one_name`, `client_entities_one_tin` or `contacts_one_email` answers the
  stored result if the draft is committed, else 409 `stale_version`.
- Docs: DEC-461; ED rows fixed; `portal-pbc`, `c5-requests-binders`, `acceptance-independence`,
  `intake-import` error tables; `error-codes.yaml` rebuilt.
- Migrations: none. Flags, matrix, registry: none.
- Tests: the three suites' strict xfails removed once green unchanged; targeted pass over them,
  `security/test_portal_scope_isolation.py` and the touched routes' existing tests.
- Rollback: revert the commit (no schema change).

## Progress log
- 2026-10-27: built ED-116 to ED-118; the three strict xfails removed with their tests unchanged.
  Targeted pass: 17 non-backfill files 1053 passed, 4 xfailed (pre-existing, TASK-1221 and
  TASK-1230); 13 backfill files 223 passed, 1 failed: R-01-T15's drop on a closed binder asserts
  404, so the drop keeps its 404 (no 409 there) and that case passed on re-run. Gates clean:
  ruff, pyright, lint-imports, banned_patterns, error_codes (`--write`: `binder_closed`),
  validate_docs, scope_guards, fresh_mfa, secrets_scan, check-generated. Playwright not run.
