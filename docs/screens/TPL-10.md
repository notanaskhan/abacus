# TPL-10 · Document on well specimen · Ridgeline preparer memo (+ letter)

| Field | Value |
|---|---|
| Route and params | Gallery only: `/components/specimens/tpl-10?st=a…d&as=samuel-ito&clock=2026-09-14T09:24:00-05:00`. Production twin TXP-01 (T-05, 2028) |
| Template and host frame | T10 · `Wave 0 - Templates.dc.html#tpl10` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TPL-10 Document on well specimen - Ridgeline preparer memo/` (README.md, spec.md, spec-alt.md; no revision.md; the shorter spec is read, as the README says) · HANDOFF_VERSION 2026-10-21 sha256:9308819d |
| Epic and tasks | F-06 · F-06-T01; F-06-T02 seed (`ridgeline.ts`, `letters.ts`); F-06-T16 specimen; F-06-T17; F-06-T22 |
| Manifest status | planned |

Code: specimen `apps/web/src/gallery/specimens/TPL-10/` over `apps/web/src/fixtures/seed/tax/ridgeline.ts` (memo) and `letters.ts` (ENG-04 clauses). Copy keys: `TPL-10/copy.ts`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a · Awaiting reviewer | `samuel-ito` | E0 Mon Sep 14, 2026, 9:24 AM | E0 | `status: draft`, `adoptedBy` Olivia Brandt (Sep 10, 2026), markers [1]–[5] with typed locators | F-06-T16 |
| b · Drafting | `samuel-ito` | E0 | E0 | `status: drafting`, `variant: paper`: three skeleton paragraphs and "Accrued Agent is drafting the memo" | F-06-T16 |
| c · Approved | `samuel-ito` | E0 | E0 | `status: approved`, `approvedBy` Samuel Ito, Sep 14, 9:40 AM; the approval control reads "Approved", disabled | F-06-T16 |
| d · Letter · ENG-04 | `samuel-ito` | E0 | E0 | `variant: letter`, `structure.kind: clauses` with variables, Brightwater Hale letterhead, DRAFT watermark; template and clause blocks only (ADR P-25 off) | F-06-T16 |

## API
None from the kit (`DocumentVM`). Approve memo opens SHL-12 through `onApprove()`.

## Status
`generated_document`: `draft` (with the sub-line "Adopted by Olivia Brandt", not a status: Q6), `drafting`, `approved`; `return.in_review` "In review · Partner" in the structure pane.

## Copy
`TPL-10/copy.ts`, verbatim: sheet header "Partnership › General Information" · KV keys and values (Status, Partnership, EIN "••-•••0287", Principal activity, Accounting method, Tax year, Partners "5 (1 GP · 4 LP)", Allocation, Extension, Due, Engine return "2025P:Ridgeline:V2", Client, Engagement, Binder, Files, Preparer, Reviewer, Signer, Created) · "Preparer memo" · "Edit" · "Regenerate…" · "Approve memo…" (Q7 ellipsis) · memo headings (Facts, Structural events, Book-to-tax bridge, Depreciation, States and PTET, Distributions, Open items, Opportunities) · meta line "Drafted by Accrued Agent · adopted by Olivia Brandt, Sep 10, 2026 · Reviewer: Samuel Ito" · approved line "Approved by Samuel Ito · Sep 14, 9:40 AM" · letterhead "Brightwater Hale LLP", "311 West Brannock Street, Chicago, IL". The memo paragraphs are seed data (`ridgeline.ts`), not copy.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| KV "→" links | CLI-02, ENG-02, BND-02 live; FIL-01 planned (N-01) | mixed |
| Open items | TPL-09 c / TXP-10 | planned |
| Approve memo… | SHL-12 (P-04) | live container |
| Group B "Capital Accounts" sub-tab | TPL-06 | planned (gallery specimen) |

## Acceptance
- TPL-10 acceptance: 470 structure pane and a 600 paper on the well.
- TPL-10 acceptance: memo figures foot (1,231,600; 1,256,200; 733,500; state shares sum to 1,231,600).
- TPL-10 acceptance: the same numbers as TPL-06 (6,200, 331,405, 28,595 = 360,000 − 331,405) and TPL-03 (Feld 25%).
- TPL-10 acceptance: KV links in ink with an ink-3 "→"; empty values "—".
- TPL-10 acceptance: citation markers light purple only on hover or focus.

## Figures
3,776,500 + 96,400 − 2,641,300 = 1,231,600; + 18,400 + 6,200 = 1,256,200; 480,000 + 9,500 + 180,000 + 64,000 = 733,500; 566,536 + 387,954 + 277,110 = 1,231,600; 360,000 − 331,405 = 28,595. Proven by `tax.foot.test.ts` (F-06-T02).

## AVOID
Gradients, emoji, saturated blue links, heavy shadows, invented colours, lorem ipsum, serif headings in chrome, numbers that disagree with the Financials and Capital Accounts specimens.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| a | "Adopted by Olivia Brandt" is a sub-line; the pill stays Draft | DF-31 has no Adopted status | F-06 §11.2 Q6, DECISIONS.md |
| a | "Approve memo…" and "Regenerate…" carry ellipses | they open a dialog (ellipsis rule) | F-06 §11.2 Q7, DECISIONS.md |
| a | Group A "Issues 11" is the seed's derived count at E0 | G-C02 | DEC-801 |
| d | No agent prose in the letter | ADR P-25 off | ADR-111, DEC-79 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–d | B (locked) · A paper header (reported, kit chrome deviation) · D (`tier-d-document.spec.ts`) | not run | spinner masked; locked at Tier B in F-06-T22 (DEC-1754); first visual run at the S22 end review |

## Open gaps
- spec-alt.md is not read (the README names the shorter spec as the source).
