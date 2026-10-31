# AUD-10 · Service organizations & SOC 1 evaluation

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/service-orgs` · `?org=<id>&page=<n>` · `?dock=viewer` |
| Template and host frame | T2 audit split (rail 330 · canvas 536 well with block cards · viewer 490) · `Wave 3 - Audit Fieldwork.dc.html#aud10` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-10 Service organizations and SOC 1 evaluation/` (README.md, spec.md; no revision) |
| Epic and tasks | A-04 · stubs T01 · inventory T07 · evaluation and gap T31 · SOC 1 reader T35 · screen T37 · parity T38 · SPEC-620. **Tier-2 cut candidate** decided at M14 (Fri Oct 15, 2027) |
| Manifest status | planned |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | marcus-delaney | Mon Sep 14, 2026, 2:30 PM | E0 | Keystone SOC 1 Type 2 period Oct 1, 2024 – Sep 30, 2025 against a calendar plan year: gap Oct 1 – Dec 31, 2025 = 92 days; 2 of 6 CUECs Evidenced; reliance pending | live |
| b | marcus-delaney | Tue Sep 22, 2026 | E0 | Sam Ortiz uploaded the bridge letter in POR-14: the gap outlined "Bridge letter · no changes reported"; Keystone "Bridge letter received"; gap procedures cite BH-EBP-140 step 8 | live |
| c | marcus-delaney | 2:30 PM | `?cuec=2` | CUEC 2 selected: the viewer jumps to SOC 1 p.41 with the CUEC lit; links AUD-09 row 2 | live |
| d | marcus-delaney | 12:24 PM | E0 | The `soc1` reader run is running (the draft lands 12:40): skeleton bars and a header spinner | live with `workpapers.drafting` |
| e | marcus-delaney | 2:30 PM | override | CO 10 exception with High impact: red-tint row linked to Findings | fixture; live when a High exception exists |
| loading, not allowed, off | as AUD-04 | — | — | `assurance.service_orgs` off: C-20 state (the inventory still serves AUD-04 with `workpapers.core`) | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read · write | `GET`, `POST`, `PATCH …/service-organizations[/{id}]` | `ServiceOrganizationOut` | `service_org.read` · `service_org.edit` | team edits |
| read | `GET …/soc-reports/{id}` | `SocReportOut` with `SocGapOut` | `service_org.read` | — |
| write | `PATCH …/soc-reports/{id}`, `PATCH …/cuecs/{n}` | `SocReportPatchIn`, `CuecPatchIn` (the gap recomputed by code) | `soc_report.evaluate` | EP, manager, senior |
| write | `POST …/soc-reports/{id}/requests` `{kind}` | `RequestDraftOut` (POR-14 bridge letter, POR-03 CUEC evidence) | `request_item.create` | drafts; a person sends |
| write | `POST …/soc-reports/{id}/reliance-requests` | `RelianceRequestOut` (409 `gap_open`, `cuec_evidence_missing`) | `soc_report.evaluate` | never the agent; the EP decides (DEC-83) |
| write | `POST …/soc-reports/{id}/drafts` | 202 | `workpaper.draft` | EP, manager, senior |

## Status
`service_organization`, `soc_reliance`, `cuec`.

## Copy
"Bridge letter · no changes reported", "Bridge letter received", the gap-procedures KV row ("… a bridge letter is not evidence of operating effectiveness"), "Complementary User Entity Controls", "2 of 6 evidenced", "Draft evidence request…", "Remind…".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| CUEC row | SHL-08 at SOC 1 p.41; AUD-09 row 2 | live |
| High exception | AUD-15 through the exception router | planned (A-06) |
| Draft evidence request… | SHL-14 (CUECs 1, 2, 3, 6 to Dana) | live (P-04) |
| Inbound | AUD-04 ("BH-EBP-140 required"), AUD-02 rail, AUD-09 row 4 | live |
| Opens AUD-03 · source documents filtered to Form 5500 & SOC 1 | AUD-03 | handoff link (status in the manifest) |
| Opens CLI-02 · Northwind Robotics, Inc. | CLI-02 | handoff link (status in the manifest) |
| Opens KNW-03 · BH Audit Methodology · EBP v3 | KNW-03 | handoff link (status in the manifest) |
| Opens ENG-05 · team and roles | ENG-05 | handoff link (status in the manifest) |
| Opens AUD-29 · activity log | AUD-29 | handoff link (status in the manifest) |
| Opens AUD-06 · Trial Balance | AUD-06 | handoff link (status in the manifest) |
| Opens AUD-07 · Materiality | AUD-07 | handoff link (status in the manifest) |
| Opens AUD-08 · Risk Assessment | AUD-08 | handoff link (status in the manifest) |
| Opens AUD-11 · Sample Selection | AUD-11 | fixture build (handoff link) |
| Opens AUD-12 · Testing | AUD-12 | handoff link (status in the manifest) |

## Acceptance
- AUD-10 acceptance: the coverage bar shows SOC period Oct 1, 2024 – Sep 30, 2025 against plan year Jan 1 – Dec 31, 2025 with a 92-day gap, matching AUD-04, AUD-09 row 4 and the seed.
- AUD-10 acceptance: "2 of 6 evidenced" equals AUD-09 row 5.
- AUD-10 acceptance: Harborline is relied on through the §103(a)(3)(C) certification, PayGrid is tested directly and Summit is not relevant.
- AUD-10 acceptance: the carve-out subservice organization (Ridgeway Data Services) is named and treated as carved out.
- AUD-10 acceptance: bridge-letter and gap procedures cite BH-EBP-140 step 8.
- AUD-10 acceptance: the layout keeps the audit split 330 · 536 · 490.

## Figures
Gap 92 days from `soc_gap` (T31) over the adopted period, never from model text; the text alternative reads "SOC 1 period ends Sep 30, 2025; plan year ends Dec 31, 2025; gap 92 days; bridge letter received Sep 22".

## AVOID
Gradients other than the gap hatch, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, real audit-firm or recordkeeper names, a reliance conclusion while the gap is open.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A10-1 | b's README viewer is Marcus; the spec says Hannah. The artboard wins | Parity | DEC-1758 |
| DV-A10-2 | Walkthrough evidence is filed with the workpaper, not as a PBC request (the 24-request count stays) | A-04 §2.1 | DEC-1758 |

## Parity
| Artboard | Tier | Diff % | Notes |
|---|---|---|---|
| a–e | C | — | by S28 (T38) unless the tier-2 cut is invoked at M14 |

## Open gaps
None.
