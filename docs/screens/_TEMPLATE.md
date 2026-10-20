<!-- Copy to docs/screens/<ID>.md (for example AUD-03.md). One screen contract per screen ID.
     Built with the build-screen-from-handoff skill. revision.md wins over spec.md for what it lists. -->

# <ID> · <screen name>

| Field | Value |
|---|---|
| Route and params | `/…` |
| Template and host frame | T? · <canvas> |
| Surface | firm · portal |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/<ID> <name>/` · HANDOFF_VERSION <sha> |
| Epic and tasks | <epic> · <task ids> |
| Manifest status | planned · fixture · live |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | | | | | built · fixture · deferred |

Loading, empty, error and not-allowed are listed too. A state is a data condition, never an `st` prop.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|

## Status
Status objects and codes shown, from `docs/product/status-vocabulary.yaml`.

## Copy
Every string verbatim from the handoff (copy keys in `copy.ts`).

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|

## Acceptance
One bullet per revision.md acceptance item; each becomes a test named "<ID> acceptance: <bullet>".

## Figures
Numbers that must foot, with the seed test that proves each.

## AVOID
From spec.md and revision.md.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|

## Open gaps
Contradictions between sources and how each was decided.
