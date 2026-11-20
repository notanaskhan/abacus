# CLS-04 · Close › Accounts — Prepaid Insurance workpaper

- **Epic / task:** C-01 · C-01-T36, C-01-T42 · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T2 variant (account tree 420 · workpaper 946)
- **Route:** `/closes/$closeId/accounts` behind `closes.engine`
- **Reads:** `GET /v1/closes/{id}/accounts` (tree), the account's schedule and arrangements
- **Writes:** Add arrangement (O2), Export entry… (QC-4); no Post AJE in C-01
- **Persona · clock:** Raj Malhotra · Mon Sep 14, 2026, 9:24 AM CT (b 9:31 AM)
- **Handoff:** `CLS-04 Close Accounts - Prepaid Insurance/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Ties once posted: GL 3,500 vs schedule 2,800 | `a` |
| a2 | Add arrangement (O2 drawer) | `a2` |
| b | Approved 9:31, read-only (no Post AJE; "Record it in QuickBooks; the next sync ties the schedule") | `b` |
| c′ | Recorded in QuickBooks · JE 48214 · found by sync 10:20 (composed read-only twin of c) | `cprime` |
| d | Does not tie: off 60.00 → review issue | `d` |
| e | Detail (register) | `e` |
| f | Bank account selected (opens CLS-05) | `f` |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, e | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-04.spec.ts`) | C-01 §5.4 |
| a2, b, c′, d, f (b and c′ deviate by design, DV-1) | C (report only) | not run | — |
| host | D | — | account tree 420 · workpaper 946 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| Opens SHL-08 · CedarMutual_BOP_2026_declarations.pdf | SHL-08 | designed (handoff link graph) |
| Opens CLS-06 · Prepaid Insurance does not tie | CLS-06 | designed (handoff link graph) |
| GL balance $3,500.00 at Aug 31. The reconciliation opens in CLS-05. | CLS-05 | designed (handoff link graph) |

## Deviations and gaps

- **DV-1 · Read-only.** b shows the approval with no Post AJE control; c′ is composed as the read-only twin of c. b2 (Post confirm) and c (Posted · QBO 48214) are C-02's (W1).
- **C-01-T50.** An explicit zero balance ($0.00) reads at ink-3, the zero dash stays ink-4 (DEC-5745).
