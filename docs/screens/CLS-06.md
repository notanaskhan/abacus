# CLS-06 · Close › Review — Copperleaf August 2026

- **Epic / task:** C-01 · C-01-T38, C-01-T42 · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T9 close-review (review 790 = queue 310 + detail 480 · register 576)
- **Route:** `/closes/$closeId/review` behind `closes.engine`
- **Reads:** the close's issues and notes, the register beside the selected issue
- **Writes:** Resolve (required note, optional evidence, optional Propose AJE), Reopen, Ask client… (template wording)
- **Persona · clock:** Raj Malhotra · Mon Sep 14, 2026, 9:24 AM CT (c 1:12 PM, d 1:20 PM)
- **Handoff:** `CLS-06 Close Review - Copperleaf August 2026/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Default: Sound Electric $3,200 selected; register at check #2285 | `a` |
| a2 | Resolve dialog | `a2` |
| b | Reconciliation · #2281 ("Ask client…") | `b` |
| c | Client answered 1:12 PM (Ben Ashby's reply and SoundElectric_INV-SE-1187.pdf) | `c` |
| d | Resolved 1:20 PM (badge 6, Reopen) | `d` |
| e | Notes tab (4 notes, never counted) | `e` |
| f | Show resolved (Shopify duplicate, RM Sep 8) | `f` |
| g | Empty: "No open issues." | `g` |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, e, g | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-06.spec.ts`) | C-01 §5.4 |
| a2, b, c, d, f | C (report only) | not run | — |
| host | D | — | T9 close-review widths 790 = 310 + 480 · 576 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| Opens CLS-05 · Operating Checking ••4410 reconciliation | CLS-05 | designed (handoff link graph) |
| Opens CLS-13 · 1099 / W-9 tracker · Sound Electric Contractors | CLS-13 | designed (handoff link graph) |
| Opens CLS-03 · Intake · Sound Electric invoice request | CLS-03 | designed (handoff link graph) |
| Opens CLS-04 · Accounts · Shopify Clearing | CLS-04 | designed (handoff link graph) |

## Deviations and gaps

- **DV-6.** The "Issues ⇕" picker's Adjustments target is CLS-07 (planned until C-02); "Open thread" targets INB-04 (planned, N-03), so the reply shows on the question.
- **DV-7.** "Ask client…" opens template wording with code facts; agent-drafted client text waits on ADR P-25.
