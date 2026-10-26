---
id: TASK-1331
title: Audit label index and search (G-02-T10)
spec: SPEC-349
acceptance_criteria: [AC-6, AC-7, AC-11]
risk_zone: red
status: in-review
epic: G-02
plan_key: G-02-T10
branch: s10b-audit-read-service
created: 2026-10-26
updated: 2026-10-26
---

## Objective
`audit_event_labels`, a rebuildable projection of actor and target labels with a `keywords`
tsvector (no Restricted text), maintained from `audit_events` by `seq`; `q` searches it only,
bounded, with `next_cursor`; the IP filter.

## Plan
- Migration **0192** (`down_revision` 0180): `audit_event_labels` (PK `(tenant_id, seq)`, RLS
  forced, GIN on `keywords`, app may insert and update the projection) and `audit_exports`
  (G-02 §4.2: one migration for both; RLS forced; T17 fills it).
- `audit_trail/labels.py`: `index_batch(tenant_id, limit)` idempotent upsert from the last
  indexed `seq`; labels only through `platform.audit_labels` (≤ Confidential) and people's
  display names; `backfill`; `search_seqs` bounded scan.
- The Temporal Schedule (`AuditLabelIndexer`, 60 s, SKIP) is not wired here: the q path catches
  the firm's index up (bounded) before it searches. Recorded in DEC-436.

## Tests
`tests/integration/test_g02t10_audit_labels.py` (pell street iii, SSN never findable,
idempotent replay), suite 1 AC-6.

## Rollback
Downgrade drops both tables (local only); the projection is rebuildable.

## Progress log
- 2026-10-26: built with T08, T09. Migration 0192 (`down_revision` 0180), reversible per
  `schema_check`. Schedule not wired (DEC-436): a search catches the index up by one batch.
  UOW-001 and UOW-002 exclude `audit_trail/labels.py`. The 500 ms p95 at 50,000 events is a
  staging measurement, not run here.
