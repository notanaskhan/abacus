# ENG-05 · Team & roles

| Field | Value |
|---|---|
| Route and params | `/engagements/$engagementId/team` (ENG-02's Team tab; P-07 §5). Artboards: `/components/screens/ENG-05?st=a…e` |
| Template and host frame | T1 inside the ENG-02 record with an inspector, the blocked-assignment Dialog and the Replace EQR picker · `Wave 3 - Engagements & Projects.dc.html#eng05` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-05 Team and roles/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · G2 v2 P-07-T24 · stub P-07-T29 · team backend P-07-T30 · AC suite P-07-T26, T32 · screen P-07-T39 |
| Manifest status | planned (`routes/manifest/eng.ts`) until P-07-T39 |

Code to come: `src/screens/ENG-05/{index.tsx, scenarios.ts, copy.ts, ENG-05.test.tsx}`. Flag `engagements.v2`. Spec: SPEC-332 AC-13 to AC-16; ADR-164.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 9:24 AM CT | E0 | Northwind PY2025 EBP audit: five confirmed, Kira Ross proposed Sep 11 and pending; hours 172.0 budget / 24.0 actual | built · live (T39) |
| b | hannah-leclerc | Fri Sep 11, 2026 | E0 − Kira's request | "+ Add person" → Kira Ross: Dialog "Assignment pending independence" | built · live (T39) |
| c | thomas-whitcombe (README viewer) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Fairhaven variant: Replace EQR picker; Thomas Whitcombe "Not eligible — EP on this plan for PY2024 (cooling-off, 2 years)", Assign disabled; Celia Marsh "Eligible" | built · live (T39) |
| d | hannah-leclerc | same | E0 + Kira confirmed | Kira's row "✓ Confirmed Sep 14"; banner gone | built · live (T39) |
| e | hannah-leclerc | same | new engagement | "No team yet." + "Add the engagement partner" | built · live (T39) |

Not-allowed: a walled engagement answers 404. Without `engagement.member_add` the add controls are hidden.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read/write | `GET/POST/PUT/DELETE /v1/engagements/{engagement_id}/team[/{user_id}]` | members with roles, budget hours, independence state | `engagement.read_metadata`, `engagement.member_add/remove`, `engagement.update` | partner, manager |
| write | work-item, to-do and sign-off slot assignment naming a pending member on an attest client | 409 `gate_unmet` `{"gate": "G2", "user_id": …}` | `work_item.assign` (P-07-T24) | partner, manager; refused for the target through `engagements.api.independence_cleared` |
| write | `PUT …/team/{user_id}/portal-visibility` | the POR-02 team card | `engagement.update` | partner, manager |
| write | `POST …/team/approve` | the EP approves the team | `team.approve` | engagement partner; human-only |
| read/write | `GET …/eqr/candidates` · `POST …/eqr` · `POST …/eqr/eligibility/approve` | eligibility per candidate; 409 `eqr_approver_is_ep` | `eqr.assign` · `eqr.approve_eligibility` | EP and manager · quality partner (≠ EP) |
| write | `POST …/independence/reminders` | "Send confirmation request" | `independence.remind` | partner, manager |

## Status
Independence chip: Confirmed · Requested (ring + amber) · Declined. EQR eligibility: Eligible (green-tint) · Not eligible (red-tint).

## Copy
| Key | String |
|---|---|
| `b.title` | "Assignment pending independence" |
| `b.body` | "{person} hasn't confirmed independence for {engagement}. She can view the engagement but can't be assigned work or sign off." (pronoun from the seed person) |
| `b.send` · `b.cancel` | "Send confirmation request" · "Cancel" |
| `c.notEligible` | "Not eligible — EP on this plan for {year} (cooling-off, 2 years)" |
| `c.eligible` | "Eligible" |
| `d.confirmed` | "✓ Confirmed {date}" |
| `e.empty` · `e.action` | "No team yet." · "Add the engagement partner" |
| `menu` | "Change role…" · "Edit hours…" · "Remove from team…" |
| `request.sheet` | "Request confirmations…" · "Send" |
| `toggle.portal` | "Shown on portal" |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Independence chip ("Opens CLI-08 · team confirmations") | CLI-08 | planned (P-07-T48) |
| Budget h and Actual h ("Opens ENG-06 · budget, time & AI effort") | ENG-06 | planned (I-04) |
| Audit cockpit ("Opens AUD-02 · audit cockpit · Northwind Robotics 401(k) Plan") | AUD-02 | planned (A-01) |
| "Shown on portal" | POR-02 | fixture (P-08) |
| Inspector capacity | HOME-04 | planned (later) |

Inbound: ENG-02 (Team tab), AUD-02 (rail "Team ›"), ENG-03 (step 4). All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- ENG-05 acceptance: Kira Ross can view the engagement but cannot be assigned work or sign off until she confirms; the engagement itself is not blocked.
- ENG-05 acceptance: budget hours foot to 172.0 and actuals to 24.0; the agent's 412 minutes stay out of the hours columns.
- ENG-05 acceptance: the EQR's eligibility approval is by the QM owner (Celia Marsh), never the EP.

## Figures
Hours 172.0 / 24.0 foot to ENG-06 (seed test).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, photo avatars, coloured initials, red backgrounds, the Accrued Agent as a signer, the words Accrual/Arc/ACME.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| g2-scope | The blocked-assignment dialog appears only on attest clients' engagements; on a non-attest engagement the person is added and confirmation is still requested | G2 v2 applies only to attest clients | DEC-39, ADR-164 item 2 |
| stricter | With the firm setting `g2_blocks_view` on, "She can view the engagement" is not true: the copy drops the view clause | Stricter-only firm setting | ADR-164 item 3 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–e | C | — | |

## Open gaps
None open.
