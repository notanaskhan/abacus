# AUD-16 · Misstatements & adjustments (AJEs, RJEs, SUM)

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/misstatements` (an AUD-02 cockpit section; `?screen=AUD-16&st=<letter>` in fixture builds) |
| Template and host frame | T6 workbook in the T2 cockpit · `Wave 2 - Audit Completion.dc.html#aud16` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-16 …/` |
| Epic and tasks | A-06 · stubs T05 · C8 service T09, T10 · SUM T12 · screen T22 · parity T36 · contract written by A-06-T38 |
| Manifest status | planned |
| Entitlement | `assurance_completion` (A-06-T37, DEC-2714) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Thu Sep 24, 2026 | SUM: projected 35,300, accrued 13,050, iron curtain 22,250 | fixture |
| b | hannah-leclerc | Thu Sep 24 | threshold policy; AJE-1, RJE-1, PAJE-1, PAJE-2 proposed | fixture |
| b2 | hannah-leclerc | Thu Sep 24 | a within-threshold batch approved by a named person | fixture |
| c | hannah-leclerc | Thu Sep 24 | approve and send: the 10-second Undo | fixture |
| d | hannah-leclerc | Fri Sep 25 | client decisions back (approved; declined with reason) | fixture |
| e | margaret-okonkwo | Fri Sep 25 | SUM concluded on SHL-11 | fixture |
| f | hannah-leclerc | Fri Sep 25 | passed adjustments (SUM) | fixture |
| off | hannah-leclerc | — | no `assurance_completion` entitlement: C-20 (DEC-2714) | live |

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET …/proposed-entries`, `/adjusted-tb`, `/sum` | C8 shapes | `proposed_entry.read` |
| write | `POST /v1/proposed-entries/send` | held C18 send (grant) | `proposed_entry.send_to_client` (fresh MFA) |

## Status
`proposed_entry`, `sum_snapshot`.

## Copy
"Summary of uncorrected misstatements", "Passed adjustments (SUM)", "Within threshold" (firm side only; never on the portal). Every word comes from the screen's `copy.ts`, verbatim from the handoff.

## Links
| From | To (manifest builder) | Planned or live |
|---|---|---|
| Opens AUD-01 · all audits | AUD-01 | per manifest |
| Opens AUD-02 · audit cockpit | AUD-02 | per manifest |
| Opens SHL-12 | SHL-12 | per manifest |
| Opens AUD-03 · source documents | AUD-03 | per manifest |
| Opens AUD-15 with this finding selected | AUD-15 | per manifest |
| Opens SHL-11 · reserved to Engagement Partner | SHL-11 | per manifest |
| Opens AUD-21 · rep letter attachments | AUD-21 | per manifest |
| Opens AUD-17 · review notes | AUD-17 | per manifest |

The designed links of AUD-16 in `handoff-links.json`, as `link-contract.test.ts` reads them.

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
