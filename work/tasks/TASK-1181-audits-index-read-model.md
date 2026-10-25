---
id: TASK-1181
title: AUD-01 index read model GET /v1/audits - tiles minus the active tile, segments, caption, facets, PBC, report due, archive clock (A-01-T08)
spec: SPEC-330
acceptance_criteria: [AC-18, AC-19, AC-20, AC-21]
risk_zone: amber
status: done
epic: A-01
plan_key: A-01-T08
branch: s8a-audits-read
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Fairhaven's PBC reads a dash before G3, Bayside reads Archive in 13 days at E0, and a walled user's totals foot without the hidden rows."

## Plan (amber zone)
- **engagements:** `index_facts.assurance_index()` (a subquery of the assurance work items with their engagement, client, entity, office, phase, profile and due date, as `work_item_index` does for binders) and `letters_sent(tenant, ids)`; exported through `engagements.api`. **organisations:** `entity_name_column`.
- **requests:** `requests.api.pbc_counts(ctx, work_item_ids)` (A-01-T10's, used here).
- **assurance:** `index.py` (filters, `visible(engagement.read_metadata)` base, tiles as `counts` over the base without the tile, segment facets over the base without the segment, the caption over the tile base, keyset cursor on tile order, report due and name; EP/Mgr initials; report-due tone and archive clock on `kernel.clock`; tags from registered providers, `content` ones only for rows the viewer may read with `engagement.read`; run badge from a guarded C6 slot); the route goes live behind `audits.cockpit`.
- **Matrix, flag, registry:** none changed.
- **Tests:** `tests/integration/test_audits_index.py` (AC-18 to AC-21); the stub contract test stops expecting 501 here.
- **Rollback:** revert; the route answers 501 again.

## Progress log
- 2026-10-25: built. `GET /v1/audits` live behind `audits.cockpit` (`assurance/index.py`, `engagements.api.assurance_index`, `organisations.api.entity_name_column`). E0 as Grace (firm admin): 27 = 7 + 9 + 6 + 2 + 3, caption 14 · 6 · 4 · 3, segments 6 · 14 · 7; Fairhaven PBC null; Bayside "Archive in 13 days"; a walled reader's totals foot without the row. Note: Hannah (manager) sees only her own engagements under `engagement.read_metadata`; the spec's "Hannah sees 27" assumes a firm-wide reader. Tests: `test_audits_read_models.py`, `test_scenario_assurance.py`, `tests/unit/assurance/test_audit_providers.py`.
- 2026-10-25: security review fixes (failing tests first): the read model refuses client, agent and system itself; run badge for content readers only; `q` escapes LIKE wildcards; an archived work item reads Archived (DEC-311).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-311 | Index rules: base, archived rows, released date before A-01-T23, segments, tags | No |
