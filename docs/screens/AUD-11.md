# AUD-11 · Sampling

| Field | Value |
|---|---|
| Route and params | No path of its own: the AUD-02 cockpit's Fieldwork › Sample Selection canvas, `/audits/$auditId?section=sample_selection&sample=<sampleSetId>&version=<n>`, behind `sampling.sample_sets` (A-03 §5.1). Artboards: `/components/screens/AUD-11?st=a…f`, plus `picker`, `off`, `loading`, `error`, `not_allowed` |
| Template and host frame | T2 record cockpit: rail 330 · canvas 696 · dock 330 (Viewer, DV-A2) · `Wave 2 - Audit Fieldwork.dc.html#aud11` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-11 Sampling/` (README.md, spec.md, revision-1.md, revision-2.md R2; revision wins) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | A-03 · contract A-03-T02 (`docs/contracts/sampling.md`, this file); sampler A-03-T04; migration A-03-T05; populations A-03-T07; sample sets A-03-T10; a, b, d and the picker A-03-T11; c, e, f and SHL-14 c A-03-T15; content A-03-T16; parity and E2E A-03-T19 |
| Manifest status | fixture (`routes/manifest/aud.ts`, A-03-T11): a, b, d, the picker and the C-20 states; live once A-03-T10 serves sample sets |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | marcus-delaney | Thu Sep 24, 2026, 10:15 AM CT | Northwind Participants Version 2 approved by Hannah Leclerc ("✓ HL"); census v2 (412) ties twice; seed `0x5E2A91`; 25 items; Version 1 Superseded (struck) | built (A-03-T11) |
| b | marcus-delaney | 9:24 AM | Version 2 "Prepared · MD", not approved: Generate disabled, tooltip "A manager must approve the sample first" | built (A-03-T11) |
| c | marcus-delaney | 9:24 AM | Generate sheet O3: five templates, due Oct 1, 2026, wave "Sample-driven", "125 requests · 100 to POR-03 · 25 to POR-14" | built (A-03-T15) |
| d | marcus-delaney | 9:24 AM | Size edited to 20: amber banner, required rationale; saving draws Version 3 (override pending) | built (A-03-T11) |
| e | marcus-delaney | 9:24 AM | A person's draw in progress: "Drawing" (DV-A1), rows 70 ms apart (reduced-motion safe), polling `…/draw` | built (A-03-T15) |
| f | simone-baptiste | Thu Sep 24, 2026, 10:20 AM CT | Granite Peak FY2026 · BH-FS-430: General ledger source, 1,912 payments, two ties, strata 24 / 1,102 / 786, 24 + 16 = 40, seed `0x7C31B4` | built (A-03-T15) |
| g | kira-ross | Mon Sep 14, 2026, 9:24 AM CT | HR or ticketing source (BambooHR) | recorded for X-01; the option is disabled with its tooltip |
| Picker | marcus-delaney | 10:15 AM | Northwind's two sample sets: "Participants · 25 of 412 · Approved", "Distributions · 10 of 64 · Draft" (DF-05; DV-A4) | built (A-03-T11) |
| Off | marcus-delaney | — | `sampling.sample_sets` off: C-20 "not turned on" | built (A-03-T11) |
| Not allowed | cole-hart | — | walled from Northwind: every read 404, no count in the picker (INV-3) | built (A-03-T11) |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, f | C (locked) | not run | locked by A-03-T19: the dock pane (DV-A2) and the population SHA-256 (DV-A3) masked; report-only as Tier C |
| b, c, d, e | C | not run | report-only (A-03-T19); dock pane masked (DV-A2); e with reduced motion |
| g | — | — | recorded for X-01 (HR or ticketing source); the option renders disabled with its tooltip |
| host | D | — | cockpit toolbar 46, audit bar 59, rail 330, canvas, dock 330; table rows 44; measured by the Tier D geometry run |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/work-items/{wid}/sample-sets` | `ListPage[SampleSetSummaryOut]` | `sample_set.read` | — |
| read | `GET /v1/sample-sets/{sid}?version=n` | `SampleSetOut` | `sample_set.read` | `sample_set.create` (Edit, Draw), `sample_set.approve` (Approve; never the preparer), `sample_set.export` (Open in Excel), `sample_set.generate_requests` (Generate…), `sign_off.prepare` (Sign off…) |
| read | `GET /v1/sample-sets/{sid}/versions/{n}/items?q=` | `ListPage[SampleItemOut]` | `sample_set.read` | — |
| read | `GET /v1/sample-sets/{sid}/versions/{n}/draw` | `DrawProgressOut` | `sample_set.read` | — |
| read | `GET /v1/populations/{pid}` | `PopulationOut` | `population.read` | — |
| write | `POST /v1/sample-sets/{sid}/versions` | `VersionIn` → 202 `VersionStartedOut` | `sample_set.create` | 409 `completeness_tie_required` |
| write | `POST …/versions/{n}/approve` | `ApproveIn` → `SampleSetOut` | `sample_set.approve` | 409 `population_not_tied`, `override_not_acknowledged`, `content_changed` |
| write | `POST …/versions/{n}/item-requests/preview` and `…/item-requests` | `ItemRequestsIn` → preview / created | `sample_set.generate_requests` | 409 `sample_not_approved` |

## Status
`sample_set_version` (Drawing · Draft · Approved · Superseded · Failed; "Override pending" and "Prepared · MD" are derived), `completeness_tie_result` (`tie`, `off {amount}`, `Check`).

## Deviations
| ID | State | Deviation | Reason |
|---|---|---|---|
| DV-A1 | e | State label "Drawing"; no dock live dot | The draw is code a person started; attributing it to the agent breaks INV-5 |
| DV-A2 | a–e | Dock opens on Viewer; the "Sample selector · Version 2" run card, narration and "Sign off run" are absent; parity masks the dock pane | No agent run exists (A-11); the dock kit is P-09 |
| DV-A3 | a, f | Population SHA-256 is real data; parity masks it | A hash cannot be forced to the design's value |
| DV-A4 | header | Composed sample-set picker | DF-05 |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Sign off… | SHL-12 `?ov=signoff:sample_set_version:<id>:L1` | planned (A-03-T11) |
| Source link | SHL-08 viewer | planned |
| Parameter values | SHL-07 citation popover "BH-EBP-210 step 3 · Table 2" | planned |
| Generate… | sheet → AUD-03 "Sample-driven" group, POR-03, POR-14 | planned (A-03-T13, T15) |
| Participant row | EBP-03 filtered | planned (A-05) |
| "All Audits" chip | AUD-01 | planned |
| Rail rows and cards | AUD-08 · AUD-04 · AUD-06 · AUD-07 · AUD-09 · AUD-10 · AUD-29 | planned (cockpit rail, A-01) |
| Dock run card | WB-09 run trace | planned (A-11) |
| Client and plan rows | CLI-02 · EBP-01 | planned |
| Program step citation | KNW-03 | planned |
| Testing rows | EBP-02 · EBP-04 · EBP-05 · EBP-06 · EBP-07 | planned (A-05) |
