---
id: TASK-962
title: Client record and overview live — subbar facts, tab counts, per-kind overview sections, relationships, add_relationship, PATCH with version and audit (P-07-T09)
spec: SPEC-321
acceptance_criteria: [AC-7, AC-8]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T09
branch: s5-clients-live
created: 2026-10-23
updated: 2026-10-23
---

## Objective
CLI-02 from the API: the record with masked TINs and the derived team, the overview from registered sections each behind its own read action (ADR-024), relationships without edges into walled clients, and a versioned PATCH.

## Plan (red zone)
- **Migration:** `0110_client_version.py` — `clients.version` (default 1) and a BEFORE UPDATE trigger that adds one on any change. Rollback: `alembic downgrade 0109` drops the trigger, its function and the column.
- **Code:** `organisations/live.py` (`client_record`, `client_overview`, sections, `client_relationships`, `add_relationship`, `update_client`), `organisations/events.py` (`ClientUpdated`, field names only), `organisations/models.py` (version, descriptor, masked TIN columns, `EntityRelationship`), routes in `contract.py`; engagements registers its overview section.
- **Tests:** `tests/integration/test_clients_live.py` (masked TIN for an applied-for EIN, the derived manager, tab counts, overview profile and sections, 404 by id, stale version, illegal transition, one `client.updated` event naming fields and never values, edges into a walled client omitted).
- **Rollback:** revert the commit and downgrade 0110.

## Progress log
- 2026-10-23: built. The derived firm-level manager grant on `client.update` (DEC-141) is deferred to P-07-T10, which adds the preparer grant the same way (DEC-153).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-153 | version trigger; changed fields as audit keys; manager grant deferred | no |
