# AUD-31 · Trial balance import and mapping

| Field | Value |
|---|---|
| Route and params | `/group/mapping` for single-entity engagements too (DV-B3; QA-8), reached through the manifest link `to.AUD-31()`; behind `ledger.tb_mapping`. Artboards: `/components/screens/AUD-31?st=f`, composed `a2…e2` (a′–e′), plus `off`, `loading`, `error`, `not_allowed` |
| Template and host frame | T3 two-pane in the Focus layout; new L2 `MappingTable` kit (A-03-T12; `packages/ui/src/data/mapping-table.tsx`, specimen `l2-mapping-table`) · `kits/AUD31 Mapping.dc.html` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-31 Trial balance mapping - Harlow and Pike interim 8312026/` (README.md, spec.md) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | A-03 · C9 v2 contract A-03-T03 (`docs/contracts/ledger-mapping.md`); taxonomy A-03-T06; rules and confirm A-03-T08; screen A-03-T12; staleness A-03-T14; parity A-03-T19. The live SPEC-316 slice (`legacy/TbMapping.tsx`) stays until T12 |
| Manifest status | fixture (`routes/manifest/aud.ts`; A-03-T12); live with `ledger.tb_mapping` per firm once A-03-T16 loads the content |

## States
| Artboard | Viewer (persona) | Clock | Data condition | Status |
|---|---|---|---|---|
| f | caleb-dunn | Mon Sep 14, 2026, 11:40 AM | Granite Peak FY2026, single entity: 128 accounts mapped by rule (prior year · High, number range · Medium) and confirmed | built at parity (A-03-T12) |
| a′ | caleb-dunn | 11:40 AM | Needs review without suggestions (no TB mapper) | composed (A-03-T12) |
| b′ | caleb-dunn | 10:50 AM | Rules running: ring polling `GET /v1/mapping-sets/{id}/run` | composed |
| c′ | caleb-dunn | 11:40 AM | Change made: "Edited by CD · was …", Confidence "—" | composed |
| d′ | caleb-dunn | 11:58 AM | Confirmed: "Mapping confirmed by Caleb Dunn · …", rail "Prepared · CD" | composed |
| e′ | caleb-dunn | 11:40 AM | Changed after sign-off: amber banner and chip after TB version 2 | composed (A-03-T12 draws it; A-03-T14 makes it live) |
| a–e (five entities) | caleb-dunn | — | Harlow & Pike group | recorded for A-09 |

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/engagements/{eid}/mapping-sets` | mapping sets per TB of record | `mapping_set.read` |
| read | `GET /v1/mapping-sets/{msid}?filter=&group_by=fs_line` | rows, tallies, subtotals, `content_hash`, `allowed_actions` | `mapping_set.read` |
| read | `GET /v1/mapping-sets/{msid}/run` | run progress | `mapping_set.read` |
| read | `GET /v1/grouping-sets` · `…/versions/{v}/lines?q=` | catalogue and the Change picker with Recently used | `grouping_set.read` |
| write | `POST /v1/engagements/{eid}/mapping-sets` | start or re-run | `mapping_set.run` |
| write | `PUT /v1/account-mappings/{id}` | `{fs_line_id, seen_version}` | `account_mapping.edit` |
| write | `POST /v1/mapping-sets/{msid}/confirm` | `{seen_hash}` → L1 | `mapping_set.confirm` |

## Deviations
| ID | State | Deviation | Reason |
|---|---|---|---|
| DV-B1 | f | The run line names the code run and carries no atom | INV-5 |
| DV-B2 | a′–e′ | Single-entity compositions; no "Accept", no "Request changes…", no reasoning line | No suggestions without the TB mapper (A-09) |
| DV-B3 | all | Route stays `/group/mapping` for single-entity engagements; `to.AUD-31()` hides the path | Chapter 04 route tree; QA-8 |
| DV-B4 | f, a′–e′ | Fixture rows are Granite Peak's 14 TB lines (blueprint §9.8), one FS line per grouping named as the line; the tallies stay the server's 128 | The 128 accounts and BH FS groupings v1's lines are content A-03-T16 loads (DEC-1555); nothing is invented (DEC-1753) |
| DV-B5 | f | The source-file pane shows the selected account's row of the read-only ledger snapshot, lit in the match purple, not the NetSuite file in the viewer | No TB file evidence in fixtures until A-03-T16; the C9 v2 row carries the snapshot's match id (DEC-1753) |
| DV-B6 | all | AUD-06's grouping › FS line reads the confirmed set's `group_by=fs_line` rows and subtotals on the client side of C9 v2; A-02's view has no `group_by` | No browser sums: the groups carry the mapping's subtotals (DEC-1753) |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Agent run line | SHL-13 dock | planned (A-09; no run in A-03, DV-B1) |
| Consolidated view | AUD-33 | planned (A-09) |
