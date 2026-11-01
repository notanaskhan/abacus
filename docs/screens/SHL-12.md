# SHL-12 Sign-off modal

Screen contract: the full contract (artboards, scenarios, endpoints, deviations) is P-04-T60's. This file holds the parity rows P-04-T58 measures; scenarios in `apps/web/src/fixtures/scenarios/SHL-12.ts`, gallery `/components/screens/SHL-12?st=<state>&frame=1`.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, e | C (locked) | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | P-04 lock; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| ap, c, d, f, g, h | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only (ap is a′); axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| host | D | not run | O3 sheet 500, top 52 (`e2e/visual/tier-d-review.spec.ts`) |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.
