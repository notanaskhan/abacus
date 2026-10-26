# ENG-05 · Team & roles

| Field | Value |
|---|---|
| Route and params | `/engagements/$engagementId/team` (ENG-02's Team tab; P-07 §5). Artboards: `/components/screens/ENG-05?st=a…e` |
| Template and host frame | T1 inside the ENG-02 record with an inspector, the blocked-assignment Dialog and the Replace EQR picker · `Wave 3 - Engagements & Projects.dc.html#eng05` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-05 Team and roles/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · G2 v2 P-07-T24 · stub P-07-T29 · team backend P-07-T30 · AC suite P-07-T26, T32 · screen P-07-T39 |
| Manifest status | planned (`routes/manifest/eng.ts`): built on fixtures by P-07-T39 as ENG-02's Team tab (in-screen tabs, no own path), planned for ENG-02's reason |

Code: `src/screens/ENG-05/{index.tsx, scenarios.ts, copy.ts, ENG-05.test.tsx}`, `src/domain/engagements/team.ts`, fixtures `fixtures/{seed,handlers}/team-roles.ts` and `fixtures/scenarios/ENG-05.ts` (P-07-T39, TASK-1274). Flag `engagements.v2`. Spec: SPEC-332 AC-13 to AC-16; ADR-164.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 9:24 AM CT | E0 | Northwind PY2025 EBP audit: five confirmed, Kira Ross proposed Sep 11 and pending; budget 172.0 (actuals 24.0 are ENG-06's, "—" here until I-04) | built · fixture (T39) |
| b | hannah-leclerc | Fri Sep 11, 2026, 9:24 AM CT | E0 − Kira's request | "+ Add person" → Kira Ross on an engagement with a G2 gate: Dialog "Assignment pending independence" | built · fixture (T39) |
| c | laura-kemp (the canvas's viewer; DEC-386) | Mon Sep 14, 2026, 9:24 AM CT | E0 | Fairhaven variant: Replace EQR picker; Thomas Whitcombe "Not eligible — EP on this plan for PY2024 (cooling-off, 2 years)" from the failing `cooling_off` check, Assign disabled; Celia Marsh "Eligible", current | built · fixture (T39) |
| d | hannah-leclerc | same | E0 + Kira confirmed | Kira's row "Confirmed" in ink (no date: see Open gaps); banner gone | built · fixture (T39) |
| e | hannah-leclerc | same | new engagement | Granite Peak PY2026 EBP Audit, Prospect, empty roster: "No team yet." + "Add the engagement partner" (offers the partners) | built · fixture (T39) |

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
| no-office | No Office column; the Person cell has no job-title sub-line (only "added {date}" for a member proposed since the approval); the inspector card has no "Partner · Chicago" line | `TeamRosterMemberOut` carries no office or title, and the staff list that has them needs `firm.manage_users` | DEC-386 |
| no-dates | Independence reads "Confirmed" without its date (a "Confirmed Jun 1"); EQR checks read "Independence confirmed" and "Capacity" without date or hours window | the roster and `EqrCheckOut` carry no confirmation date; capacity is `not_assessed` (DEC-327) | DEC-386 |
| actuals | Actual h shows "—" per row and in the totals | P-07 §2.1: until I-04; the seed's footing test keeps 24.0 | P-07 §2.1; DEC-386 |
| agent-minutes | Agent row "Acts with the invoking user's permissions · never signs off" without "412 agent-minutes, not billable"; the agent inspector has no Effort row | P-07 §2.1: until P-10 | P-07 §2.1 |
| pronoun | Banner and dialog say "they" where the canvas says "she" | the roster carries no pronoun | DEC-386 |
| approval-line | The inspector's Approval fieldset shows only "The EP cannot approve the EQR on her own engagement."; no "Eligibility approved by Celia Marsh (QM delegate) · Jun 1, 2026" | no read of the eligibility approval exists (only `POST …/eqr/eligibility/approve`) | DEC-386 |
| role-history | The member inspector has no Role history or "Other engagements this month" | no read for either; HOME-04 is later | DEC-386 |
| dialogs | Change role…, Edit hours… and Remove from team… open composed C-22 dialogs ("Change role — {name}", "Edit hours — {name}", "Remove {name} from the team?") with Save / Remove | the canvas only toasts "Opens …"; the routes exist | DEC-386 (DEC-32's approach) |
| viewer-c | c is seen by Laura Kemp (Fairhaven's manager), not Thomas Whitcombe | the canvas board uses Laura Kemp; Thomas is not on Fairhaven and could not open Replace EQR (`eqr.assign`) | DEC-386 |
| g2-scope | The blocked-assignment dialog appears only on attest clients' engagements; on a non-attest engagement the person is added and confirmation is still requested | G2 v2 applies only to attest clients | DEC-39, ADR-164 item 2 |
| stricter | With the firm setting `g2_blocks_view` on, "She can view the engagement" is not true: the copy drops the view clause | Stricter-only firm setting | ADR-164 item 3 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–e | C | — | Playwright not run locally (chromium 1243 wanted, 1248 cached); `e2e/screens/ENG-05.spec.ts` carries the axe check |

## Open gaps
- `TeamRosterMemberOut` lacks office, job title, pronoun and the confirmation date (no-office, no-dates, pronoun).
- No read of the EQR eligibility approval (who, when, or "Awaiting approval by a QM delegate · requested {date}") (approval-line).
- No role-history read for the member inspector (role-history).
- Actual hours wait on I-04, agent-minutes on P-10.
