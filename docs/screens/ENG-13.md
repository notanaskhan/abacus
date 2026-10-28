# ENG-13 · Roll forward

| Field | Value |
|---|---|
| Route and params | `/engagements/$engagementId/roll-forward` (O6 over ENG-02; P-07 §5). Artboards: `/components/screens/ENG-13?st=a…e` |
| Template and host frame | O6 `Wizard` (five steps, Carry · Skip per row) · `Wave 6 - Group Audit & Procedures.dc.html#eng13` (kit `kits/ENG13 Rollforward.dc.html`) |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/ENG-13 Roll forward - Tessellate SOC 2 Type 2/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · backend P-07-T55 · screen P-07-T60 |
| Manifest status | planned (`routes/manifest/eng.ts`) until P-07-T60 |

Code: `src/screens/ENG-13/{index.tsx, scenarios.ts, copy.ts, ENG-13.test.tsx, ENG-13.production.test.tsx}`, fixtures `src/fixtures/scenarios/ENG-13.ts`, axe `e2e/screens/ENG-13.spec.ts` (P-07-T60). Flag `engagements.roll_forward_v2`.

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | laura-kemp | Mon Nov 16, 2026, 10:15 AM CT | E2 | Tessellate SOC 2 Type 2, step 2 What to carry (212 + 1 = 213 requests) | built · fixture (attest carry; see Deviations) (P-07-T60) |
| b | laura-kemp | same | E2 | Step 3 Template version: "BH SOC 2 · TSC 2017 (rev. 2022) v1" Current; "Nothing to reconcile." | built · fixture (attest carry) |
| c | hannah-leclerc | Mon Nov 16, 2026, 11:00 AM | E2 | Granite Peak FY2026 → FY2027: template changed FS v5 → FS v6; conflict rows | built · fixture (template conflicts) |
| d | hannah-leclerc | Mon Jan 11, 2027, 9:30 AM | E2 + archive | Northwind PY2025 EBP Audit Archived → PY2026: 26 workpapers, 24 requests carried as Draft | built · live (T60) |
| e | laura-kemp | Mon Nov 16, 2026, 10:15 AM | E2 | Step 5 Review and Create; toast "Engagement created · SOC 2 Type 2 · Oct 1, 2026 – Sep 30, 2027" | built · live (T60) |

Not-allowed: a walled source answers 404; a source in `active` answers 409 `roll_forward_source_not_released`.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read and write | `POST /v1/engagements/{engagement_id}/roll-forward/drafts` · `GET`/`PATCH`/`DELETE …/{draft_id}` · `POST …/{draft_id}/create` (`docs/contracts/engagements-v2.md` §8a) | `RollForwardDraftOut` (selections, team, template decision, catalogue); one unit of work at Create; continuance acceptance record opened | `roll_forward.create` on the client + `roll_forward.read` on the source (DEC-805) | firm admin, practice leader, partners and managers by level; the source's engagement partner or manager to read it; agent and system deny. The Carry · Skip controls and Create follow `allowed_actions` (`roll_forward.create`) |

## Status
Source `engagement` Delivered or Archived (soon pill + Lock 12 "WORM"); carried request items arrive as Draft (never client-visible). Template "Current".

## Copy
| Key | String |
|---|---|
| `row.toggle` | "Carry" · "Skip" |
| `b.current` · `b.pinned` | "Current" · "No newer version · pinned at Create" |
| `b.nothing` | "Nothing to reconcile." |
| `e.create` · `e.createLetter` | "Create" · "Create & draft letter" (fixture builds; production draws Create only until N-02) |
| `e.toast` | "Engagement created · {type} · {period}" |

Template names, carry rows and counts are data.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Create" | ENG-02 | planned (P-07-T20) |
| "Create & draft letter" | ENG-04 | planned (N-02) |
| Team independence chips | CLI-08 | planned (P-07-T48) |
| Conflict rows | SHL-22 | planned |
| Learned-context rows | WB-13 | planned (later wave) |

Inbound: ENG-02 ("Roll forward"). All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- ENG-13 acceptance: evidence, results and sign-offs never move; prior evidence is referenced read-only (ADR-004).
- ENG-13 acceptance: carried request items arrive as Draft and are never client-visible.
- ENG-13 acceptance: the new engagement opens a continuance acceptance record (G1 again) and pins one template version.

## Figures
Northwind: 26 workpapers (6 + 3 + 7 + 6 + 4), 24 requests as Draft; Tessellate 212 + 1 = 213 requests (fixture).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, Accrual/Arc/ACME/LSA, Fieldguide product names, "task" for a to-do, the agent approving, signing or sending anything, copying evidence, results or sign-offs.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| attest-carry | a and b (SOC 2 attest carry) are fixture-only | Attest engagements arrive with X-01 | P-07-T60 row, P-07 §5 |
| conflicts | c (template conflicts and SHL-22 change list) is fixture-only | Template diffing lands with chapter 03's `RollForwardWorkflow` (K-03) | P-07 §4.5 |
| letter | "Create & draft letter" opens ENG-04's record-mode card until N-02 | Interim recorded letter | P-07 §3.6 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| d e | C | — | |
| a b c | C (fixture) | — | |

## Open gaps
- The v1 rows' details ("4 people · roles as last year; independence asked again", "24, as Draft; the client sees nothing until you send", "Last year's record, letters and archive, linked read-only") are written for the v1 categories the handoff does not draw on their own (DEC-805); copy review with the screen's parity pass (P-07-T63).
- Conflict choices (c) are a pressed-button pair, not a Segmented: a Segmented always holds a selection, and Next must wait for both choices.
