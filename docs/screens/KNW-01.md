# KNW-01 · Knowledge library

| Field | Value |
|---|---|
| Route and params | `/knowledge` (Knowledge); `?category=`, `?tab=review\|changes`, `?q=` |
| Template and host frame | Catalog layout (category list, catalog grid, About card) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-01 …/` (README.md, spec.md) |
| Epic and tasks | K-01 · API K-01-T03 · screen K-01-T04 · journey K-01-T11 · parity K-01-T17 · docs K-01-T26 |
| Manifest status | fixture at `/knowledge`, behind `knowledge.catalog` |

One catalog over a provider slot: a later epic adds its category with
`register_catalog_provider` and touches nothing here (the module README says how). Rows come from
the providers through `visible()`; the agent proposes nothing on this screen.

## States
| Artboard | Viewer (persona) | Clock | Data condition |
|---|---|---|---|
| a | margaret-okonkwo | Mon Sep 14, 2026, 9:24 AM | All · Library |
| b | margaret-okonkwo | 9:24 AM | the Methodology category |
| c | margaret-okonkwo | 9:24 AM | the Review queue |
| d | margaret-okonkwo | 9:24 AM | the Change log |
| e | ana-cruz | 9:24 AM | Audit Staff: drafts left out by the API and no + menu |
| f | margaret-okonkwo | 9:24 AM | search "materiality" |

## Journeys
`apps/web/e2e/journeys/knw-01-catalog.spec.ts`, and J01 step 5w (K-01-T11), fixture-first.

## Parity
Locked with KNW-03 by K-01-T17 (TASK-2615). The current tier and diff are in the visual report.

## Deviations
- **g and h** (the Oct 1 counts and the engagement templates) are K-03's and later providers'; they
  are not built here.

## Open gaps
Manifest stays `fixture` until the screen is walked on staging (DEC-195).
