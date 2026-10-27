# CLI-06 · New client / prospect intake (single and bulk import)

| Field | Value |
|---|---|
| Route and params | `/clients/new` (O6 over CLI-01); `?mode=import` for bulk import (P-07 §5). Artboards: `/components/screens/CLI-06?st=a…i` |
| Template and host frame | O6 `Wizard` (stepper) over CLI-01 · `Wave 3 - Home & Clients.dc.html#cli06` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-06 New client prospect intake - single - bulk import/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · stubs P-07-T37 · TIN P-07-T10 · conflicts and screening P-07-T36 · single commit P-07-T42 · bulk import P-07-T52 · screens P-07-T49 (single), P-07-T54 (bulk) |
| Manifest status | live (`routes/manifest/cli.ts`, P-07-T49: single intake at `/clients/new`; bulk import P-07-T54) |

Code to come: `src/screens/CLI-06/{index.tsx, scenarios.ts, copy.ts, CLI-06.test.tsx}`, `src/domain/clients/ConflictResults.tsx`, `src/fixtures/handlers/intake.ts`. Flag `clients.v2`. Spec: SPEC-332 AC-23 to AC-26.

## States

9 artboards (a, g, h, i from spec.md; b–f added during the build, README). The step frames b–f are the wizard's steps; a is step 5.

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | grace-holloway | Tue Sep 8, 2026, 2:10 PM CT | Thornbury holdout (estate not yet added) | Step 5 Conflict check: four names, "No conflicts"; screening rows recorded by a person | built · live (T49) |
| b | grace-holloway | same | same | Step 1 Entity details: dedupe card "96% match · Walter Thornbury", "Add the estate under this client (recommended)" | built · live (T49) |
| c | grace-holloway | same | same | Step 2 Related entities: decedent → estate | built · live (T49) |
| d | grace-holloway (README lists Paul Thornbury: the contact being added) | same | same | Step 3 Contacts: Paul Thornbury, executor | built · live (T49) |
| e | grace-holloway | same | same | Step 4 Services: final 1040, estate 1041, Form 706 | built · live (T49); due dates planned (see Deviations) |
| f | grace-holloway | same | same | Step 6 Review: "Create & start acceptance" · "Create" | built · live (T49); intake toggle planned |
| g | grace-holloway | Tue Sep 8, 2026, 2:04 PM CT | E0 + a synthetic 212-row CCH-format file | Bulk import review: 204 matched + 8 to review + 0 new = 212; rows 7–8 Skip → "Import 210 records" | built · live (T54) |
| h | samuel-ito | 2:10 PM | same | Conflict hit: "Harborline Trust Company" → amber "Counterparty · custodian for Calloway Family Trust — review" with "Clear as not adverse…" for a manager | built · live (T49) |
| i | grace-holloway | 2:10 PM | same | Validation: Date of death empty → "Required for Form 706 due date" | built · live (T49) |

Not-allowed: without `client.intake` the "+ New client" entry is hidden and the route renders not-allowed. A match on a walled client renders "Match on a restricted client" (SPEC-332 AC-24). Flag off: the flag-off ViewState.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| write | `POST /v1/clients/dedupe` | candidates with scores (names in the body) | `client.create` | firm admin, partner, manager |
| write | `POST/PATCH/DELETE /v1/client-intake-drafts` · `…/validate` · `…/{id}/commit {start_acceptance}` (+ `Idempotency-Key`) | one unit of work: entity, relationship, contact, Prospect engagement, work items, conflict link, acceptance record | `client.intake` | firm admin, partner, manager; agent and system deny |
| write | `POST /v1/conflict-checks` · `GET …/{id}` | results with `{redacted: true, match_kind}` for walled matches | `conflict.run` | firm admin, partner, manager |
| write | `POST /v1/conflict-checks/{id}/results/{result_id}/clear` | `{assessment, reason}` | `conflict.clear` | partner, manager; human-only |
| write | `POST /v1/screening-records` | a person-recorded result with an optional evidence link | `screening.record` | firm admin, partner, manager |
| write | `POST /v1/client-imports` (multipart) · `GET …/{id}` · `…/rows` · `PUT …/rows/{row_id}/decision` · `POST …/{id}/run` (202) | bulk import | `client_import.run` | firm admin, partner, manager |

## Status
`client` Prospect for the new engagement's client entity; the engagement is created Prospect only. Conflict assessment words: "No conflicts" · "Counterparty … — review" · "Not adverse". Import progress pill "Importing 210 records…".

## Copy
| Key | String |
|---|---|
| `dedupe.match` (b) | "96% match · Walter Thornbury" |
| `dedupe.recommended` (b) | "Add the estate under this client (recommended)" |
| `validation.dod` (i) | "Required for Form 706 due date" |
| `conflicts.none` (a) | "No conflicts" |
| `conflicts.restricted` | "Match on a restricted client" |
| `conflicts.clear` (h) | "Clear as not adverse…" |
| `screening.recordedBy` | "Recorded by {person}" |
| `review.createStart` · `review.create` (f) | "Create & start acceptance" · "Create" |
| `import.run` (g) | "Import {count} records" |
| `import.progress` (g) | "Importing {count} records…" |
| `import.toast` (g) | "{imported} records imported · {skipped} skipped · {new} new clients" |
| `import.decisions` (g) | "Merge" · "Keep both" · "Skip" |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Create & start acceptance" | CLI-07 | planned (P-07-T46) |
| "Create"; dedupe "Open" | CLI-02 `to.CLI02({ clientId })` | planned (P-07-T19) |
| The host and Escape | CLI-01 `to.CLI01()` | fixture (P-07-T12) |
| A conflict hit's client link (unwalled only) | CLI-02 | planned (P-07-T19) |

Inbound: CLI-01 "+ New client" and "Bulk import". All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-06 acceptance: the estate is added as an entity of the existing Walter Thornbury client whose display name stays "Walter Thornbury" (DEC-62).
- CLI-06 acceptance: engagements are created as Prospect only; "Create & start acceptance" opens CLI-07.
- CLI-06 acceptance: Next validates each step; step rows jump only to completed steps.
- CLI-06 acceptance: bulk import foots 204 + 8 + 0 = 212 and 210 imported + 2 skipped; nothing below 90% merges without a person's decision.

## Figures
CLI-06 g: 204 + 8 + 0 = 212; 212 − 2 = 210 (seed and scenario footing tests, P-07-T54).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, bordered inputs, native selects, auto-merging below 90% without review, creating engagements before acceptance; any automated screening result.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| screening | Screening rows (OFAC SDN, adverse media, restricted entities) show results "Recorded by ‹person›" with an optional evidence link, not an automatic check | In-app conflicts first, human-recorded screening; no list provider | DEC-64, SPEC-332 AC-26 |
| due-dates | Step 4's per-service due dates are planned: they render from T-08's deadline rules when that lands; until then the row shows the service only | No rules table yet | DF-10 |
| intake-toggle | The POR-18 intake send to Paul Thornbury ("portal Invited") is planned; f's toggle is hidden in production until the intake grant kind ships | Intake-scope grants are P-08/OQ-11's | P-07 §3.2 (OQ-11) |
| redaction | A walled match renders one row without name, link or count | Walls never leak | DEC-43, DEC-64 |
| d-viewer | The README names Paul Thornbury as d's viewer; the viewer is Grace adding him | A contact never sees the firm wizard | P-07 §5 fixture table |
| served | The conflict step lists the check's matches (no per-name "No matches" rows, which the check does not serve) and the counterparty words without the relationship ("Counterparty — review"); screening rows recorded earlier are not readable back (no read route), so a's three recorded rows are the scenario's opening state and production shows "Record…" per list until a person records it in this intake; the step-1 values are those the draft holds (type, name, decedent, date of death); the date is entered as YYYY-MM-DD | P-07-T42's shapes | DEC-543 |
| validation | A problem on another step's field (the services step's `entity.date_of_death`) jumps to that step and says why there | i, "Next validates each step" | DEC-543 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–i | C | — | |

## Open gaps
None open.
