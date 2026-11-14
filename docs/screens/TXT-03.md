# TXT-03 · Beneficiaries, K-1s & 65-day election · Calloway Family Trust

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/beneficiaries` (`?ov=release-k1s`, `?ov=ask-trustee`); `form=1041` and `tax.fiduciary_k1_release` |
| Template and host frame | T6: statement pane 878 + right column 488 (two cards); second small Segmented "Calculation · Beneficiaries & K-1s" |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXT-03 Beneficiaries- K-1s and 65-day election - Calloway Family Trust/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-07 · SPEC-656 · T-07-T01 (contract), T-07-T05 (stubs), T-07-T08 (seed), screen rows per T-07 §9 |
| Persona | Samuel Ito (Tax Manager) |
| Flags | `tax.fiduciary_k1_release` (with `tax.fiduciary_workpapers`) |
| Priority | P1 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards and 1 composed state. Composed states are fixture-only, report Tier C against the nearest artboard and are never locked.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Draft | Two packages "Draft K-1 · pre-release"; no final approval; Release K-1s… disabled with Lock and reason | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt03.a` |
| a2 | Ready to release | Final approval by Daniel Reyes; 8879-F Completed by Eleanor Calloway; confirm opens | Mon Sep 28, 2026 | Sep 28 | D · C report-only | planned · `txt03.a2` |
| b | Released | Discs olive ✓; "Released Sep 28", then Viewed (Nora); button Resend… | Tue Sep 29, 2026, 6:40 PM CT | Sep 29 6:40 PM | D · C report-only | planned · `txt03.b` |
| c | Election recorded for TY2026 | "Elected for TY2026 · 50,000 paid Feb 20, 2027" (DV-4) | Mon Mar 1, 2027, 9:24 AM CT (inferred) | Mar 1, 2027 | D · C report-only | planned · `txt03.c` |
| d | Ask the trustee | `?ov=ask-trustee`: O3 compose from the firm template + Send (DV-5, DV-15) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt03.d` |
| e | Empty | No signed computation: "Run the trust calculation to allocate DNI to beneficiaries." | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only | planned · `txt03.e` |
| a3 (composed) | Release relocked | 8879-F `superseded_by_change` after a drift past the Pub 1345 tolerance: step 2 reverts (DEC-85) | Mon Sep 28, 2026 | Sep 28 variant | D · C report-only vs a2 | planned · `txt03.a3` (fixture-only) |
| loading | — | skeleton per the template (T3 / T6 loading grammar) | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | The "Beneficiaries & K-1s" segment is hidden; 1041 packages release through TXP-12 (T-02) | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/TXT-03/scenarios.ts` (T-07 §5.3), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `txt03.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (T-07 §4.3; stubs in T-07-T05):

- `GET /v1/tax-returns/{id}/beneficiaries` (`beneficiary_allocation.read`)
- `POST /v1/tax-returns/{id}/k1-packages/prepare` (T-02 `k1_package.prepare`)
- `POST /v1/tax-returns/{id}/k1-packages/release` (T-02 `k1_package.release`; 409 `gate_unmet {final_approval, form_8879_f}`)
- `POST /v1/k1-packages/{pid}/resend` (T-02 `k1_package.resend`)
- `PUT /v1/client-entities/{eid}/sixty-five-day-elections/{tax_year}` (`fiduciary_election.record`)
- `POST /v1/tax-returns/{id}/trustee-questions` (`fiduciary_election.read` draft; C5 `request_item.send`)

Matrix actions from `permission-matrix/tax.yaml` (T-07-T03): every write is a person's (`agent: deny`); portal principals deny.

## Links

| From | To | Status |
|---|---|---|
| Beneficiary row | TXP-12 (1041 mode) + SHL-08 imported PDF | live (DV-14) |
| Release steps | SIG-02, POR-13 | live |
| Ask the trustee → Send | POR-04 question variant (C5) | live (DV-15) |
| K-1 preview | TAX-11 | planned (T-06) |
| Add to planning | TAX-15 | planned (T-08; hidden in production, DV-6) |
| Calculation segment | TXT-02 · Review › Trust Calculation | planned (T-07-T17) |

## Notes

K-1 status words are §3.3.1's: firm side "Draft K-1 · pre-release"; the portal shows "Not released yet". The disabled Release carries `aria-disabled="true"` and a visible reason. Nora and Theo each see only their own K-1 (INV-4).

## Deviations

- DV-4 c's fixture clock is Mon Mar 1, 2027 9:24 AM CT (after the Feb 20, 2027 payment).
- DV-5 the planning paragraph and trustee question are firm templates with code values; a person sends (DEC-79, ADR-111).
- DV-6 Add to planning is planned (T-08).
- DV-14 beneficiary row opens TXP-12 and the CCH PDF in SHL-08 until T-06.
- DV-15 Ask the trustee is POR-04's question variant through C5.

## Acceptance

SPEC-656's criteria for this screen; each becomes a test named "TXT-03 acceptance: <criterion>".
