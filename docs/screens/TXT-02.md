# TXT-02 · Review › Trust Calculation · Calloway Family Trust

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/trust-calculation` (`?view=tree|character`, `?row=<node>`, `?version=<n>`, `?ov=signoff` SHL-12 L2, `?ov=viewer` custodial statement line lit; SHL-09 as a local O1 popover); `form=1041` |
| Template and host frame | T6 WorkbookLayout with the CalcTree grammar (F-06); tally strip 186–238; second small Segmented "Calculation · Beneficiaries & K-1s" |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXT-02 Review - Trust Calculation - Calloway Family Trust/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-07 · SPEC-656 · T-07-T01 (contract), T-07-T05 (stubs), T-07-T08 (seed), screen rows per T-07 §9 |
| Persona | Samuel Ito (Tax Manager, reviewer) |
| Flags | `tax.fiduciary_workpapers` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards and 1 composed state. Composed states are fixture-only, report Tier C against the nearest artboard and are never locked.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Default | Version 3 computed: full tree; Nora's "DNI allocated" full-bleed lavender; Σ K-1s = DEDUCTION tie | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `txt02.a` |
| a2 | Sign-off · SHL-12 | `?ov=signoff`, L2 (Reviewer) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt02.a2` |
| b | Collapsed overview | `interact: collapseAll()`: four top rows with totals | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `txt02.b` |
| c | By character | `?view=character`: Interest 100,000 · Ordinary dividends 300,000 · qualified 240,000 across Nora, Theo, Trust | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `txt02.c` |
| d | Changed | Theo Dec 15 80,000 → 100,000 after L2 on v3: Changed micro-pills, struck priors, banner "Theo's Dec 15 distribution edited · re-approval needed" + Re-approve… (DV-3) | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only (struck-value rendering) | planned · `txt02.d` |
| e | Signed off | L2 by SI on the current version: "✓ SI"; tally "Reviewed · SI" | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · **C locked** | planned · `txt02.e` |
| f1 (composed) | Waiting on interpretation | Interpretation not approved or reopened: tally dashes; EmptyState "Approve the instrument interpretation to compute DNI." | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only vs a | planned · `txt02.f1` (fixture-only) |
| loading | — | skeleton per the template (T3 / T6 loading grammar) | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | TAX-05's sub-row hides Trust Calculation; the route redirects to the return's default tab; no pane renders blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/TXT-02/scenarios.ts` (T-07 §5.3), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `txt02.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (T-07 §4.3; stubs in T-07-T05):

- `GET /v1/tax-returns/{id}/fiduciary-computation?view=tree|character&version=` (`fiduciary_computation.read`)
- `POST /v1/tax-returns/{id}/fiduciary-computation/recompute` (`fiduciary_computation.recompute`; 409 `interpretation_not_approved`)
- `GET /v1/tax-returns/{id}/fiduciary-computation.xlsx?version=` (`fiduciary_computation.export`)
- `GET|POST /v1/tax-returns/{id}/fai-lines`, `PATCH /v1/fai-lines/{lid}` (`fai_line.edit`)
- `GET|POST /v1/tax-returns/{id}/trust-expenses`, `PATCH /v1/trust-expenses/{xid}` (`fai_line.edit`)
- `GET|POST /v1/tax-returns/{id}/trust-distributions`, `PATCH /v1/trust-distributions/{did}` (`trust_distribution.edit`)
- `POST /v1/sign-offs` (C3, L2 on `fai_dni_computation`)

Matrix actions from `permission-matrix/tax.yaml` (T-07-T03): every write is a person's (`agent: deny`); portal principals deny.

## Links

| From | To | Status |
|---|---|---|
| Clause chip | TXT-01 `?clause=` | planned (T-07-T15) |
| Sign off / Re-approve | SHL-12 L2 | live |
| Row → statement line | SHL-08 | live |
| Figure → provenance | SHL-09 | live |
| Beneficiaries & K-1s | TXT-03 | planned (T-07-T25) |
| Open in Excel | XLSX download | planned (T-07-T16) |

## Notes

The browser never sums: every figure, share and tie comes from the read model. No dollar sign renders in the tree. "Open in Excel" is a deterministic XLSX (ADR-042).

## Deviations

- DV-2 the built tally pill reads "Ties"; the canonical word is "tie" (copy lint, T-07-T04).
- DV-3 the built Changed frame's banner and Re-approve… are adopted (DEC-84).
- DV-12 `fai_dni_computation` is L2 only (code computes, no L1).

## Acceptance

SPEC-656's criteria for this screen; each becomes a test named "TXT-02 acceptance: <criterion>".
