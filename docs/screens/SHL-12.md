# SHL-12 Sign-off modal

Screen contract: the full contract (artboards, scenarios, endpoints, deviations) is P-04-T60's. This file holds the parity rows P-04-T58 measures; scenarios in `apps/web/src/fixtures/scenarios/SHL-12.ts`, gallery `/components/screens/SHL-12?st=<state>&frame=1`.

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, e | C (locked) | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | P-04 lock; axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| ap, c, d, f, g, h | C | not run (P-04-T58: the Playwright visual project runs at the S24 batch end) | report-only (ap is a′); axe and keyboard in `apps/web/e2e/screens/SHL-review.spec.ts` |
| host | D | not run | O3 sheet 500, top 52 (`e2e/visual/tier-d-review.spec.ts`) |

Gate: chapter 04 §9.3 keeps Tier C report-only, so the locks are listed and reported, not blocking (DEC-1970). Keyboard: Escape closes the topmost layer and focus returns to the opener.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| View changes; the checks' Open notes (Opens AUD-17 · review notes and sign-off matrix) | AUD-17, planned in the manifest; a `PlannedLink` until it has a builder | planned (P-04-T60) |
| The checks' Confirm independence (Opens ENG-05 · team roles (later)) | ENG-05, planned in the manifest; a `PlannedLink` | planned |
| The checks' Open issues (Opens TAX-06 · return issues) | TAX-06, planned in the manifest; a `PlannedLink` | planned (P-04-T60) |
