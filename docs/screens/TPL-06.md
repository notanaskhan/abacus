# TPL-06 · Workbook grid specimen · Ridgeline capital accounts

| Field | Value |
|---|---|
| Route and params | Gallery only: `/components/specimens/tpl-06?st=a…e&as=samuel-ito&clock=2026-09-14T09:24:00-05:00`. Production twin TXP-07 (T-05, 2028) |
| Template and host frame | T6 · `Wave 0 - Templates.dc.html#tpl06` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-06 Workbook grid specimen - Ridgeline capital accounts/` (README.md, spec.md; no revision.md) · HANDOFF_VERSION 2026-10-21 sha256:9308819d |
| Epic and tasks | F-06 · F-06-T01; F-06-T02 seed (`ridgeline.ts`); F-06-T18 to T20; F-06-T21; F-06-T22 |
| Manifest status | planned (gallery: `/components/screens/TPL-06?st=a…e`, F-06-T20) |

Code: specimen `apps/web/src/gallery/specimens/TPL-06/` over `apps/web/src/fixtures/seed/tax/ridgeline.ts`. Copy keys: `TPL-06/copy.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a · As drafted | `samuel-ito` | E0 Mon Sep 14, 2026, 9:24 AM | E0 | rollforward as drafted, Ending 6,860,000; M-2 tally `off 6,200`; tie-out difference (6,200) | built (F-06-T20 on the F-06-T18 kit) |
| b · Fixed | `samuel-ito` | E0 | E0 | after the reviewer accepts the agent's fix (P-04's flow): tax-exempt column 124 · 2,356 · 2,015 · 155 · 1,550 = 6,200; Ending 6,866,200; M-2 `tie` | built (F-06-T20 on the F-06-T18 kit) |
| c · By partner | `samuel-ito` | E0 | E0 | `view: by_partner`: five 452 panes, Tax beside Book | built (F-06-T20 on the F-06-T18 kit) |
| d · Building | `samuel-ito` | E0 | E0 | `building`: Pending pills, skeleton rows, "Workbook agent is running" | built (F-06-T20 on the F-06-T18 kit) |
| e · Signed off | `samuel-ito` | E0 | E0 | sign-off slot "✓ SI"; pill "Reviewed · SI" | built (F-06-T20) |

## API
None from the kit (`WorkbookVM`). Every total, tie and difference is a server value in the fixture.

## Status
`return.in_review` ("In review · Partner"), `return_sync_chip.not_yet_exported`, `tie_out_tally`, sign-off slot (F-06-T03).

## Copy
`TPL-06/copy.ts`: "Capital Accounts" · "By partner", "By movement" · "Open in Excel" · "Sign off…" · pane title "Partners' capital — tax basis (books kept on the income-tax basis)" · columns · tally labels ("Capital foots", "M-2 ties", "Book ties", "Item L derives", "Begin total", "Contributions", "CY income", "Transfers", "Distributions", "End total") · "Tie-out to Schedule L" rows · the tax-exempt link sentence · the transfers footnote · "Workbook agent is running" · "Reviewed · SI".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "off 6,200", Issues | TXP-10 issue (TPL-09 c) | planned |
| any number | SHL-09 provenance (P-04) | planned |
| Sign off… | SHL-12 (P-04) | live container |
| Group B "Summary" sub-tab | TPL-10 | planned (gallery specimen) |

## Acceptance
- TPL-06 acceptance: tally strip with 9.5 px uppercase labels and 17 px tie/off pills.
- TPL-06 acceptance: every row crossfoots and every column foots; transfers net to 0 (331,405 = 2,319,835 × 5/35).
- TPL-06 acceptance: the only amber element is "off 6,200" and the tie-out explains it (6,866,200 − 6,860,000).
- TPL-06 acceptance: fixed state sums the tax-exempt column to 6,200 and Ending to 6,866,200; M-2 ties.
- TPL-06 acceptance: negatives red in parentheses, zeros "—", no "$".
- TPL-06 acceptance: both tab groups fit one 50 px row at 1400.

## Figures
5,960,000 + 250,000 + 1,250,000 − 600,000 = 6,860,000; + 6,200 = 6,866,200; 124 + 2,356 + 2,015 + 155 + 1,550 = 6,200; 331,405 = 2,319,835 × 5/35; 2,100,000 + 218,750 + 1,085 = 2,319,835; transfers net 0. Proven by `tax.foot.test.ts` (F-06-T02).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, "$" in the statement table, zebra rows, numbers that do not foot.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| tabsbar | Group A "Issues 11" is the seed's derived open-issue count at E0 | G-C02: the count follows the seed; an artboard value that differs is a masked region | DEC-801, DECISIONS.md |
| sign-off | "Sign off…" and the "✓ SI" chip sit in the control bar, not the pane header | the T6 kit's one sign-off placement (F-06-T18); TPL-06 renders on the kit | DEC-1557 |
| ⓘ | the value cards carry no ⓘ text | the handoff's ⓘ opens SHL-09 provenance (planned); no words are designed for it | DEC-1557 |
| tie-out link | "Tax-exempt interest … not in the rollforward →" is a row label, not yet a link | TXP-10 is planned; the row keeps the words | DEC-1557 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–e | B · A strips · D | not run | Issues count region masked; spinners masked; locked in F-06-T22 |

## Open gaps
- None beyond the masked Issues count.
