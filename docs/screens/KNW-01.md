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

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Methodology row, Used by | ENG-01, filtered by this methodology | planned |
| Program row | KNW-03, the program editor | planned |
| Checklist row | TAX-14, with this checklist | planned |
| Firm standards and thresholds | KNW-04 | planned |
| Templates and research | KNW-05 | planned |
| My Agents | WB-06 | planned |
| Edit Agent sheet (read-only unless you own it) | WB-07 | planned |
| Versions and rollout | KNW-07 | planned |
| Engagement template builder | KNW-06 | planned |

## Journeys
`apps/web/e2e/journeys/knw-01-catalog.spec.ts`, and J01 step 5w (K-01-T11), fixture-first.

## Parity
Locked with KNW-03 by K-01-T17 (TASK-2615). The current tier and diff are in the visual report.

## Deviations
- **g and h** (the Oct 1 counts and the engagement templates) are K-03's (artboard-level carry,
  DEC-5810): K-03 registers the Engagement templates catalogue provider and counter and is their
  parity owner (lock in K-03-T59).

## K-03 artboards (K-03-T04, TASK-8803)
| Letter | Artboard | Persona | Clock (CT) | Figures | Build | Owner |
|---|---|---|---|---|---|---|
| g | Counts · Thu Oct 1, 11:30 AM | Margaret Okonkwo | Thu Oct 1, 11:30 AM (README header: Mon 14 Sep 9:24 AM is the canvas render clock; the artboard title wins) | 107 items; FS v6 published | planned | AY |
| h | Engagement templates category | Margaret Okonkwo | Thu Oct 1, 11:30 AM | BH Audit Methodology · FS v6 live, FS v5 Deprecated for new work | planned | AY |

## Open gaps
Manifest stays `fixture` until the screen is walked on staging (DEC-195).
