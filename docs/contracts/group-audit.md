# Group audit (v1)

| Field | Value |
|---|---|
| Register row | epic contract (A-09 §8.1) |
| Version | v1 (additive) |
| Status | stub (A-09-T03) |
| Provider epic | A-09 (N) |
| Consumers | K-04, N-03, Q-05, AUD-34, AUD-35, POR-23 |
| Freeze sprint | S45 (Fri Jul 21, 2028, A-09 §8.1) |
| Flag | entitlement `group_audit`; rollout `ledger.consolidation`, `assurance.group_audit` (A-09-T09) |
| Spec | `docs/specs/SPEC-658-a09-group-audit.md` (F5 to F8) |
| ADRs | ADR-146 (P-09), ADR-160, ADR-161, ADR-163, ADR-236 (proposed) |

## 1. Purpose
Components and planned work, group scoping with materiality options, coverage and aggregation (code), the two decision kinds, component auditors, deterministic instructions and their human send, deliverables with Late derived, and the component auditor room.

## 2. Who may call it
Every route answers, in order: a client principal 404; the action on the work item's engagement (walls 404, independence 403), or on a record's own path the entitlement first and the service's authorisation; 404 without `group_audit`; then 501 naming its task. Every field is classified; balances and evidence are client confidential, materiality firm confidential; nothing here carries TRI. Code: `backend/src/abacus/modules/assurance/group_contract.py` (ledger stays dependency-free, DEC-66, so assurance hosts the routes). Typed fixtures: `assurance/group_fixtures.py` (computed footings).

| Operation | Method and path | Matrix action | Task |
|---|---|---|---|
| Scoping | GET `/v1/audits/{wid}/group-scoping` · `…/export.xlsx` | `group_scoping.read` | T23 |
| Component | PUT `/v1/components/{id}` (422 `component_pm_invalid`) | `component.edit` | T23 |
| Group materiality | POST `/v1/audits/{wid}/decisions/group-materiality` → P-04 decide (EP, rationale, fresh MFA) | `group_materiality.propose` / `decision.decide` | T23 |
| Component auditors | GET/POST `/v1/audits/{wid}/component-auditors` | `component_auditor.read` / `.manage` | T27 |
| Instructions | POST `/v1/component-auditors/{id}/instructions/draft` · PATCH `/v1/component-instructions/{id}` · POST `…/send` | `component_instructions.draft` / `.edit` / `.send` | T27 |
| Make reference | POST `/v1/component-auditors/{id}/make-reference` | `component_auditor.manage` | T27 |
| Deliverables | GET/POST `/v1/component-auditors/{id}/deliverables` · POST `/v1/component-deliverables/{id}/review` · `/return` | `component_deliverable.read` / `.manage` / `.review` | T28 |
| Room (portal) | GET `/v1/portal/component-rooms/{id}` · `/instructions` (+ `/pdf`) · POST `/instructions/acknowledge` · POST `/deliverables/{did}/uploads` · `/drops` · GET/POST `/questions` | `component_room.read` / `component_instructions.acknowledge` / `component_deliverable.upload` / `component_room.ask` | T33 |

The room (`portal/component_room_contract.py`) answers a firm principal 404 and serves only the grant's `component` scope; every other component, the consolidation, eliminations, scoping and group materiality are 404 (INV-4).

## 3. Models
`GroupScopingOut` (decision facts 240,000 / 180,000 / 12,000, `GroupMaterialityOptionOut`s from code, `GroupComponentOut`s with PM and % of group PM, `GroupCoverageOut` per measure), `ComponentAuditorOut`, `ComponentInstructionsOut` (sections with needs-input, provenance, the send-blocked reason, content hash), `ComponentDeliverableOut` (Late derived), and the room's `ComponentRoomOut`, `RoomInstructionsOut`, `RoomDeliverableOut` (client words only). Fixture footings: component PMs 135,000 + 105,000 + 54,000 + 90,000 = 384,000; coverage 78% / 22% of 50,760,000.

## 4. Status words
`component`, `component_instructions` (client "✓ You acknowledged"), `component_deliverable` (client Due · ✓ You uploaded · Overdue · Returned), `group_materiality_decision`.

## 5. Human-only actions
Sending instructions (10-second Undo; issues the grant), reviewing and returning deliverables, deciding group materiality and make reference (EP reserved): agent, system and support deny.
