# TXT-01 · Review › Instrument · Calloway Family Trust 2025 Form 1041

| Field | Value |
|---|---|
| Route and params | `/tax-returns/$returnId/review/instrument` (`?clause=<label>` lights a clause; `?determination=<key>` selects a row; `?ov=signoff` SHL-12 L3, `?ov=approve:<suggestionId>` SHL-10, `?ov=viewer` SHL-08 page image); `beforeLoad` requires `form=1041` and `tax.fiduciary_workpapers`, else redirects to the return's default tab |
| Template and host frame | T3 EvidenceTriad, two-pane mirrored preset (reader flex 876 · profile 490); TAX-05 Review sub-row item "Instrument" (T-04 frame) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/TXT-01 Review - Instrument - Calloway Family Trust 2025 Form 1041/` (no `revision.md`; the README's artboard table gives the letters) |
| Epic and tasks | T-07 · SPEC-656 · T-07-T01 (contract), T-07-T05 (stubs), T-07-T08 (seed), screen rows per T-07 §9 |
| Persona | Samuel Ito (Tax Manager) on a–c; Kevin Osei (Tax Preparer) on d1–d3 |
| Flags | `tax.fiduciary_workpapers` |
| Priority | P0 |
| Manifest status | planned |
| Owner | ayushkbhatia |

## States

7 artboards and 3 composed states. Composed states are fixture-only, report Tier C against the nearest artboard and are never locked.

| Artboard | State | Data condition that produces it | Demo clock | Snapshot | Parity tier | Status · scenario key |
|---|---|---|---|---|---|---|
| a | Proposed | Interpretation Proposed (run Sep 3; L1 adopted by Kevin Osei Sep 4); 7 determinations, 6 clause chips; Trust type lit with III(a) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D (blocking) · **C locked** | planned · `txt01.a` |
| a2 | Clause hover | `interact: hoverChip('IV(a)')`: reader scrolls to and lights Art. IV(a) 360 ms (spec state E, DV-1) | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt01.a2` |
| a3 | Passage selected | `interact: clickPassage('Art. II')`: popover lists "Fiduciary accounting income" | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt01.a3` |
| a4 | Sign-off · SHL-12 | `?ov=signoff`, level L3 (Manager), content hash | Mon Sep 14, 2026, 9:24 AM CT | E0 | D · C report-only | planned · `txt01.a4` |
| b | Approved | L3 by Samuel Ito Sep 14; determinations locked; header "Approved · Samuel Ito · Sep 14"; button Approved (disabled) | Mon Sep 14, 2026, 9:24 AM CT | E0 after approval | D · **C locked** | planned · `txt01.b` |
| c | Scenario · principal invaded | Theo 25,000 `source=principal` under IV(b): amber banner; Nora 160,000 · Theo 105,000 · trust retains 135,000 | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only | planned · `txt01.c` |
| d | Unread | Instrument attached, no interpretation: no highlights; EmptyState "Instrument not read yet" + Read instrument | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · **C locked** | planned · `txt01.d` |
| d1 (composed) | Agents off | Reader off or at stage shadow, or consent declined: rows show Record… and require a clause; Read instrument not offered (DV-16) | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only vs d (never locked) | planned · `txt01.d1` (fixture-only) |
| d2 (composed) | Reading | Run in progress: "Checking citation 4 of 6" over C6 v2 SSE, polling fallback | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only vs d | planned · `txt01.d2` (fixture-only) |
| d3 (composed) | Consent required | Reader refused 409 `consent_required`: "§7216 AI consent — Calloway Family Trust (1 of 2 signed)" | Mon Sep 14, 2026, 9:24 AM CT | E0 variant | D · C report-only vs d | planned · `txt01.d3` (fixture-only) |
| loading | — | skeleton per the template (T3 / T6 loading grammar) | — | — | D | planned |
| error | — | the read failed: designed error with Retry (chapter 10 §10.3 kind 10) | — | — | D | planned |
| not allowed | — | walled or out of scope: 404, no counts (INV-3) | — | — | — | planned |
| flag off | — | TAX-05's sub-row hides Instrument; the 1041 review proceeds on TAX-05 worksheets (T-04). The route redirects; no pane renders blank | — | — | — | planned |

Fixture scenarios live in `apps/web/src/screens/TXT-01/scenarios.ts` (T-07 §5.3), exported from the Python scenario (`make fixtures`, F-04-T31) and derived from the seed's footing figures, never typed by hand. Copy keys are `txt01.<state>.<element>` in the screen's `copy.ts`.

## API

Every state reads this endpoint set (T-07 §4.3; stubs in T-07-T05):

- `GET /v1/tax-returns/{id}/instrument` (`instrument.read`)
- `POST /v1/tax-returns/{id}/instrument` (`instrument.attach`)
- `GET|POST /v1/governing-instruments/{iid}/clauses` (`instrument.read` / `instrument.attach`)
- `POST /v1/tax-returns/{id}/instrument/read` (`instrument.read_run`; 202, 409 `consent_required` · `capability_unavailable` · `not_segmented`)
- `POST /v1/tax-returns/{id}/instrument/determinations`, `PATCH /v1/instrument-determinations/{did}` (`instrument_determination.edit`; 422 `uncited_change`, 409 `version_conflict` · `locked`)
- `POST /v1/instrument-interpretations/{iid}/reopen` (`instrument_interpretation.reopen`)
- `GET /v1/tax-returns/{id}/instrument/cited-by` (`instrument.read`)
- `POST /v1/sign-offs` (C3, L1 and L3 on `instrument_interpretation`)

Matrix actions from `permission-matrix/tax.yaml` (T-07-T03): every write is a person's (`agent: deny`); portal principals deny.

## Links

| From | To | Status |
|---|---|---|
| Clause chip / passage | LegalReader (in-screen) | live |
| Cited by · Trust Calculation | TXT-02 `?row=` | planned (T-07-T17) |
| Cited by · Worksheets 1041 page 1 | TAX-05 Worksheets field | live |
| Approve interpretation | SHL-12 L3 | live |
| Edit a Proposed row | SHL-10 Approve with edits | live |
| View page image | SHL-08 | live |
| Download / Open in Files | FIL-01 | live |

## Notes

The reader is a **reflowed legal reader** built from the clause tree (OQ-2), not page images; Gelasio on the page-1 title only, Geist elsewhere. No clause text is stored: the face re-reads the sealed layer through `evidence.api.text_layer`'s masked projection. Seven determination keys: `grantor_status`, `trust_type`, `fai_definition`, `trustee_fees`, `principal_invaded`, `exemption`, `election_65_day`.

## Deviations

- DV-1 spec states A–E vs artboards: E = a2; a3, a4 are extra sub-states.
- DV-11 editing: SHL-10 "Approve with edits" on a Proposed agent row; an O3 sheet with reason and clause on a human or adopted row.
- DV-12 required levels: `instrument_interpretation` L1 + L3 (KNW-04 review-level content).
- DV-13 outbound links are tooltip-only in the canvas; routes and params as above.
- DV-16 d1, d2, d3 are composed (no artboard); AY records a design follow-up for d1.

## Acceptance

SPEC-656's criteria for this screen; each becomes a test named "TXT-01 acceptance: <criterion>".
