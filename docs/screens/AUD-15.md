# AUD-15 · Findings register (issues & deficiencies)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/findings` (an AUD-02 cockpit section; `?screen=AUD-15&st=<letter>` in fixture builds) |
| Template and host frame | T2 audit split (rail 330 · canvas 1036) · `Wave 2 - Audit Completion.dc.html#aud15` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-15 …/` |
| Epic and tasks | A-06 · stubs T05 · findings service T11 · screen T18 · tests T26 · parity T36 · contract written by A-06-T38 |
| Manifest status | planned |
| Entitlement | `assurance_completion` (A-06-T37, DEC-2714) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Fri Sep 25, 2026, 10:40 AM | 9 findings in bands 1 + 2 + 1 + 5; badge 3 (proposed + exception for resolution) | fixture |
| b | hannah-leclerc | 10:40 AM | a finding drawer open with its deficiency severity card | fixture |
| c | margaret-okonkwo | Fri Sep 25 | severity decided on SHL-11 by the EP | fixture |
| d | hannah-leclerc | 10:40 AM | an exception routed from EBP-04 (F-01 on EBP-04!F31) | fixture |
| e | hannah-leclerc | 10:40 AM | client communication drafted (a person sends) | fixture |
| f | hannah-leclerc | 10:40 AM | empty register | fixture |

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/work-items/{work_item_id}/findings` | `FindingsOut` | `finding.read` |
| write | `POST …/findings/{id}/request-severity` | C3 card `deficiency_severity` | `finding.request_severity` |

## Status
`audit_finding`, `deficiency`.

## Copy
"Findings", "Awaiting a decision", band and severity words from the status registry. Every word comes from the screen's `copy.ts`, verbatim from the handoff.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 | per manifest |
| Opens AUD-02 · audit cockpit | AUD-02 | per manifest |
| Opens AUD-10 | AUD-10 | per manifest |
| Opens AUD-16 | AUD-16 | per manifest |
| Opens AUD-17 · review notes | AUD-17 | per manifest |
| Opens SHL-08 · PayGrid Contribution Detail 2025.xlsx at pay date 12/26/2025 | SHL-08 | per manifest |
| Opens EBP-04 with cell F31 selected | EBP-04 | per manifest |
| Opens AUD-09 with D5 selected | AUD-09 | per manifest |

The designed links of AUD-15 in `handoff-links.json`, as `link-contract.test.ts` reads them.

## Parity, accessibility and keyboard
Tier C report (fixture build); axe and keyboard in `apps/web/e2e/screens/AUD-completion-a11y.spec.ts` (A-06-T36); journey steps in J03, J04, J05 and J22 (A-06-T35). Tier C locks wait for measured baselines.

## Deviations
| ID | Deviation | Why |
|---|---|---|
| DV-1 | Clocks are artboard-scoped: each scenario carries its own demo clock | the handoff renders boards at different moments |
| DV-2 | R2 links to screens not built yet stay planned | the links rule (DEC-347) |
| DV-3 | L5 (the EQR's level) is read-only here; the EQR signs nothing on these papers | SQMS 2, A-07 F1 |
| DV-4 | Passed adjustments are numbered PAJE-1, PAJE-2 | the handoff's revision; DEC-2391 |

## Consumer notes
| Consumer | What it reads from this screen's services |
|---|---|
| A-05 | EBP exceptions arrive as C3 issues with cell anchors (AUD-15); Note 8 lands on AUD-20 |
| A-07 | G5 (notes cleared, papers signed), the SUM for the representation letter, `fs.approved_by_management` |
| R-02 | C18 kinds `proposed_entry`, `uncorrected_misstatements`, `fs_draft`; C10 drafts from AUD-20 |
| C-02 | packages read the C8 entries; nothing posts to a client ledger |
| T-05 | the adjusted TB layers (C9) after C8 entries |
| A-09 | group findings roll up through AUD-15's register |
| A-10 | the statements studio links stay hidden until A-10 |
| P-10 | runs on these papers show in the dock; the agent proposes, never decides |

Contracts: `docs/contracts/completion.md`, `docs/contracts/adjustments.md`, `docs/contracts/portal-approvals.md`, `docs/contracts/deliverables.md`.
