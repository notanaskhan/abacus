# AUD-04 · Audit program & workpaper (General Audit Planning › Service Organizations)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/program/$wpRef` · `?tab=service-orgs\|linkage\|approach&version=` · `?ov=signoff:workpaper:<id>:L1\|L2` (SHL-12) |
| Template and host frame | T2 RecordCockpit without dock (rail 330 · canvas 1036) + SHL-07 citation popover · `Wave 2 - Audit Planning.dc.html#aud04` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-04 Audit program and workpaper - General Audit Planning - Service O/` (README.md, spec.md; no revision) |
| Epic and tasks | A-04 · stubs T01 (`docs/contracts/workpapers-core.md`) · cell store T03/T04 · procedures and inventory T07 · drafter T11 · screen T21 · parity T38 · SPEC-620 |
| Manifest status | planned (`routes/manifest/aud.ts`) |

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 2:30 PM | override | GAP version 1 written by a `gap` draft: every value a pending suggestion (outlined ◌ ticks), header pill "Draft · Accrued Agent"; the Keystone cell carries two verified citations (BH-EBP-110 step 4 at v3; SOC 1 p.14 section III) | live (T21) |
| b | marcus-delaney | 2:30 PM | override | Marcus's L1 adopted every suggestion on the version (R-SO-8): ticks ink-3 ✓, pill "Prepared · MD", "Performed by Agent run #n · adopted by MD" | live |
| c | hannah-leclerc | 2:30 PM | override | L1 and L2 signed: green pill "Signed off", chips ✓ MD ✓ HL; a later cell edit shows "Changed after sign-off" | live |
| d | hannah-leclerc | 2:30 PM | interact | Carve-out cell "Ridgeway Data Services" with two sources: SHL-07 stepper "1 / 2" (SOC 1 p.14 section III; BH-EBP-140 step 3); step 2 opens SHL-08 with the region lit purple | live |
| e | hannah-leclerc | 2:30 PM | `?tab=linkage` | service organization → procedure → workpaper from `service_organizations`, `procedures` and the cell store (Keystone → BH-EBP-140 steps 1–8 → SOC 1 Evaluation; Harborline → BH-EBP-310 step 2; PayGrid → BH-EBP-410 steps 2–6; Summit → none needed) | live |
| f | hannah-leclerc | 2:30 PM | `?tab=approach` | reliance vs substantive per area from `control_activities.reliance` and the service-organization reliance state; "BH-EBP-140 required: Yes" links to AUD-10 | live |
| loading | any | — | — | skeleton rows (C-20) while `GET …/workpapers/{id}/record` resolves | live |
| not allowed | client, third party, client_service, walled member | — | — | 404 from every A-04 route (INV-3, INV-4); the route shows the not-found state | live |
| off | any | — | — | `workpapers.core` off: the C-20 "not turned on" state; the rail row hides | live |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagements/{eid}/workpaper-states?kind=general_audit_planning` | `WorkpaperStateOut` | `workpaper.read` | — |
| read | `GET …/workpapers/{id}/record?tab=&version=` | `WorkpaperRecordOut` | `workpaper.read` | `workpaper.edit`, `workpaper.draft`, `workpaper.export`, `sign_off.prepare`, `sign_off.review`; the reviewer and EQR read only |
| read | `GET …/program-tailoring?program=BH-EBP-110` | `ProgramProcedureOut[]` | `procedure.read` | — |
| read | `GET …/service-organizations` | `ServiceOrganizationOut[]` | `service_org.read` | — |
| write | `PATCH …/workpapers/{id}/cells` | `CellsEditIn` (409 `version_conflict`, 422 `reason_required`) | `workpaper.edit` | EP, manager, senior, staff |
| write | `POST …/workpapers/{id}/drafts` `{mode: gap}` | 202 `WorkpaperDraftStartedOut` | `workpaper.draft` | EP, manager, senior; absent with `workpapers.drafting` off |
| read | `GET …/workpapers/{id}/export.xlsx` | bytes | `workpaper.export` | team, reviewer, EQR |
| write | `POST /v1/sign-offs` (C3) | L1 adoption, L2 | `sign_off.create` | opens SHL-12; the screen never signs |

## Status
`audit_section` (rail and header), `workpaper_value_state` (ticks), `audit_procedure`, `service_organization`.

## Copy
Verbatim from spec.md: header pills "Draft · Accrued Agent", "Prepared · MD", "Signed off"; popover header "BH-EBP-110: General Planning Procedures" with the firm's own step text; "Citations (1)", "Procedures (1)", "BH-EBP-140 required: Yes", "Open in Excel", "Sign off…"; Audit Approach rows "Reliance on Keystone controls: Yes, with bridge letter and CUEC testing" · "Reliance on PayGrid: No — substantive" · "Harborline: certification relied on per §103(a)(3)(C)".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Cited cell ↗ | KNW-03 `?step=4&from=citation` | live (K-01) |
| Citation step 2 | SHL-08 at SOC 1 p.14 | live (P-03) |
| BH-EBP-140 required | AUD-10 | live once T37 lands; planned before |
| Sign off… | SHL-12 `?ov=signoff:workpaper:<id>:L1` | live (P-04) |
| Rail rows | AUD-05, AUD-09, AUD-03 | live (A-01) |
| Opens AUD-01 · all audits | AUD-01 | handoff link (status in the manifest) |

## Acceptance
- AUD-04 acceptance: the popover header names the firm's program and its step text is the firm's own wording.
- AUD-04 acceptance: the table separates relevance, SOC evidence and subservice treatment, and Summit reads "No".
- AUD-04 acceptance: the bridge-letter row agrees with AUD-03 (requested Sep 1) and AUD-10 (gap Oct 1 – Dec 31, 2025).
- AUD-04 acceptance: agent-drafted values use outlined ticks and nothing reads as signed off.
- AUD-04 acceptance: a citation whose source moved shows "Source moved — Re-link…" and is not offered as verified (AC1.4).

## Figures
The bridge-letter gap is 92 days (Oct 1 – Dec 31, 2025), computed by `soc_gap` (T31); the workpaper only cites it.

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum; a "Technology hosting" row treated as a peer (Ridgeway Data Services is a carved-out subservice organization); the words Accrual, Arc, ACME, LSA, Finality, NetSuite as service organizations; AU-C paragraph text in chrome (ADR-056, D8).

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| DV-A4-1 | b's viewer is Marcus (README), the plan's persona table agrees | The artboard wins for parity | DEC-1758 |
| DV-A4-2 | "Open in Excel" is an audited download with Restricted cells masked, not an ADR-036 export | OQ-13 | DEC-1758 |
| DV-A4-3 | Designed workpaper, never converted to Sheets | D3 | — |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–f | C (0.20 / 3%) | — | locks by S28 (T38); T2 frame at Tier B is F-05's |
| header, pills, bands | D | — | audit bar 59, pane header 46 (14.5/500), pills 21/19/18, radius 12 |

## Open gaps
None beyond the deviations.
