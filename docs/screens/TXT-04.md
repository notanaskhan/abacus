# TXT-04 · Gift & estate workpapers (706 / 709) · Estate of Walter Thornbury

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/estate` (`?sub=inventory|deductions|computation|gifts`; `?ov=signoff` L4, `?ov=request` SHL-14; derivation popovers are local O1 state); `form=706` and `tax.estate_workpapers` |
| Template and host frame | T6 in the return frame: sub-tabs Inventory · Deductions · Computation · Gifts (709); due-date chip; tally strip; statement tables |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXT-04 Gift and estate workpapers -706 709-/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-07 · SPEC-656 · T-07-T01 (contract), T-07-T05 (stubs), T-07-T08 (seed), screen rows per T-07 §9 |
| Persona | Samuel Ito (Tax Manager); Daniel Reyes (signing partner) on c1 |
| Flags | `tax.estate_workpapers` |
| Priority | P2 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

6 artboards and 1 composed state. Composed states are fixture-only, report Tier C against the nearest artboard and are never locked.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Inventory | Six schedules foot 16,400,000 DOD; AVD 15,993,000; basis to 1041 12,688,000; D and F Gathering | Mon Oct 19, 2026, 9:24 AM CT (DV-10) | Oct 19 | D · C report-only | planned · `txt04.a` |
| b | Deductions | J funeral 28,500 · J administration 240,000 (§642(g) pending) · K 131,500 · O 500,000 = 900,000 | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 | D · C report-only | planned · `txt04.b` |
| c | Computation | Tentative tax 6,625,800; BEA 15,000,000 + DSUE 3,000,000; credit 7,145,800; net tax —; Without DSUE 680,000; Illinois Pending; filing banner; "Accrued tie-out (shadow)" (DV-7) | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 | D · C report-only | planned · `txt04.c` |
| d | Gifts (709) | 2023 taxable gift 1,200,000 filed Apr 15, 2024; 2024–2026 within the annual exclusion; tie to Computation | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 | D · C report-only | planned · `txt04.d` |
| e | Extended | Form 4768 recorded (T-03 extensions): "Extended to May 3, 2027"; state stays Gathering | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 variant | D · C report-only | planned · `txt04.e` |
| f | Derivation · applicable exclusion | `interact: openDerivation('applicable_exclusion')`: rows + note + "Provenance ›" (DV-18) | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 | D · C report-only | planned · `txt04.f` |
| c1 (composed) | Approve values | `?sub=computation&ov=signoff`, L4 (engagement partner, DF-08, DV-8) | Mon Oct 19, 2026, 9:24 AM CT | Oct 19 | D · C report-only vs c | planned · `txt04.c1` (fixture-only) |
| loading | — | skeleton per the template (T3 / T6 loading grammar) | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | The 706 Review sub-row is hidden; TAX-02's overview only | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/TXT-04/scenarios.ts` (T-07 §5.3), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `txt04.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (T-07 §4.3; stubs in T-07-T05):

- `GET /v1/tax-returns/{id}/estate/{inventory|deductions|computation|gifts}` (`estate_workpaper.read`)
- `POST /v1/tax-returns/{id}/estate/assets`, `PATCH /v1/estate-assets/{aid}` (`estate_workpaper.edit`)
- `POST /v1/tax-returns/{id}/estate/deductions`, `PATCH /v1/estate-deductions/{did}` (`estate_workpaper.edit`)
- `POST /v1/client-entities/{eid}/gift-history`, `PATCH /v1/gift-history-items/{gid}` (`estate_workpaper.edit`)
- `GET /v1/tax-returns/{id}/estate/derivations/{tile}` (`estate_workpaper.read`)
- `POST /v1/sign-offs` (C3, L4 on `estate_workpaper`)
- `GET /v1/due-dates?…` (K-02)

Matrix actions from `permission-matrix/tax.yaml` (T-07-T03): every write is a person's (`agent: deny`); portal principals deny.

## Links

| From | To | Status |
|---|---|---|
| Gathering row | TAX-03 intake | live |
| Request appraisal… | SHL-14 prefilled for Paul Thornbury | live (DV-17) |
| Derivation → Provenance › | SHL-09 | live |
| 2023 Form 709 | FIL-01 | live |
| Approve values… | SHL-12 L4 | live (DV-8) |
| Extension | TAX-13 | live |

## Notes

The Illinois Form 700 card never shows a figure (spec AVOID; OQ-10). Basis-to-1041 is null for IRD and non-probate life insurance by rule. Thornbury's §7216 consent is "not requested": no agent runs on the estate.

## Deviations

- DV-2 "tie", never "Ties".
- DV-7 "Accrued tie-out (shadow)" on c until a CCH 706 import exists (DEC-77).
- DV-8 c1 Approve values is composed (L4 partner).
- DV-9 asset statuses use the new `estate_inventory_item` row (`valued`, `gathering_support`; words unchanged).
- DV-10 the fixture snapshot is Mon Oct 19, 2026 9:24 AM CT.
- DV-17 Request appraisal is SHL-14 prefilled from the firm's request template; a person sends.
- DV-18 f was added in build.

## Acceptance

SPEC-656's criteria for this screen; each becomes a test named "TXT-04 acceptance: <criterion>".
