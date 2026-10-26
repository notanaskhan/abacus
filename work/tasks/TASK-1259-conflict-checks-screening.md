---
id: TASK-1259
title: Conflict-check service and screening records (organisations) (P-07-T36)
spec: SPEC-332
acceptance_criteria: [AC-23, AC-24, AC-25, AC-26]
risk_zone: red
status: in-review
epic: P-07
plan_key: P-07-T36
branch: s9a-engagement-lifecycle
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"The Harborline hit is cleared by Samuel Ito with a reason, and a match on a walled client shows
no name to the walled user." Today `organisations/conflicts_contract.py` answers 501.

## Plan (red zone)
- **Migration 0164 `conflict_checks`** (organisations; reversible):
  - `conflict_checks` (insert-only: `subject_kind`, `subject_id`, `names_sealed` (sealed per
    tenant, bound to the check), `names_count` 1–50, `run_by`, `run_at`, `status` clear · hits).
  - `conflict_results` (insert-only: `check_id`, `name_index`, `matched_ref_type` client ·
    client_entity · contact, `matched_ref_id`, `matched_client_id`, `match_kind`, `score`,
    `counterparty_role`).
  - `conflict_result_events` (insert-only, `actor_kind = 'human'` CHECK: `result_id`,
    `assessment`, `reason_sealed`, `cleared_by`, `cleared_at`). The current assessment is the
    newest event's; with none it is `pending` (`counterparty_review` for a counterparty match).
  - `screening_records` (insert-only, `actor_kind = 'human'`: `subject_kind`, `subject_id`,
    `list`, `result`, `recorded_by/at`, `evidence_version_id`, `note_sealed`).
  - Human-only register: `conflict.cleared`.
- **Vocabulary**: `conflict_assessment` gains `conflict` ("Conflict", red-tint, terminal), as the
  contract (§4) says T36 does; regenerate `_statuses.py` and the web status file.
- **Search** (`organisations/conflicts.py`, new): deterministic, synchronous, at most 50 names,
  `SET LOCAL statement_timeout = '2s'`, as a system principal (a `TenantContext` of kind
  `system`, so walls do not narrow the search) over metadata only (names, never documents):
  clients and client entities by normalised name (equal: `exact`; `similarity >= 0.6`:
  `trigram`, `pg_trgm`); contacts the same, except a contact holding a counterparty role
  (custodian, recordkeeper, TPA, payroll provider) on another client is `counterparty`; and for
  each matched entity, every relationship edge to an entity of another client is a
  `relationship` match on that client. One result per matched object and kind (best score).
- **Redaction** (AC-24): at read time, per reader: a result whose matched client is one the reader
  is walled from (`identity.api.walled_from`) is `{id, redacted: true, match_kind, assessment}`
  and nothing else; no count of them anywhere; clearing one answers 404.
- **Clear** (AC-25): `conflict.clear`, human-only: the route refuses client, agent and system
  first, then the service requires a live human; an assessment code and a reason (sealed);
  audited `conflict.cleared`.
- **Screening** (AC-26): `screening.record`; a person's result with an optional evidence link and
  note; audited `screening.recorded`; nothing looked up.
- **Matrix**: the derived `firm_manager` (a manager-level staff member at firm level, as
  `firm_partner` is for partners, DEC-132) joins `conflict.run`, `conflict.clear`,
  `screening.record` and `client.intake` (DEC-326 and DEC-143 left the manager cells for a
  derived grant). Identity: `_roles.yaml`, `authz` (`FIRM_MANAGER`), labels, the manager and tax
  reviewer role templates, the matrix tests' role partition. Banned pattern: only
  `organisations/conflicts.py` and the contract file name `clear_conflict_result`.
- **Subjects**: a client or client entity subject must exist and not be walled from the caller
  (404); draft subjects (engagements' and P-07-T42's intake drafts) are references organisations
  cannot read (module direction), recorded as given.
- **Contract**: `acceptance-independence.md` (status, §4, the manager cells), `make generate`.
- **Tests**: P-07-T38's conflict suite (TASK-1257) unmarked as it passes; stub and consumer tests
  move the conflict routes to LIVE; `tests/integration/test_conflict_checks.py` for the search
  kinds, the timeout setting and the database rules.
- **Rollback**: revert; 0164 downgrades (drops the tables, restores 0163's register).

## Progress log
- 2026-10-26: planned.
- 2026-10-26: built as planned (DEC-373). Results store references and scores, never names;
  the outcome is derived from the newest assessments. Engagement counterparties are contact
  roles only (the ledger's counterparties are another module's). Tests: P-07-T38's conflict
  suite, 9 markers removed, 11 pass; `test_conflict_checks_rules.py` 2 pass; the derived
  `firm_manager` unit test; the stub and consumer contract suites updated (conflict routes
  LIVE, `conflict` now a registry assessment); the role partition and `client.intake` matrix
  tests updated for `firm_manager`; the web registry row count (377). Gates green; `make
  generate`, web tsc and the status and SHL-03 vitest suites.
