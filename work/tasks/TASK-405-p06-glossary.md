---
id: TASK-405
title: Glossary rows for P-06 - binder_recipient, request_upload_intent, screening_feedback, evidence_object_key, UI "Withdraw" (P-06-T04)
spec: SPEC-046
acceptance_criteria: [AC-13]
risk_zone: red
status: done
epic: P-06
plan_key: P-06-T04
branch: p06-t04-glossary
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Glossary PR merges; L12 accepts the identifiers." Add the protected glossary rows P-06's
migrations and screens will need before they land (P-06 §4.10), so P-06-T05, T18 and T20 name
their tables from the glossary and L12 (generated from the "Don't use" columns, SPEC-046 AC-13)
accepts them.

## Plan (red zone: docs only)
- Files: `docs/product/glossary.md`; `backend/tests/unit/quality/test_glossary_l12.py`.
- No migration, registry, flag or matrix edit. No new "Don't use" entries, so the L12 ban list is
  unchanged and no existing identifier can start failing.
- Tests: the new code names are glossary rows; L12 passes the five tables and their classes;
  `upload` stays banned outside the compound.
- Rollback: revert the commit.
- Approval: AMENDMENT-solo §2, decided and recorded by the builder (no second approver).

## What changed
- **New terms: requests** `Binder recipient` (`binder_recipients`, insert-only with `removed_at`;
  not a delegation) and `Request upload intent` (`request_upload_intents`, UNLOGGED, 90 s TTL,
  polled for "Uploading 2 files…"; states that `upload` is allowed only in this compound and the
  legacy `upload_*` tables and stays banned as a synonym of evidence version).
- **New terms: evidence** `Withdrawal` row filled in from ADR-162 with action `evidence.withdraw`
  and the UI word **"Withdraw"**; new `Evidence object key` (`evidence_object_keys`,
  `evidence_versions.storage_mode`; not the S3 object path, not the tenant key).
- **New terms: agents** `Screening feedback` (`screening_feedback`, reason code required on thumbs
  down, insert-only, never changes a verdict; distinct from `agent_feedback`).
- **Copy-level bans** "Remove" or "Delete" on a client's unaccepted upload → "Withdraw" with the
  DF-15 sentence (R-01 records the POR-14 "Remove" as its deviation).
- **Tests** three cases in `test_glossary_l12.py` (P-06-T04).

## Collision check
`glossary_bans()` holds none of `binder_recipient(s)`, `request_upload_intent(s)`,
`screening_feedback`, `evidence_object_key(s)`, `evidence_withdrawal(s)`, nor their first words
(`binder`, `request`, `screening`, `evidence`). L12 compares whole names, singulars and table first
words, so `upload` (banned) inside `request_upload_intents` does not trip it.

## Progress log
- 2026-10-22: rows written from P-06 §4.2, §4.10, DF-15 and ADR-162 (accepted on main as TASK-403;
  the epic still says ADR-137). Checks: `pytest tests/unit/quality/test_glossary_l12.py
  test_glossary_report.py` (10 passed), ruff, `banned_patterns` (clean), `glossary_report`
  (163 terms, 107 bans), `validate_docs` (no new violations).
