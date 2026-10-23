---
id: TASK-961
title: Clients index live — GET /v1/clients on the P-36 envelope through visible_clients, filters, q, exact total, registered client facts (P-07-T08)
spec: SPEC-321
acceptance_criteria: [AC-6, AC-7]
risk_zone: red
status: done
epic: P-07
plan_key: P-07-T08
branch: s5-clients-live
created: 2026-10-23
updated: 2026-10-23
---

## Objective
CLI-01 from the API: rows, status counts, facets and an exact total after `visible(scope=client)`, with walls as 404 semantics and nothing saying a client is hidden (DEC-43, DEC-47).

## Plan (red zone)
- **Code:** `organisations/live.py` (`list_clients`), `organisations/slots.py` (fact registry), `organisations/contract.py` (route), `identity/authz` (`visible_clients` with the derived `firm_partner`; `Resource.client`), `identity/repository.py` (`engagement_team_query`), `kernel/uow` (`audit_activity`), `engagements/client_facts.py` and `requests/repository.py` (registered facts).
- **Matrix:** `client.read` gains `firm_partner: allow` (DEC-141).
- **Module graph:** requests registers its open-request count through `engagements.api` (re-exported), so BOUND-002 and the plan's graph are unchanged.
- **Tests:** `tests/integration/test_clients_live.py` (exact total and counts, keyset paging, cursor bound to its filters, the walled person's same-keys response, engagement-role reach, partner reach, `q` over entity names, the service-line filter and row facts); `tests/contracts/clients/test_clients_stub.py` updated for the live routes.
- **Rollback:** revert the commit; no migration in this task.

## Progress log
- 2026-10-23: built with P-07-T09 in one batch PR. Facts and their definitions in DEC-153. Second TASK-number race in a day (TASK-943 to TASK-948 were taken twice): the `validate_docs` duplicate check runs per branch, so the batch ship script now re-runs it after the rebase.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-153 | fact sources, last activity, `firm_partner` read | no |
