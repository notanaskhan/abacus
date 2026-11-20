# CLS-05 · Close › Reconciliation — Operating Checking ••4410, Aug 31, 2026

- **Epic / task:** C-01 · C-01-T37, C-01-T42 · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T3 EvidenceTriad two-pane (rec sheet 876 · statement viewer 490)
- **Route:** `/closes/$closeId/accounts/$accountRef` behind `closes.engine`
- **Reads:** the account's reconciliation, the statement and the register
- **Writes:** Propose AJE (the agent drafts in O2, a person proposes), sign-off through SHL-12 L1
- **Persona · clock:** Raj Malhotra · Mon Sep 14, 2026, 9:24 AM CT (c 10:05 AM, d 2:31 PM)
- **Handoff:** `CLS-05 Close Reconciliation - Operating Checking/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Difference $0.00 with 2 open items (refund line lit) | `a` |
| a2 | Propose AJE (agent draft of AJE-06 in O2, human Propose) | `a2` |
| a3 | Sign-off blocked (SHL-12 L1, reasons listed) | `a3` |
| b | Difference ≠ 0 · Run 1 (Sep 2; off 380.00; Aug 27 line Unmatched) | `b` |
| c | Entry proposed 10:05 (AJE-06 proposed · Review required) | `c` |
| d | Reconciled and signed 2:31 PM, read-only | `d` |
| e | Loading pages | `e` |
| f | Detail (August register beside the statement) | `f` |
| g | Savings ••4436 (statement still requested; empty viewer) | `g` |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, f | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-05.spec.ts`) | C-01 §5.4 |
| a2, a3, c, d (DV-2), e, g | C (report only) | not run | — |
| host | D | — | T3 two-pane 876 · 490 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| Opens SHL-08 · Square payout file · Aug 31 transfer | SHL-08 | designed (handoff link graph) |

## Deviations and gaps

- **DV-2 · d.** "AJE-06 posted (QBO 48218)" reads "AJE-06 recorded in QuickBooks · JE 48218".
- **DV-6.** "Review required" opens SHL-10 (`?ov=approve:<proposalId>`) until CLS-07 lands in C-02.
- **C-01-T50.** Explicit zero figures read at ink-3 (DEC-5745).
