---
id: TASK-1334
title: Migration engagement_exports and exports.create, undo, status and history (A-01-T18)
spec: SPEC-344
acceptance_criteria: [AC-6, AC-7, AC-8]
risk_zone: red
status: in-review
epic: A-01
plan_key: A-01-T18
branch: s10b-audit-trail-export
created: 2026-10-26
updated: 2026-10-26
---

## Objective
The engagement export routes stubbed by A-01-T17 (TASK-1261) answer 501. Make create, undo,
history and status live (download stays 501 until A-01-T22): a person with fresh MFA, onshore and
independent creates a `queued` export held by a single-use approval grant whose `not_before` is
ten seconds on (P-35); Undo inside the window voids the grant and leaves an `undone` row and no
package. Acceptance: "Undo inside 10 s leaves an undone row and no package, and agent, offshore
and stale-MFA requests are refused."

## Plan
- **Order of checks (create):** a non-human, support or client principal is refused 403 first;
  the work item resolves through `engagements.api.work_item_engagement` (404 outside the tenant);
  `authorise(ctx, "export.create", engagement resource + work item)` (404 behind a wall, 403 by
  role, independence, `offshore`, stale MFA); only then the `audits.binder_export` flag (404 off).
  Then 422 `export_kind_unsupported` when the work item has no assurance row
  (`engagements.api.assurance_item`; a tax return or any non-audit item), and 422
  `binder_not_in_work_item` when a scope binder id is not one of the work item's asked PBC
  binders (`requests.api.pbc_binders`, read as the requester; DEC-379). Empty scope = every one;
  a work item with none is 422 `binder_not_in_work_item` too (nothing to export).
- **Write (one unit of work):** `issue_grant(action="export.create", subject engagement_export,
  payload = SHA-256 of the requested event, not_before = clock.now + 10 s, expires = +7 days)`;
  insert the `engagement_exports` row (`queued`, `requested_by_kind = 'human'`, `mfa_at`,
  `grant_id`, `not_before`, resolved scope); audit `engagement_export.requested` (identifiers:
  export, work item, kind, binder count; grant); outbox `engagement_export.requested`
  (identifiers only), whose subscriber starts `EngagementExportWorkflow` (TASK-1335).
- **Idempotency-Key** through `kernel.uow.idempotency.idempotent` (route
  `engagement_export.create`, body = work item + request): a replay returns the same export, read
  fresh.
- **Undo:** the requester only, inside the window on `kernel.clock` (`now < not_before`); else 409
  `undo_window_closed`. `void_grant`; a grant already consumed is 409 `effect_started`. Status
  `undone`, `undone_at`, `undone_by`; audit `engagement_export.undone`; outbox
  `engagement_export.undone`. The table trigger repeats the window and the requester rule.
- **Reads:** `export.read` on the work item's engagement (history, newest first, at most 50,
  cursor = keyset on `requested_at, id`), and on the export's engagement (status).
  `allowed_actions`: `undo` for the requester inside the window, `download` when ready and the
  reader may `export.download` (T22 serves it).

## Files
- `backend/migrations/versions/0191_engagement_exports.py` (down 0180, origin/main a0d16491's head; no 0190 exists)
- `backend/src/abacus/modules/evidence/{exports.py,export_models.py,export_events.py}` (new)
- `backend/src/abacus/modules/evidence/export_contract.py` (routes live; download still 501)
- `backend/src/abacus/modules/evidence/{registry.py,api.py,audit_targets.py}` (appends)
- `backend/src/abacus/modules/requests/{source_documents.py,api.py}`: `pbc_binders` (append)
- `backend/tests/integration/test_a01t18_engagement_exports.py` (new)
- `backend/tests/contracts/engagement_export/test_engagement_export_v1.py`: the four live routes
  no longer declare 501 (the test's docstring: "501 on until A-01-T18 and T22")
- `docs/contracts/engagement-export-v1.md`, `docs/product/decision-log.md` (DEC-433)

## Migration 0191
`engagement_exports` (A-01 §4.2 M2): every column of the row; CHECKs on kind, status,
`requested_by_kind = 'human'`, `format_version`, digests, counts, failure and void codes, the
ready CHECK, `undone` and `failed` completeness; FK to `work_items (tenant_id, engagement_id, id)`
and `approval_grants (tenant_id, id)`; index `(tenant_id, work_item_id, requested_at DESC)`.
Column-level INSERT on the create columns, UPDATE on status and the stamps only; DELETE revoked.
Trigger `engagement_exports_guard`: forward transitions only (queued → packaging, undone, failed;
packaging → ready, failed; ready → expired); `undone` only by the requester as a person before
`not_before` (raises `undo_window_closed`). `engagement_export_downloads` and
`engagement_export_contents`: insert-only (ADR-004), immutability triggers. All three
tenant tables with forced RLS (`tenant_table`).

## Registry edits
`evidence/registry.py`: TABLES += 3; INSERT_ONLY += downloads, contents; INSERT_COLUMNS and
UPDATE_COLUMNS = the migration's grants. Matrix untouched (A-01-T17 added the rows). Flag
untouched.

## Tests
`test_a01t18_engagement_exports.py` (Postgres, app role): AC-6 create (row, grant 10 s, audit,
outbox, replay same export), AC-7 Undo inside the window (undone, grant void, no package) and
after (409), AC-8 (422 for a non-assurance item and a foreign binder), refusals (agent, offshore,
stale MFA, staff, walled 404 before the flag, flag off 404), the DB refusing a non-human
requester and an undo after the window, grants as the app role, cross-tenant isolation.

## Rollback
Flag `audits.binder_export` off (every route 404). Migration downgrade drops the three tables and
the trigger function (synthetic data only before Jun 1, 2027; P-38).

## Progress log
- 2026-10-26: plan written; built with TASK-1335 in the s10b worktree (no commits by this agent,
  the lead commits and regenerates).
- 2026-10-26 (relaunched builder): migration 0191 now revises 0180 (no 0190 exists); single head 0191. Fixed in the pass: `engagement_exports` and `engagement_export_contents` added to the integration seed's COUNTS; the schema-check contract test gains `engagement_exports` (and K-01's `methodology_version_states`, ED-111). Decision renumbered DEC-433 (merged with T19's). one targeted pass (`-n 2`, 13 files/dirs: the engagement-export, security-center and compliance-kernel contracts, the A-01-T18/T19 and G-02-T12 integration suites, schema check, the three regenerated security tests, the export builder, worker main, the export replay): 1604 passed, 8 failed; failures fixed and re-run green (20 passed).
- 2026-10-26: security review (PASS WITH FIXES) addressed; see DEC-433's security-review clause. Targeted pass: 291 passed, 1 failed (a test committing through tenant_session), fixed and green on re-run.
