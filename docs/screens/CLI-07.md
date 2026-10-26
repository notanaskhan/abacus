# CLI-07 · Acceptance & continuance

| Field | Value |
|---|---|
| Route and params | `/clients/$clientId/acceptance/$engagementId` (P-07 §5). Artboards: `/components/screens/CLI-07?st=a…g` |
| Template and host frame | T2 `RecordCockpit` with rail and the decision dock (SHL-11 grammar, local `DecisionDock`) · `Wave 3 - Home & Clients.dc.html#cli07` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/CLI-07 Acceptance and continuance - Estate of Walter Thornbury/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-21 |
| Epic and tasks | P-07 · contract P-07-T23 · stub P-07-T29 · live P-07-T35 · AC suite P-07-T38 · screen P-07-T46 · gate kinds P-07-T47 |
| Manifest status | live (`routes/manifest/cli.ts`, P-07-T46): a, b, d, e, f over the live routes; c and g on fixtures; links to CLI-02 wired in `routes/firm/clients.tsx` (DEC-195, DEC-431) |

Code (P-07-T46, TASK-1328): `src/screens/CLI-07/{index.tsx, scenarios.ts, copy.ts, CLI-07.test.tsx}`, `src/domain/engagements/{DecisionDock.tsx, acceptance.ts}`, `src/fixtures/{seed,handlers}/acceptance.ts`, `src/fixtures/scenarios/CLI-07.ts`, `e2e/screens/CLI-07.spec.ts` (axe), the route in `src/routes/firm/clients.tsx` and the gallery artboard. Flag `engagements.acceptance_v2`. Spec: SPEC-332 AC-1 to AC-12. Built per DEC-431.

## States

7 artboards (a–f spec.md; g revision R2).

| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | daniel-reyes | Mon Sep 14, 2026, 9:40 AM CT | E0 | Thornbury record Awaiting partner; three flags, Moderate risk | built · live (T46) with human-authored flags; the pre-screen meta fixture-only |
| b | samuel-ito | Fri Sep 11, 4:10 PM | E0 − Grace's check | Draft: "Manual check · estate not yet in CCH Axcess Practice"; dock "Not ready for decision — 1 manual check open"; "Send to partner" disabled | built · live (T46) |
| c | daniel-reyes | Fri Sep 11, 4:01 PM | E0 | Pre-screen running: "Accrued Agent is screening · 4 of 9 sections" | built · fixture only (DEC-64) |
| d | daniel-reyes | Mon Sep 14, 9:46 AM | E0 + decision | Decided and locked: "Accepted with conditions · Daniel Reyes · Sep 14, 9:46 AM", three open conditions owned by Samuel Ito | built · live (T46) |
| e | daniel-reyes | Mon Sep 14, 9:40 AM | E0 + decline | Declined: reasons; the engagement shows Declined | built · live (T46) |
| f | margaret-okonkwo | Mon Sep 14, 10:05 AM | E0 | Continuance — FY2026 FS audit · Meridian Tool & Die, Inc.; prior-year history; NAS → CLI-08 | built · live (T46) |
| g | margaret-okonkwo | Thu Oct 1, 2026, 10:40 AM | Oct 1 snapshot | Continuance — FY2027 FS audit · Granite Peak; responsiveness flag "on-time rate 48% (firm 63%)" | built · fixture until I-03 (INS-05) |

Not-allowed: everyone but the engagement partner sees the decide control disabled with "Partner decision". A walled engagement answers 404.

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagements/{engagement_id}/acceptance` | record, answers, checks, flags, decision, conditions | `acceptance.read` | team; quality partner `in_scope` |
| write | `PUT …/acceptance/answers/{section_code}` · `POST …/acceptance/flags` · `…/manual-checks/{section_code}/request\|complete` · `…/send-to-partner` · `…/conditions/{condition_id}/complete` | prepare | `acceptance.prepare` | partner, manager (manual-check completion also client service) |
| write | `POST …/acceptance/risk-partner-review` | `{partner_id}` | `acceptance.request_review` | engagement partner |
| write | `POST …/acceptance/decision` | `{option, rationale, conditions[], seen_version}`; 409 `decision_locked`, `review_required`; 422 `rationale_required` | `acceptance.decide` | engagement partner, `mfa_recent`; agent and system deny; human-only |

## Status
`acceptance_record`: Draft · Pre-screening (fixture) · Awaiting partner · Decided · Declined (DF-06). Engagement pill Prospect → Accepted / Declined. Severity Low · Medium · High; risk Low · Moderate · High.

## Copy
| Key | String |
|---|---|
| `dock.notReady` (b) | "Not ready for decision — {count} manual check open" |
| `dock.send` (b) | "Send to partner" |
| `dock.partnerOnly` | "Partner decision" |
| `dock.options` | "Accept" · "Accept with conditions" · "Decline" |
| `dock.decide` | "Decide" |
| `toast.decided` | "Decision recorded" |
| `decided.pill` (d) | "Accepted with conditions · {partner} · {date}" |
| `decided.letter` (d) | "Draft engagement letter →" |
| `flag.makeCondition` | "Make this a condition →" |
| `review.request` | "Request risk-partner review…" |
| `meta.prepared` (production) | "Prepared by {person} · {date}" |
| `running.card` (c, fixture) | "Accrued Agent is screening · {done} of {total} sections" |
| `g.dock` | "Not ready for decision — questionnaire in progress" |
| `g.rail` | "Client responsiveness" |
| `dock.continuance` (f, g) | "Continue" · "Continue with conditions" · "Discontinue"; details "Proceed to the {period} engagement letter." · "Add conditions from the flags." · "Record reasons; no letter." |
| `dock.question` | "Accept the {client} engagement?" · continuance "Continue the {client} engagement for {period}?" |
| `dock.reserved` | "Reserved to {partner} · Engagement partner. The decision date must precede the engagement letter (G1)." |
| `dock.recorded` (d, e) | "Decision recorded {date} · it can't be edited. The engagement letter follows it (G1)." · "… No engagement letter will be drafted." |
| `dock.labels` | "Rationale" · "Reasons" (Decline) · "Continuance note" (continuance in Draft) · "Conditions" · "{done} of {total} done" · "Owner {person} · Open" |
| `flag.partnerCan` (b) | "{partner} can make this a condition" |
| `risk.summary` | "{n} sections clear ({m} by manual check) · {n} flags · {n} manual check open · conclusion awaiting partner · risk-partner review not required at {rating}" |
| `check.open` (b) | "Manual check open · {section}" |
| `clear` | "Clear sections ({n})" |
| Written for P-07-T46 (DEC-431) | "Request manual check…", "Complete check…", "Mark check done", "Asked of {person} · {date}", "Add flag…", "Request review", "Complete review", source rows "File" / "Request", refusals "Choose an option.", "A rationale is required.", "Add at least one condition.", "This record changed since you opened it. Reload to see the latest.", "The decision is already recorded.", "A risk-partner review must be completed first.", "That person can't take this on here.", "Couldn’t save. Try again." |

Questionnaire sections come from the firm's database template ("Tax engagements v2"), never `copy.ts`; flag text, sources and conditions are data.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| "Draft engagement letter →" ("Opens ENG-04 · engagement letter · Estate of Walter Thornbury") | ENG-04 | planned (N-02) |
| Client name ("Opens CLI-02 · Estate of Walter Thornbury") | CLI-02 | planned (P-07-T19) |
| f NAS line ("Opens CLI-08 · Independence · Meridian Tool & Die, Inc.") | CLI-08 | planned (P-07-T48) |
| g source rows ("Opens INS-05 · Client responsiveness · Granite Peak"; "Opens BND-04 · Granite Peak · overdue only") | INS-05 · BND-04 | planned (I-03, P-06); fixture only |
| Flag source rows | SHL-08 (`?ov=viewer`) | planned (P-03) |
| HOME-02 gate row (inbound once C13 registers) | HOME-02 | planned |

All targets are manifest IDs that `link-contract.test.ts` knows.

## Acceptance
- CLI-07 acceptance (R2): frames a–f, including the Thornbury decision and the Meridian continuance variant, are unchanged.
- CLI-07 acceptance (R2): frame g shows the flag "On-time rate 48% (firm 63%)" with two cited sources.
- CLI-07 acceptance (R2): the decision stays with the engagement partner; the dock is not ready for decision on Oct 1.
- CLI-07 acceptance (R2): the note names Luis Ferrante (Granite Peak's CFO) and no new people.
- CLI-07 acceptance: the decision date is before any letter date (G1 < letter, SPEC-332 AC-11).

## Figures
Gross estate about $16.4M against the 2026 basic exclusion of $15,000,000; Form 706 due Nov 2, 2026, 49 days from Sep 14 (seed data).

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, lorem ipsum, any agent-owned accept or decline control, red full-card backgrounds, risk gauges or scores above 15px, a decision date later than the letter; treating the responsiveness flag alone as a reason to decline; "task" for a to-do.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| flags | Production flags are human-prepared (author Samuel Ito); a/d's "Accrued Agent pre-screened" meta reads "Prepared by ‹person› · ‹date›" when no pre-screen run exists | The AI pre-screen comes later, behind the data boundary | DEC-64, SPEC-332 AC-2 |
| c | The pre-screen running state is fixture-only | As above | DEC-64 |
| recommendation | "Decide requires a rationale when the choice differs from the recommendation" becomes: a rationale is always required | No agent recommendation in production | SPEC-332 AC-7 |
| states | Record states Draft · Pre-screening · Awaiting partner · Decided · Declined | Undesigned states | DF-06 |
| g | Fixture until INS-05 exists | Insights lands with I-03 | P-07 §5 |
| dock | A local `DecisionDock`; no agent recommendation, Reasoning block or "Request more analysis…"; continuance option words from f and g | SHL-11's card is not built; no agent in production | DEC-431 |
| rail and clear lines | A section's rail line and clear line are its answers `summary` and `detail`; the `conclusion` section reads the decision | The record carries no per-section sentence; the template is database content | DEC-431 |
| sources | A flag's source row reads "File" or "Request" (the API carries `{kind, id}` only), no citation count | No source-name read yet | DEC-431 |
| bar meta | "Prepared by ‹preparer› · ‹sent date›"; g reads "Prepared by Hannah Leclerc" (no "Opened by" fact) | The record has no opened-by field | DEC-64, DEC-431 |
| writes | "Request manual check…", "Complete check…", "Add flag…" are added; "Edit answers" and "View answers" are not drawn | Undesigned controls for live routes; no section form yet | DEC-431 |
| engagement pill | The record bar shows the engagement's own status (f reads "Prospect", not "Not started") | The status comes from the engagement record | DEC-431 |

## Parity
| Artboard | Tier (A/B/D) | Diff % | Notes |
|---|---|---|---|
| a b d e f | C | — | mask a/d agent meta in production-variant tests |
| c g | C (fixture) | — | |

## Open gaps
- Source names and citation counts on flag rows wait on a source-name read (P-03, SHL-08).
- The risk-partner picker offers the team candidates; a partner-level filter needs a level on `CandidateOut` (the server already refuses a non-partner).
- Parity (Tier C) and axe are not yet run: `e2e/screens/CLI-07.spec.ts` is written; Playwright was skipped in P-07-T46 (chromium mismatch).
