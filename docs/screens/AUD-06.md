# AUD-06 · Trial balance & leadsheets

| Field | Value |
|---|---|
| Route and params | No path of its own: the AUD-02 cockpit's Trial Balance canvas, `/audits/$auditId?section=trial_balance` (`?dock=viewer` for the linked trust report), behind `ledger.tb_workpaper` (DEC-314; the C9 v1 view by layer and leadsheet by area are live since A-02-T10, DEC-440). Artboards: `/components/screens/AUD-06?st=a…h`, plus `empty`, `newer`, `loading`, `error`, `not_allowed` |
| Template and host frame | T2 audit split inside the AUD-02 cockpit: rail 330 · workpaper 536 · viewer 490 · `Wave 2 - Audit Planning.dc.html#aud06` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-06 Trial balance and leadsheets/` (README.md, spec.md, revision.md R2; revision wins) · HANDOFF_VERSION 2026-10-17 |
| Epic and tasks | A-02 · contract A-02-T03 (C9 v1, `docs/contracts/c09-ledger.md`); scenarios A-02-T05 (TASK-1215); a and c A-02-T09 (TASK-1286, this file); read model A-02-T10; b, d, e, g, h A-02-T14; ties and issue link A-02-T17; Open in Excel A-02-T22; live swap A-02-T24 |
| Manifest status | planned (`routes/manifest/aud.ts`): built on fixtures as a cockpit canvas; turns live with A-02-T24 |

Code: `apps/web/src/screens/AUD-06/{TrialBalance.tsx, copy.ts, artboard.tsx, scenarios.ts}`; the
cockpit wiring in `screens/AUD-02/index.tsx`; data `fixtures/scenarios/AUD-06.ts`,
`fixtures/seed/aud06.ts` (A-02-T05), `fixtures/seed/trust.ts` (the Harborline document, P-03-T14).

## States
| Artboard | Viewer (persona) | Clock | Snapshot | Data condition that produces it | Status |
|---|---|---|---|---|---|
| a | hannah-leclerc | Mon Sep 14, 2026, 2:30 PM CT | E0 | Northwind PY2025 v1 adopted 10:02 AM by Marcus Delaney; fund lines L1 + L2 (HL); three ties; KRS Target 2045 selected, its Harborline row lit in the Viewer dock | built (T09, fixture) |
| b | hannah-leclerc | 2:30 PM (9:26 AM state) | E0 | The agent's draft: outlined agent ticks, no initials | built (T14, fixture): header pill "Draft · Accrued Agent" when every mark is the agent's; the rail's "Complete · 9:26 AM" is the cockpit provider's (A-01) |
| c | hannah-leclerc | 2:30 PM | E0 | BrokerWindow EOY 1,606,560.00: "off 1,560.00", red ink, Flag linked to an issue | built (T09, fixture) |
| d | hannah-leclerc | Tue Oct 6, 2026, 2:30 PM | E0 + AJE-1 | Final layer: AJE column, tag AJE-1, net assets 16,861,000.00 | built (T14, fixture; live when A-06 registers its adjustment source) |
| e | hannah-leclerc | 2:30 PM | E0 | Leadsheets tab: Investments PY · CY · Δ · Δ% | built (T14, fixture): statement grammar, the area picker when the lines name more than one area |
| f | hannah-leclerc | 2:30 PM | E0 | `?ov=signoff:trial_balance:<tb>:L2` | SHL-12 is P-04-T48; "Sign off…" is planned |
| g | caleb-dunn | Mon Sep 14, 2026, 4:05 PM CT | E1 | Harlow & Pike Manufacturing, Interim 8/31/2026, whole dollars | built (T14, pane only until A-09): chip "TB: Interim · 8/31/2026", one column "Interim 8/31/2026", "Balances to 0" tie; the entity strip in dev and gallery builds only (planned facts, AUD-33) |
| h | hannah-leclerc | Mon Nov 9, 2026, 10:15 AM CST | — | Granite Peak FY2026, Final layer; Hand off to tax (hidden) | built (T14, pane only): "Hand off to tax…" drawn disabled with its tooltip in dev and gallery builds only (AUD-38 planned); absent in production |
| Empty | simone-baptiste | E0 | | Granite Peak with a pulled snapshot and no TB of record | "No trial balance yet"; adopt actions A-02-T24 |
| Newer | simone-baptiste | E0 | | v1 adopted, one newer pull (2 lines changed) | banner A-02-T24 |
| Loading | simone-baptiste | E0 | | the TB list never answers | skeleton |
| Error | simone-baptiste | E0 | | the TB list answers 500 | C-20 error with Retry |
| Not allowed | cole-hart | E0 | | walled from Granite Peak: every read 404 (INV-3) | walled ViewState, no hint |

## API
| Read or write | Endpoint | Shape | Matrix action | allowed_actions and read-only reasons per role |
|---|---|---|---|---|
| read | `GET /v1/engagements/{id}/trial-balances` | `TrialBalancesOut` | `trial_balance.read` | as C9 |
| read | `GET …/trial-balances/{tb}/layers/{layer}` | `TbLayerViewOut` (groups, lines, ticks, flags, named totals, balance, provenance, `layers_available`, `allowed_actions`) | `trial_balance.read` | `trial_balance.annotate` (Edit), `sign_off.review` (Sign off…), `trial_balance.export` (Open in Excel); 409 `layer_unavailable` |
| read | `GET …/trial-balances/{tb}/checks` | `TieOutCheckOut[]` (status, difference, rollforward `formula`) | `trial_balance.read` | — |
| read | `GET …/trial-balances/{tb}/leadsheets/{area}?layer=` | `TbLeadsheetAreaOut` | `trial_balance.read` | — |
| read | `GET /v1/citations/{citation_id}` | `CitationV2Out` (`match_id`, `source.evidence_version_id`) | `citation.read` | the linked row: the line's typed citation, never a guessed region (SPEC-333 AC-8) |

## Status
`trial_balance_layer` (Unadjusted · AJE · RJE · Final), `trial_balance_label` (the chip "TB: Standard"), `tie_out_tally` (`tie`, `off {amount}`, `pending`).

## Copy
`screens/AUD-06/copy.ts`: header pills, tabs, columns, the AC-4.1 tooltip "Adjustments arrive with Findings & adjustments", the caption grammar of A-02 §3.1 ("Imported by ‹person› from a NetSuite export, ‹date›, ‹time›"), the chip and tick popovers of spec INTERACTIONS, "Draft · Accrued Agent", "No trial balance yet".

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Source Docs | AUD-03 | planned (disabled, dev and gallery only) |
| Sign off… | SHL-12 overlay | planned (P-04-T48) |
| Edit | inline annotations (P-04 path, A-02-T35) | planned |
| Open in Excel | export.xlsx | planned (A-02-T22) |
| A line | the cockpit's Viewer dock (SHL-08 ViewerPane) | live in fixture mode |
| "All audits" breadcrumb | AUD-01 | planned until A-01-T11 |
| Client name in the header | AUD-02 cockpit | planned until A-01-T12 |
| Consolidated TB (multi-entity) | AUD-33 | planned |
| AJE-1 on an adjusted line | AUD-16 | planned |
| Investments and certification | EBP-06 | planned (EBP wave) |
| Distributions and loans | EBP-05 | planned (later wave) |

## Acceptance
- AUD-06a and AUD-06c pass their Vitest scenarios (`TrialBalance.test.tsx`, `AUD-06.test.tsx`).
- Clicking KRS Target 2045 lights its trust-report row (the region's match light is the 360 ms fade).
- No code path sums a column in the browser (a source test on `TrialBalance.tsx` and `artboard.tsx`).
- R2: the TB label chip; Northwind a–f keep their figures; AJE-1 foots 33,540.00 + 15,060.00 = 48,600.00 (A-02-T05 scenario test).

## Figures
Six funds 14,895,000.00 / 12,683,000.00; investments 16,500,000.00 / 13,940,000.00; net assets 16,812,400.00 / 14,228,500.00; loan rollforward 288,500.00 + 96,200.00 − 57,450.00 − 14,850.00 = 312,400.00; c off 1,560.00. Proved on the fixtures by `AUD-06.test.tsx` and on screen by `TrialBalance.test.tsx`.

## AVOID
Gradients, emoji, saturated blue, heavy shadows, invented colours, truncated numbers, amounts without cents in this workpaper, unlisted funds, totals that do not foot, initials on an agent's tick, editing ledger snapshots, the agent approving entries.

## Deviations
| ID | What differs from the handoff | Why | Decision recorded |
|---|---|---|---|
| D1 | The named totals (Total mutual funds & CITs, Total investments, Net assets) follow the lines as a totals block instead of sitting between them | C9 v1 `TbNamedTotalOut` carries no position; the browser does not infer one | DEC-395 |
| D2 | Northwind's view also lists the net-asset and change accounts (3000–5200) under their group | the C9 view is the whole trial balance; the handoff draws the statement of net assets part | DEC-342 (fixture groups) |
| D3 | The caption reads "Unadjusted. Imported by Marcus Delaney from the Accrued trial balance template, Sep 14, 10:02 AM." without "Fund lines reviewed by …" | C9 v1 provenance has no review facts; A-02-T10 adds the caption | DEC-395 |
| D4 | The Harborline document is the P-03 fixture's (rows on page 2 of 3), not "1 / 1" | one seeded document for SHL-08 and AUD-06 | DEC-395 |
| D5 | Edit, Sign off…, Source Docs and Open in Excel are drawn disabled in dev and gallery builds and absent in production | their targets are planned (P-04-T48, A-02-T22, AUD-03) | chapter 04 §2.1 rule 4 |
| D6 | g's entity strip and h's Hand off to tax… read facts the artboard passes (`OPENS[state].planned`), not the C9 view, and render only in dev and gallery builds | C9 v1 carries no entity group or tax hand-off; their targets (AUD-33, AUD-38) are planned | DEC-440; A-02-T14 |
| D7 | b's draft pill reads "Draft · Accrued Agent" from the marks (every tick the agent's); C9 v1 has no pre-adoption draft shape | the view carries tick actors, not a draft flag | DEC-342 |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| g | C (threshold 0.20, maxDiffPixelRatio 3 %) | 2.20 | locked (A-02-T31, measured Thu Oct 29, 2026) |
| a, c | C | 2.71 / 2.86 | locked (DEC-838, measured Fri Oct 30, 2026) with the Viewer dock, the rail and the audit bar masked: the dock per D4, the rail and bar as AUD-02's chrome, whose unmasked locks are A-01-T33's (DEC-909); 4.25 / 4.40 with the dock alone |
| b, e | C | 2.93 / 2.53 | locked (DEC-838, measured Fri Oct 30, 2026) with the Viewer dock masked (D4) |
| d | C | 4.59 | report-only, the dock masked (3.11 with the rail and bar masked too) |
| f | C | 10.34 | report-only, the dock masked: the artboard records `?ov=signoff:…` but does not draw the sign-off dialog the handoff shows |
| h | — | — | the handoff's AUD-06h is a 2880 × 580 strip (the pane detail), not a window; no window baseline, unmeasured |
| host | D | — | audit bar 59, rail 330, workpaper 536, viewer 490 on a, c and e (`tier-d-connections.spec.ts`): the Trial Balance row widens the dock to `--ev-w` as AUD-03 does (DEC-838) |

## Open gaps
- The rail's "Prepared · MD" sub-line for the Trial Balance row is the cockpit provider's (A-01); the fixture rail reads the run grammar.
- The fixture citations reuse the Harborline rows' match ids under the lines' own citation ids (`aud06Citations`).
