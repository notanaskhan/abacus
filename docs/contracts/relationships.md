# Relationships v1 — the CLI-03 map

| Field | Value |
|---|---|
| Owner | organisations (T-06; SPEC-702 F8, §4; DEC-62) |
| Status | stub (T-06-T08, 2026-11-17; DEC-5517) |
| Code | `backend/src/abacus/modules/organisations/relationships_contract.py` (`relationships_router`) |
| Flag | `clients.relationship_map` (default off; off: 404 and CLI-03 shows P-07's list; on: 501 until T-06-T21) |
| Fixtures | `backend/src/abacus_tools/synthetic/scenarios/brightwater_hale/relationships_slice.py` (TPL-14 a–f; a walled view) |
| Consumer tests | `backend/tests/contracts/t06_entity_depth/` and the TS fixture (T-06-T09) |

P-07's `GET /v1/clients/{id}/relationships` (live, `client.read`) is unchanged; the graph is its own read.

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/clients/{id}/relationship-graph` | `client.read` | nodes, edges, banner (the annotation slot), the viewer's positions |
| `POST /v1/clients/{id}/relationships` | `relationship.create` | 201; 422 `relationship_self_edge`, `relationship_percent_exceeds` |
| `PATCH /v1/relationships/{id}` | `relationship.update` | `expected_version` |
| `POST /v1/relationships/{id}/end` | `relationship.end` | ended, never deleted; reason required |
| `POST /v1/clients/{id}/external-parties` | `relationship.create` | "Not a Brightwater Hale client" |
| `PUT /v1/users/me/graph-layouts/{client_id}` | `graph_layout.save` | own rows; never audited |

**Walls:** a walled client's node is absent with no placeholder and no count (DEC-43); a K-1 edge between two clients needs read on both engagements (DEC-88). **Never in the portal** (INV-4). **Example:** 2 + 38 + 30 + 5 + 25 = 100% into Ridgeline at year end; Pell Street Ventures 35% through 6/30/2025.
