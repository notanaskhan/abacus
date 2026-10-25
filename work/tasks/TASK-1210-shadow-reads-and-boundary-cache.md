---
id: TASK-1210
title: Shadow output hidden on every read, and no stale boundary facts in the worker (Q-02-T08 remainder; SPEC-036 AC-5, Q5)
spec: SPEC-036
acceptance_criteria: [AC-5]
risk_zone: red
status: in-progress
epic: Q-02
plan_key: Q-02-T08
branch: s8b-core
created: 2026-10-25
updated: 2026-10-25
---

## Objective
TASK-076 (Oct 19) hid shadow-run output from the agents module's readers. An audit on 2026-10-25 of every reader of agent output found the gaps left since then:
- citation rows written by shadow runs (P-03-T10) are read by the citation display, citation lists, the viewer's regions and relink, with no shadow condition;
- approving a guidance or template draft by id finds a shadow run's draft;
- `_shown_run` is a `NOT IN` over a nullable run id, so a request batch's aggregate (no run) is shown only while the firm has no shadow run, and the gates' screening reader took aggregates as versions' results;
- the boundary's firm facts are cached 60 s per process and cleared only in the API process that changed them; the worker, which makes model calls, never hears.

## Plan
- **Migration 0158:** `citations.shadow boolean NOT NULL DEFAULT false`; back-fill from `agent_runs.shadow`, then successors (update guard disabled for the statement only); the insert grant gains the column. Downgrade restores the grant and drops the column.
- **Writer:** `record_citations(..., shadow=)` (only an agent actor may pass true); `record_agent_citations` takes `shadow` as a required keyword; the screener, upload reviewer and matcher pass `locked.shadow` from the locked run row.
- **Readers:** `shown_citation()` = not shadow and source not withdrawn, in `citation_list`, `verified_citations_into` (viewer regions) and `verified_citations_of` (anchor stacks); `citation_display` and `relink` answer 404 for a shadow row; a relinked successor keeps the flag.
- **Agents:** `get_guidance_draft` and `get_template_draft` filter shadow runs; `_shown_run` shows rows with no run explicitly; `latest_screenings_for_gates` takes per-version rows only.
- **Cache (DEC-337):** `boundary.hold_facts_for(seconds)`; the worker calls `hold_boundary_facts_for(0)` at boot. No outbox event: it would reach only the relay's process.
- **Tests:** `tests/integration/trust_kit/test_shadow_citations.py` (6), `tests/integration/backfill/test_q02t08_shadow_by_id.py` (2), three DEC-337 cases in `tests/unit/ai_gateway/test_client_data_boundary.py`; trust-kit tests pass `shadow=False`.
- **Rollback:** revert the commit and downgrade 0158; the readers then show shadow citations again (today's behaviour).

## Progress log
- 2026-10-25: built. `tests/integration/trust_kit` and `test_schema_check_db.py`: 270 passed before the new file; the new files pass (6 and 2). Boundary unit file: 23 passed.
- 2026-10-25: targeted run `tests/unit/agents tests/unit/ai_gateway tests/unit/evidence tests/unit/worker tests/integration/agent_tests` plus the P-04-T16 projector, P-06-T20 aggregate, this task's by-id file and the F-03 lifecycle migrations (`-n 4`): 2061 passed, 1 failed (`test_work_slot_workflows.py::test_ac6_a_run_with_free_slots_asks_once_and_never_sleeps`, a wall-clock test, under load from five other agents); the file alone: 26 passed. Candidate for `@pytest.mark.serial` (DEC-335) if the end-of-day gate shows it again.
- 2026-10-25: security review fix round. (1) High: 0158's back-fill ran as the owner, which is held to forced row-level security, so it updated nothing; `citations` and `agent_runs` are now unforced for the statements (as 0068 and 0082), and `test_q02t08_citation_shadow_migration.py` seeds at 0157 and upgrades. (2) `_used_in` counted shadow anchors: filtered. (3) A shadow citation's audit events named their engagement in the audit explorer: `audit_owners` leaves them out. (4) Defence in depth: the BEFORE INSERT trigger `citations_shadow_follows` ORs in the run's and the predecessor's flag. (5) The gateway reads the opt-in flag uncached; opting out works with the flag off (DEC-367 amended). Targeted: trust kit, schema check, kernel/evidence/identity unit, by-id file: 14149 passed; migration file 2 passed.
