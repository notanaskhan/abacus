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

## 7. Audit and outbox events
Reads write none. Engagement creation writes `engagement.created` and emits `engagement.created`. Every new engagement gets its assurance work item and primary entity from the database (migration 0068 and 0069 triggers).
