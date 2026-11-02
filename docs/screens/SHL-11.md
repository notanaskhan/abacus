# SHL-11 · Decision card

| Field | Value |
|---|---|
| Route and params | Overlay `?ov=decision:<cardId>` (O3 sheet) over any firm route; the inline variant (e) mounts in a host's dock (AUD-07, NOT-02). Artboards: `/components/screens/SHL-11?st=a..h&frame=1` |
| Template and host frame | O3 sheet modal 500, top 52; inline card 330 (e) · `Wave 0 - Shell.dc.html#shl11` |
| Surface | firm (never a client surface) |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-11 Decision card/` (README.md, spec.md; no revision.md) |
| Epic and tasks | P-04 · decision cards P-04-T23 · sheet P-04-T50 · independent AC tests P-04-T28 · parity P-04-T58 · this contract P-04-T60 |
| Manifest status | fixture (`routes/manifest/shl.ts`) until the staging walk; live where its host screen is |

Code: `src/screens/SHL-11/{index.tsx, InlineCard.tsx, copy.ts, scenarios.ts, SHL-11.test.tsx, InlineCard.test.tsx}`, `src/fixtures/scenarios/SHL-11.ts`.

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | margaret-okonkwo | Mon Sep 14, 2026, 10:01 AM CT | A card awaiting its reserved person; options computed by code; "Recommended by Accrued Agent" on one option; Decide disabled until a rationale exists | fixture |
| b | hannah-leclerc | 10:01 AM | The viewer is not the reserved role: radios disabled, the "Only the … can decide" banner, Remind only | fixture |
| c | margaret-okonkwo | 10:01 AM | Decided: the card collapses to "✓ Decided by … · {when}" | fixture |
| d | margaret-okonkwo | Tue Oct 6, 2026 | History with a reassessment row | fixture |
| e | margaret-okonkwo | 10:01 AM | The inline dock variant (330) | fixture |
| f | margaret-okonkwo | 10:01 AM | Deficiency severity (A-06 `deficiency_severity`) | fixture |
| g | margaret-okonkwo | 10:01 AM | §754 recommendation (T-04) | fixture |
| h | margaret-okonkwo | 10:01 AM | Superseded by a newer card | fixture |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons |
|---|---|---|---|---|
| read | `GET /v1/decision-cards/{id}` | the card, its computed options, context, factors, history | `decision.read` | `decision.decide` only for the reserved person |
| write | `POST /v1/decision-cards/{id}/decide` (fresh MFA; rationale) | the decision | `decision.decide` | 403 for anyone else and the agent; 422 `rationale_required` |
| write | `POST /v1/decision-cards/{id}/notify` | — | `decision.notify` | the team, never the agent |
| write | `POST /v1/decision-cards/{id}/reassess` | the reassessment | `decision.reassess` | the kind's reassessor |
| write | `POST /v1/decision-cards/{id}/analysis-requests` | an analysis request | `decision.request_analysis` | the team |

## Copy
Verbatim from spec.md through `src/screens/SHL-11/copy.ts` (the copy registry): "Reserved to {role}", "Recommended by Accrued Agent", "Rationale (required for the file)", "Decide", "Remind {name}", "Request more analysis…", "✓ Decided by {name} · {when}". Agent reasons render only through `AgentText`.

## Links
| From | To | Planned or live |
|---|---|---|
| Option context chips | SHL-07 citation popover | live |
| Request more analysis… | the host's dock composer | planned (P-09); records an analysis request through C3 today |
| Inbound | AUD-07, AUD-08, NOT-02, HOME-02, AUD-15, TAX-* | per the manifest |
| A cited figure (Opens SHL-08 with the cited figure lit) | SHL-08, planned in the manifest (no builder yet) | planned (P-04-T60) |

## Deviations
1. Artboards a, c, d, e, f, g and h have no letter in the spec's STATES list; the build's letters are the parity keys.
2. Fixture dates follow DF-13: every artboard renders at its README clock, not the demo day, so d stays Oct 6.
3. The kind's provider computes every option and figure (ADR-050); the card never takes options from a caller (A-04-T12, DEC-1950).
4. The agent's recommendation is a tag on one option, never a pre-selection that decides (INV-1).

## Build notes (the build-screen skill)
Start from `scenarios.ts` (one per artboard), mount through `installFixtureMode`, keep the reserved-person check on the server's `allowed_actions`, never a client role check.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, c | C (locked) | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | P-04 lock; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts`; radio group arrows |
| b, d, e, f, g, h | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only (e is the 330 inline card); axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| host | D | not run | O3 sheet 500, top 52 (`e2e/visual/tier-d-review.spec.ts`) |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.
