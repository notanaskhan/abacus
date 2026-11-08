# AUD-20 · Financial statements & disclosure checklist

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/fs-disclosure` (an AUD-02 cockpit section; `?screen=AUD-20&st=<letter>` in fixture builds) |
| Template and host frame | T10 structure + paper inside the T2 cockpit · `Wave 2 - Audit Completion.dc.html#aud20` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-20 …/` |
| Epic and tasks | A-06 · statements T19, T25 · render T29 · screen T30 · tests T33, T34 · parity T36 · contract written by A-06-T38 |
| Manifest status | fixture |
| Entitlement | `assurance_completion` (A-06-T37, DEC-2714) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Fri Sep 25, 2026 | 63 of 63 lines tie; checklist 97 + 45 + 0 = 142 items | fixture |
| a2 | hannah-leclerc | Fri Sep 25 | Send draft to client… (O3); sending waits for R-02's C10 (S31) | fixture |
| b | hannah-leclerc | 10:40 AM | 62 of 63: benefits off 14,850; the card opens AUD-16 at RJE-1 | fixture |
| c | hannah-leclerc | Fri Oct 2, 3:00 PM | drafting: skeleton and the agent's line | fixture |
| d | hannah-leclerc | Fri Sep 25 | client preview: DRAFT watermark, no checklist, no sources | fixture |
| e | hannah-leclerc | Thu Oct 8, 11:00 AM | approved by management | fixture |
| f | hannah-leclerc | Fri Sep 25 | Note 3's fair-value hierarchy reads 16,500,000 | fixture |
| off | hannah-leclerc | — | no `assurance_completion` entitlement | live |

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/statement-documents/{id}`, `/checklist` | statements contract | `statement.read` |
| write | `PUT …/checklist/{item}` (N/A needs a reason: 422 `reason_required`) | `ChecklistAnswerIn` | `statement.edit` |
| write | `POST …/send-draft` (501 until R-02's C10) | `StatementSendDraftIn` | `statement.send_draft` |

## Status
`statement_document`, `disclosure_checklist_item`.

## Copy
"Send draft to client…", "Send draft", "Sending starts when client delivery is switched on.", "DRAFT". Every word comes from the screen's `copy.ts`, verbatim from the handoff.

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
