---
id: TASK-1743
title: N-02-T12 Independent AC tests for signatures v1 and record mode (T07-T09)
spec: SPEC-381
acceptance_criteria: [AC-1, AC-2, AC-3, AC-16, AC-17]
risk_zone: red
status: in-review
epic: N-02
plan_key: N-02-T12
branch: s14-n02-t12
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADR-078 independent tests for N-02-T07 (migration 0292), T08 (record-mode import) and T09 (sources
and G3). Acceptance (backlog row): "The suite passes on N's code and fails on a planted UPDATE of
signature_evidence or an agent-principal import."

## Plan (red, tests only)
- `backend/tests/integration/backfill/test_n02t12_signatures_independent.py`, own buckets and
  firms, written from SPEC-381 and the permission matrix:
  - insert-only `signature_evidence` and `envelope_events` for the app role and the owner (the
    planted UPDATE), rows unchanged after the attempt;
  - INV-1 at three layers: the matrix denies agent and system every SPEC-381 §9 human-only verb;
    `authorise` refuses an agent holding `envelope.import_record` in its task scope and a system
    context; the database refuses `imported_by` under an agent, a system or another person;
  - forced RLS on all 13 signatures tables; another firm's rows invisible to the app role; another
    firm's person answered 404;
  - COMPLIANCE locks on the letter, certificate and manifest until the firm's floor; the bucket
    refuses shortening (COMPLIANCE and GOVERNANCE-with-bypass) and deleting the locked version;
  - scanner error, timeout and infected refused, nothing staged; attestation false or missing 422;
  - G3 truth table over all 8 subsets of {provider letter, record import, `letter.record`}, plus a
    record import of another purpose never meeting it;
  - INV-3: a walled person's stage and import answer 404 with no count, before the file check;
  - INV-5: the importer on the envelope, audit, outbox and write-once manifest.
- DEC-833 in the decision log.

## Progress log
- `2026-10-29` — Written and run once: 40 passed. ruff, format and pyright clean. One fix while
  running: deleting a key without `VersionId` writes a delete marker (allowed, the locked version
  stays), so the suite deletes the locked version itself.

## Handoff
- **Current state:** PR open, held for the batch.
- **Next:** Q-04-T012.
