---
id: TASK-1191
title: Moved and broken citation detection and the human relink (P-03-T12)
spec: SPEC-322
acceptance_criteria: [AC-10, AC-36, AC-37]
risk_zone: red
status: in-progress
epic: P-03
plan_key: P-03-T12
branch: s8a-evidence-pipeline
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"A superseded source marks dependent citations moved within one relay cycle, a relink from an agent or worker context is refused, and a human relink writes a new verified row and an audit event."

## Plan (red zone)
- **Detector** `evidence/citations/moved.py`, outbox consumers composed into evidence's existing handlers (`evidence.api.in_turn`, so the worker's pinned list is unchanged): `evidence_version.created` moves every citation to the item's earlier live versions (`cause_ref = evidence_version:<new>`); `evidence_version.withdrawn` breaks the withdrawn version's citations (`withdrawn:<id>`). Each new event: a `citation.moved` / `citation.broken` audit event and outbox event (identifiers only). Idempotent on the event: one event per citation and cause (`citation_events_once_per_cause`, migration 0152, shared with TASK-1190), emits only for rows written; nothing written, nothing committed.
- **Withdrawn versions (DEC-298, DEC-299):** a withdrawn new version moves nothing (`get_version` hides it); citations to a withdrawn earlier version are broken, not moved; a `moved` event naming a successor withdrawn later no longer counts (`display.state_of(ignore=...)`), and relink never lands on a withdrawn successor.
- **Owners:** `evidence.api.mark_sources_superseded(tx, source_type=, source_id=, old=, new=)` for methodology and workpapers, in their unit of work.
- **Relink** `POST /v1/citations/{id}/relink` served behind `evidence.citations_v2`: `_live_human` (person, not support, `serving_request()`), 404 for walled, withdrawn or firm-level, `authorise(citation.relink)`, advisory lock per citation, 409 `not_moved`, the old quote re-read from the old layer by its hash and found on the newest live successor, verified there by the kind's verifier as the person; new row (`supersedes_id`, same anchor and `n`, `human`), `relinked` event, `citation.relinked` audit. 422 `relink_unverified` writes nothing.
- **Tests:** `tests/integration/trust_kit/test_citations_moved.py` (AC6.1 to AC6.3, including the DB CHECK). Rollback: revert the commit; 0152 downgrades to 0146.

## Progress log
- 2026-10-25: built as planned; 7 new integration tests and the whole `trust_kit` package (60) pass; C4 contract and evidence unit tests pass. `trust_kit/support.Seeder.run_untriggered` seeds a withdrawal row for a version that is not a detached-key upload (the route's own guard is tested by P-06-T19's suites). **Deferred:** P-03-T18's independent suite; methodology and workpaper owners calling `mark_sources_superseded` (K-01, A-04).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-321 | How a withdrawn version and a relink's successor are treated; one event per citation and cause | No |
