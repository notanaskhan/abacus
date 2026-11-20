# KNW-03 · Program editor

| Field | Value |
|---|---|
| Route and params | `/knowledge/programs/$programId`; `?step=`, `?from=citation`, segment `steps\|changes`, `tailoredFor=` |
| Template and host frame | Program editor over the methodology version workbook |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/KNW-03 …/` (README.md, spec.md) |
| Epic and tasks | K-01 · read API K-01-T12 · a, b, e K-01-T13 · c, d, f K-01-T15 · journey and parity K-01-T17 · docs K-01-T26 |
| Manifest status | planned with path `/knowledge/programs/$programId` (fixture-built; live once walked on staging, DEC-195) |

Programs and steps carry stable, version-pinned anchors, so a workpaper citation (SHL-07) lands on
the exact step. Only the QM owner changes a mandatory lock. The agent decides nothing here.

## States
| Artboard | Viewer (persona) | Clock | Data condition |
|---|---|---|---|
| a | margaret-okonkwo | Mon Sep 14, 2026, 2:30 PM | arrived from an AUD-04 citation: `?step=4&from=citation`, step 4 lit |
| b | margaret-okonkwo | 2:30 PM | a with the SHL-07 popover open on step 4 |
| c | hannah-leclerc | 2:30 PM | editing her draft v4 |
| d | margaret-okonkwo | 2:30 PM | BH-EBP-110 tailored on the Northwind engagement (A-04's tailoring, in fixture mode) |
| e | margaret-okonkwo | 2:30 PM | the Change log segment: v2 → v3 for BH-EBP-110 (7, 9, 10 changed; 15 new) |
| f | hannah-leclerc | 2:30 PM | Fix in Knowledge from the 9:58 AM Internal Control run: BH-EBP-140, step 8 lit, the run's error quoted |

## Journeys
`apps/web/e2e/journeys/knw-03-program-editor.spec.ts`, and J01 step 6 (K-01-T17), fixture-first.

## Parity
Locked with KNW-01 by K-01-T17 (TASK-2615). The current tier and diff are in the visual report.

## Deviations
- **g** arrives with K-03 and K-05; it is not built here.

## Open gaps
Manifest stays `planned` until the screen is walked on staging (DEC-195).

## K-03 artboard g (K-03-T04, TASK-8803; DEC-5810)
| Letter | Artboard | Persona | Clock (CT) | Figures | Build | Owner |
|---|---|---|---|---|---|---|
| g | Rules & skills · FS v6 | Margaret Okonkwo | Thu Oct 1, 10:00 AM | Rules column from SHT-03 (rules 1–3 and 6 act on steps, DF-34); skill cells read the BH-SK-430 v1 pin | planned (rules half K-03; skill-v2 half K-05-T32) | AY |

Rules segment opens SHT-03 read-only (SPEC-720 AC-15). K-05 is the parity owner of the full
artboard.
