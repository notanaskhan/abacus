# CLI-08 · Independence & conflicts

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/independence/$engagementId` (P-07 §5). Artboards: `/components/screens/CLI-08?st=a…g` |
| Template and host frame | T1 inside the client record with tabs (Team confirmations · NAS matrix · Conflicts · Rotation), O2 person drawer, O3 confirm sheet, SHL-11 conclusion · `Wave 3 - Home & Clients.dc.html#cli08` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-08 Independence and conflicts - PY2025 EBP Audit - Northwind Roboti/` (README.md, spec.md; no revision) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · G2 v2 P-07-T24 · stub P-07-T29 · conflicts P-07-T36 · live P-07-T41 · AC suites P-07-T26, T43 · screen P-07-T48 |
| Manifest status | live (`routes/manifest/cli.ts`, P-07-T48) |

Code to come: `src/screens/CLI-08/{index.tsx, scenarios.ts, copy.ts, CLI-08.test.tsx}`, `src/domain/engagements/IndependenceChip.tsx`, `src/fixtures/handlers/independence.ts`. Flags `engagements.v2` (G2 v2), `engagements.acceptance_v2` (CLI-08 v2). Spec: SPEC-332 AC-13 to AC-28; ADR-164.

## States

7 artboards (spec.md) plus one undesigned state (DF-06).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 9:24 AM CT | E0 | Northwind PY2025 team MO · TW · HL · MD · AC: "4 of 5 confirmed"; amber G2 banner naming Ana Cruz; "Conclude…" disabled "Reserved to Margaret Okonkwo" | built · live (T48) |
| b | hannah-leclerc | same | E0 | NAS matrix under ET 1.295, Dana Kowalski SKE designee | built · live (T48) |
| c | hannah-leclerc | same | E0 | Conflicts: seven names searched; Harborline the one related party ("Not adverse") | built · live (T48) |
| d | hannah-leclerc | same | E0 | Rotation: years served by the EP, the EQR reviewer and the manager | built · live (T48) |
| e | ana-cruz | same | E0 | Ana's own view: "Confirm your independence for PY2025 EBP Audit"; three statements; toast "Independence confirmed · Sep 14, 9:31 AM" | built · live (T48) |
| f | margaret-okonkwo | same | E0 + Ana confirmed | "5 of 5 confirmed"; "Conclude…" opens SHL-11; then "Concluded · Margaret Okonkwo · Sep 14" | built · live (T48) |
| g | hannah-leclerc | same | E0 + breach | "Breach logged — evaluate, communicate to TCWG, remediate" | built · live (T48) |
| declined-note (no artboard) | hannah-leclerc | same | E0 + a decline | A member "Declined" with their note shown to the EP; the member stays blocked | built · live (T48; DF-06) |

Not-allowed: a walled engagement answers 404. A member sees only their own confirmation actions; staff financial details are never shown to others.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET …/independence` · `GET …/independence/rotation` | summary, banner reasons, rotation | `independence.read` | team; quality partner `in_scope` |
| write | `POST …/independence/confirm` · `…/decline` | self only; 409 `not_self` | `independence.confirm` | team members for themselves; agent and system deny |
| write | `POST …/independence/reminders` | `{user_ids}`; sent by the person clicking | `independence.remind` | partner, manager |
| read/write | `GET/PUT …/independence/nas[/{service_code}]` | NAS rows, SKE designee (attest only) | `nas.evaluate` | partner, manager; the decision reserved to the EP |
| write | `POST …/independence/breaches` · `…/breaches/{id}/events` | log, evaluate, TCWG communicated, remediated | `independence.breach_manage` | partner, manager, quality partner |
| write | `POST …/independence/conclude` | `{option, safeguards}`; 409 `independence_preconditions_unmet` | `independence.conclude` | engagement partner, `mfa_recent`; human-only |
| read | `POST /v1/conflict-checks` · `GET …/{id}` | redacted walled matches | `conflict.run` | firm admin, partner, manager |

## Status
`independence_confirmation`: Requested (ring + amber) · Confirmed · Declined. Conclusion options: Independent · Independent with safeguards · Not independent. Pending is never red.

## Copy
| Key | String |
|---|---|
| `subbar.count` | "{confirmed} of {total} confirmed" |
| `conclude.button` · `conclude.reserved` | "Conclude…" · "Reserved to {partner}" |
| `conclude.title` | "Conclude engagement independence?" |
| `conclude.options` | "Independent" · "Independent with safeguards" · "Not independent" |
| `concluded.pill` | "Concluded · {partner} · {date}" |
| `e.banner` | "Confirm your independence for {engagement}" |
| `e.statements` | "I have no financial interest in the Northwind Robotics 401(k) Plan or Northwind Robotics, Inc." · "No immediate family member works in a key position at the plan sponsor or its service providers." · "I am not a participant in the plan." (the statement version is data; these are Northwind's) |
| `e.confirm` · `e.toast` | "Confirm" · "Independence confirmed · {date}, {time}" |
| `g.banner` | "Breach logged — evaluate, communicate to TCWG, remediate" |
| `reminder.send` | "Send reminder" |
| `nonAttest` | "Non-attest client: no SKE designation required" |

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Conclude…" | SHL-11 (local `DecisionDock` until P-04 promotes it) | planned (P-04) |
| Engagement name | ENG-02 | planned (P-07-T20) |
| Team row | ENG-05 | planned (P-07-T39) |
| Harborline "Not adverse" popover → Calloway | CLI-02 | planned (P-07-T19) |

Inbound: CLI-02 ("Independence 4 of 5 →"), ENG-05 (blocked assignee, chips), SHL-12 ("Why?" on a blocked sign-off), HOME-04 (Ana's flag), CLI-07 (continuance NAS line), ENG-13 (team chips). All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-08 acceptance: four of five confirmed before Ana, five of five after; only Ana confirms for Ana.
- CLI-08 acceptance: only Margaret Okonkwo concludes; the agent never does.
- CLI-08 acceptance: Ana Cruz can open the engagement but is blocked from assignment and sign-off until she confirms (G2 v2).
- CLI-08 acceptance: a breach banner stays until its evaluation, TCWG communication and remediation are recorded.

## Figures
CLI-08 "4 of 5" before Ana and "5 of 5" after; the confirmed team equals AUD-02's rail (seed test).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, anyone confirming on another's behalf, agent-concluded independence, red for "pending", showing staff financial details to other users.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| declined | An undesigned "Declined with a note" state: the note goes to the EP and the member stays blocked | Undesigned client and engagement states | DF-06 |
| reminder | "Send reminder" is sent by the person clicking from the firm's template, not by a "Confirmation chaser agent" | Reminders are sent by a person; no schedule | P-07 §4.5, §4.8; DEC-64 |
| g2 | The banner's "no assignment or sign-off until Ana confirms" applies to attest clients only; Ana can still read | G2 v2 | DEC-39, ADR-164 |
| annual | The drawer's annual confirmation is empty until G-01's ADM-02 section | DEC-91 open; DF-07 | DEC-91 |
| served | What the live summary does not serve reads in its place: "Annual firm confirmation" is ✓ (a boolean, no date); "Interests check" is "Statements confirmed" (a member's interests are theirs; staff financial details are never shown to others); the requested line is "Requested · 2 reminders" (no requested date); the SKE designee is ✓ (a contact id, no name); the NAS services are named from Northwind's codes; the Conflicts tab lists the check's matches (no per-name searched rows) and reads the check named by `?check=` | P-07-T41's shapes | DEC-542 |
| pronoun | The pending banner reads "They cannot be assigned … until they do (G2)" (no pronoun data) | Copy for any member | DEC-542 |
| declined-note | The declined state's note is fixture text (no artboard) | DF-06 | DEC-542 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a–g | C | — | |

## Open gaps
None open.
