# AUD-17 · Review notes & sign-off matrix

| Field | Value |
|---|---|
| Route and params | `/audits/$auditId/review-notes` (an AUD-02 cockpit section; `?screen=AUD-17&st=<letter>` in fixture builds) |
| Template and host frame | T2 audit split · `Wave 2 - Audit Completion.dc.html#aud17` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/AUD-17 …/` |
| Epic and tasks | A-06 · notes and matrix T15, T16 · screen T24 · tests T31 · parity T36 · contract written by A-06-T38 |
| Manifest status | fixture |
| Entitlement | `assurance_completion` (A-06-T37, DEC-2714) |

## States
| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | hannah-leclerc | Fri Sep 25, 2026 | open notes and the sign-off matrix (13 of 26 rows drawn, DEC-2391) | fixture |
| b | marcus-delaney | Fri Sep 25 | a note responded | fixture |
| c | hannah-leclerc | Fri Sep 25 | a note cleared | fixture |
| d | hannah-leclerc | Fri Sep 25 | a paper changed after sign-off (stale chip) | fixture |
| e | hannah-leclerc | Fri Sep 25 | Reopen on a cleared note (A-06-T24) | fixture |
| f | hannah-leclerc | Fri Sep 25 | No review notes. | fixture |

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET …/review-notes`, `/sign-off-matrix` | C3 notes and sign-offs | `workpaper.read` |
| write | `POST /v1/review-notes/{id}/reopen` | C3 | `review_note.reopen` |

## Status
`review_note`, `sign_off`.

## Copy
"Sign-off matrix", "No review notes.", L1 to L4 level words. Every word comes from the screen's `copy.ts`, verbatim from the handoff.

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
