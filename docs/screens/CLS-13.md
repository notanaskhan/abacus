# CLS-13 · 1099 / W-9 tracker · Copperleaf 2026

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/entities/$entityId/information-returns` (`?year=`, `?w9=1`, `?vendor=`); artboards `/components/screens/CLS-13?st=…` |
| Template and host frame | T1 IndexList |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLS-13 1099 W-9 tracker - Copperleaf 2026/` |
| Epic and tasks | C-02 · SPEC-700, SPEC-701; screen contracts and scenarios C-02-T15 (TASK-8624); screen and live swap per `docs/plan/epics/C-02.tasks.csv` |
| Manifest status | live (C-02-T47: a–f and d2) |

Parity tier target: C (C-02 §5.5). Copy keys live in `apps/web/src/screens/CLS-13/copy.ts` when the screen task builds it; words from the handoff and the status vocabulary only. Fixtures come from the Python scenario through `make fixtures` (F-04-T31), never hand-written.

## States
| Letter | Artboard | Scenario | Persona | Clock (CT) | Build | Owner |
|---|---|---|---|---|---|---|
| a | September tracking | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon Sep 14, 9:24 AM | live | AY |
| b | W-9 request batch | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| c | TIN mismatch | `see fixtures/scenarios/CLS-13.ts` | Elena Ruiz | Mon 14 Sep 2026, 9:24 AM | live | AY |
| d | January · approve batch | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Tue Jan 26, 2027 | live | AY |
| d2 | January · filed | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| e | Prior year · 2025 | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |
| f | Empty | `see fixtures/scenarios/CLS-13.ts` | Raj Malhotra | Mon 14 Sep 2026, 9:24 AM | live | AY |

## Deviations
- Personas and clocks per state are in the scenario file. CLS-13c's README viewer cell names the vendor string; the state is Raj Malhotra's.

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-01 · Closes | CLS-01 | designed (handoff link graph) |
| Opens SHL-08 · the signed Form W-9 | SHL-08 | designed (handoff link graph) |

## Design deltas (C-02-T10, DEC-5509)
Each row is the frame it amends (an annotated handoff screenshot) and the build answer; none needs a backend change outside the C-02 backlog.

| Frame | Handoff | Build | Why |
|---|---|---|---|
| `screenshots/CLS-13d.png` actions | e-file wording | "Export IRIS file", "Mark filed", "Record acceptance"; no Transmit | R-04, IRIS-001; SPEC-701 AC-18, AC-19 |
| `CLS-13b.png` channel | "Email the vendor a secure W-9 link" selectable | shown unavailable until R-03's link principal | C-02 §2.4 |
| `CLS-13a.png` vendor row | "Elena Ruiz Design" | kept verbatim; the contamination scan allows the exact vendor string | DEC-5508 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its screen task builds the screen.

| From | To | Status |
|---|---|---|
| Opens CLS-01 · Closes | CLS-01 | designed (handoff link graph) |
| Opens SHL-08 · the signed Form W-9 | SHL-08 | designed (handoff link graph) |


## Data and states (C-02-T47, DEC-6030)

| State | Data condition | Read |
|---|---|---|
| a | 2026 tracker: 12 vendors paid, 6 reportable, 2 requested, 1 TIN mismatch, 0 filed; December close not locked (`approval_open` false, target Jan 11, 2027) | `GET /v1/client-entities/{id}/information-returns?tax_year=2026` |
| b | a's data with the W-9 request drawer open (`?w9=1`): the two vendors without a W-9 that could need a 1099; the vendor-link channel unavailable | `POST …/w9-requests` (channel portal; firm's default wording) |
| c | a's data with Elena Ruiz Design's TIN check expanded (`?vendor=`): `tin_mismatch_on` Aug 28, backup withholding watch | `POST /v1/vendors/{id}/backup-withholding` (started, with a reason) |
| d | Jan 26, 2027: December close locked (`approval_open` true) | as a |
| d2 | batch filed through IRIS: the six reportable vendors `filed`, tile Filed 6 | as a |
| e | tax year 2025 (`?year=2025`): no payments synced (`payments_synced` false: Vendors paid "—"), the five filed returns, batch accepted Jan 29, 2026 | as a, `tax_year=2025` |
| f | no vendor payments synced | as a |

Additive read fields (C-02-T47): per row `tin_kind`, `backup_withholding`, `w9_requested_at`, `w9_evidence_version_id`, `tin_mismatch_on`, `filed`, `payments[]` (method, amount, count when known, counted); per year `payments_synced`, `filed_on`, `accepted_at`, `approval_open`, `approval_target_on`. `wording_template_version_id` on the W-9 request is optional (None: the firm's default wording).

**Deviations (C-02-T47).** (1) Route carries the entity (`/clients/$clientId/entities/$entityId/information-returns`) as CLS-11's does; the read is per client entity. (2) Entity type reads from C-02-T45's classification: "LLP (partnership)" shows "Partnership" and "Bank (corporation)" shows "C corporation" (the enum has no LLP or bank). (3) The tile summary shows the server's threshold and due rules; the handoff's "Payments Jan 1–Aug 31, 2026 from QuickBooks Online" and "e-file required (10+ …)" prefixes have no field yet. (4) The portal channel reads "Ask Copperleaf Coffee Roasters, Inc. through the portal" without "Ben Ashby uploads" (no uploader in the read). (5) The scenario's vendor payments are ACH bill payments with no transaction count (the handoff gives totals only). (6) Approve 1099 batch… opens SHL-10 with C-02's later wiring; here it enables on `approval_open`. (7) The dialogs' body copy is ours.
