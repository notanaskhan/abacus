# C1 · Work item and engagement lifecycle (v1)

| Field | Value |
|---|---|
| Register row | C1 in `docs/contracts/README.md` |
| Version | v1 |
| Status | frozen (2026-10-21; snapshot `backend/tests/contracts/c1_work_items/v1.json`) |
| Provider epic | F-03 |
| Consumers | every module; ENG-01, ENG-02, AUD-01, BND-01 |
| Freeze sprint | S1 (starts 2026-11-02); frozen early |
| Flag | none (reads only) |
| Spec | `docs/specs/SPEC-306-s1-data-model.md` |
| ADRs | ADR-140; P-04 work items and gates; DEC-39 gate policy |

## 1. Purpose
Consumers can rely on these:
- an engagement's type, chosen from the 14 types;
- its lifecycle status (the registry's 8 codes) and its service line;
- the facts for the G1–G3 gates its type requires;
- its work items, of five kinds, with one assurance item per attest engagement.

## 2. Who may call it
| Operation | Method and path | Matrix action | Roles allowed | Agent or system principal |
|---|---|---|---|---|
| Engagement projection | `GET /v1/engagements/{engagement_id}` | `engagement.read_metadata` | firm roles, engagement team, client roles (metadata) | allowed by the matrix rule |
| Engagement list | `GET /v1/engagements` | `engagement.read_metadata` | as above | as above |
| Work items | `GET /v1/engagements/{engagement_id}/work-items` | `work_item.read_metadata` | firm roles and the engagement team | agent: `task_scope` |
| Work-item list (live, F-03-T31) | `GET /v1/work-items?engagement_id=&kind=&status=&cursor=&limit=` | `work_item.read_metadata` | as above, filtered by `visible_scope(..., "work_item", ...)` | agent: `task_scope` |
| Create a work item (service, F-03-T22) | `engagements.api.create_work_item` (no route yet) | `work_item.create` | engagement partner, manager | agent: deny |

## 3. Models
All the models live in `backend/src/abacus/modules/engagements/routes.py`.

- **`EngagementSummaryOut`**:
  - `id`, `name`, `client_id`, `client_name`, `client_entity_id`, `client_entity_name`, `created_at`;
  - `type`: one of the 14 types;
  - `status`: `EngagementStatus`;
  - `service_line`: audit, tax, cas or advisory;
  - `fiscal_period_start`, `fiscal_period_end` (confidential).
- **`EngagementOut`**: the summary plus `team` and `gates: [GateOut]`. The gates are filled on the single-engagement read.
- **`GateOut`**: `gate` (G1 to G3), `met`, and `blockers`, a list of codes:
  - `acceptance`, `acceptance_declined`;
  - `independence_conclusion`;
  - `engagement_letter`;
  - `no_gate_provider`.
- **`EngagementOut.allowed_actions`** (F-03-T31): the engagement actions the caller may offer, from `identity.allowed_actions` (never recorded as a check).
- **`ListPage[WorkItemRowOut]`** (F-03-T31): the P-36 list envelope (`items`, `next_cursor`, `total`, `total_capped`, `counts` per status, the status filter left out of the counts); rows carry `engagement_id`. Behind `engagements.work_items_api`: on locally, in tests and for synthetic firms; 404 elsewhere until P-07.
- **`WorkItemOut`**: `id`, `kind` (assurance, tax_return, close, notice, advisory_project), `name`, `status` (active, archived), `period_start`, `period_end`, `due_on`, and `phase` (assurance only).

## 4. Status words
`engagement` in `docs/product/status-vocabulary.yaml`: prospect · accepted · declined · contracted ("Letter signed") · active · on_hold · delivered · archived.

## 5. Human-only actions
- **Acceptance** (`acceptance.record`): the engagement partner only, with fresh MFA.
- **The independence conclusion and the letter record** (`letter.record`).
- The agent is denied each of these at the matrix.

## 6. Errors
| Status | Body | When |
|---|---|---|
| 404 | `{"detail": "not_found"}` | unknown engagement, or walled from the caller |
| 409 | `{"detail": "unknown_work_item_kind"}` | creating a work item of an unregistered kind (the slot) |
| 409 | `{"detail": "work_item_exists", "facts": {"kind": …}}` | a second assurance item, or a second close for a period |
| 422 | `{"detail": "cursor_invalid"}` | a cursor this list didn't issue for this firm and these filters |

## 7. Audit and outbox events
Reads write none. Engagement creation writes `engagement.created` and emits `engagement.created`. Every new engagement gets its assurance work item and primary entity from the database (migration 0068 and 0069 triggers).

## 8. C1 v1.1 note (P-07-T05)
Additive, no C1 field changes: P-07's engagements family (`engagements-v2.md`) adds the gate facts with blockers for G1 to G9 (`GET /v1/engagements/{id}/gates`, `EngagementGateOut`), the v2 index and record projection beside `GET /v1/engagements` and `GET /v1/engagements/{id}`, the interim recorded letter, and the engagement-type catalogue that F-02-T11's check covers (no `single_audit`). Behind `engagements.v2`; stub 2026-10-23.

## 9. Brightwater Hale E0 examples (F-03-T06)
Captured from the API on the E0 scenario with the binders slice (`make seed-demo SLICE=binders`), read by Grace Holloway (firm admin), on 2026-10-26. These are synthetic: Brightwater Hale only (ADR-085). Each block is `GET /v1/engagements/{engagement_id}/work-items` for the client's first engagement in the `GET /v1/engagements` order. Engagement ids are stable across loads; work-item ids are made by the database's trigger at load and differ from one load to the next.

### Copperleaf Coffee Roasters, Inc.: TY2025 Form 1120-S (`active`)
Engagement `73767760-de32-4fe0-a437-6776d12762b1`.

```json
[
  {
    "due_on": null,
    "id": "349e31ba-2399-4501-81df-9f2c3a7ecae0",
    "kind": "tax_return",
    "name": "2025 Form 1120-S",
    "period_end": "2025-12-31",
    "period_start": "2025-01-01",
    "phase": null,
    "status": "active"
  }
]
```

### Northwind Robotics, Inc.: PY2025 EBP Audit (`active`)
Engagement `36cf7ac7-6f57-4dd7-b71d-2ebff60c6928`.

```json
[
  {
    "due_on": "2026-10-09",
    "id": "680f7807-73b6-47db-be35-c68a4a9b72bf",
    "kind": "assurance",
    "name": "PY2025 EBP Audit",
    "period_end": "2025-12-31",
    "period_start": "2025-01-01",
    "phase": "planning",
    "status": "active"
  }
]
```

### Bluestem Analytics, LLC: TY2025 Form 1120-S (`active`)
Engagement `ea61faf9-5033-430d-b91f-757a8411bca1`.

```json
[
  {
    "due_on": null,
    "id": "de3dbfab-ce74-470b-bfad-bbabbd757d78",
    "kind": "tax_return",
    "name": "2025 Form 1120-S",
    "period_end": "2025-12-31",
    "period_start": "2025-01-01",
    "phase": null,
    "status": "active"
  }
]
```

### Meridian Tool & Die, Inc.: TY2025 Form 1120 (`active`)
Engagement `95a4a979-3d58-4885-a947-dc3067aa86fc`.

```json
[
  {
    "due_on": null,
    "id": "217e3314-d8c0-4ac4-9b1b-faaa1d2cbc96",
    "kind": "tax_return",
    "name": "2025 Form 1120",
    "period_end": "2025-12-31",
    "period_start": "2025-01-01",
    "phase": null,
    "status": "active"
  }
]
```
