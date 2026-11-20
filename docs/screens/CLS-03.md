# CLS-03 · Close › Intake — Copperleaf August 2026

- **Epic / task:** C-01 · C-01-T35, C-01-T42 · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T9 QueueDetailLayout preset close-review (790 = tree 310 + detail 480 · viewer 576)
- **Route:** `/closes/$closeId/intake` behind `closes.engine`
- **Reads:** `GET /v1/closes/{id}/intake` (the request tree, received files, the summary), capabilities
- **Writes:** Incorporate, Return to client… (reason), Send reminder (a person sends), Upload on behalf
- **Persona · clock:** Raj Malhotra · Mon Sep 14, 2026, 9:24 AM CT (b 9:05 AM)
- **Handoff:** `CLS-03 Close Intake - Copperleaf August 2026/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Pending incorporation | `a` |
| a2 | the cited total lit | `a2` |
| a3 | Return to client… reason picker | `a3` |
| b | Incorporated 9:05, toast "Run 2 started · 9 tasks" | `b` |
| c | Requested · Savings ••4436 (reminder history, Send reminder, Upload on behalf) | `c` |
| d | Questionnaire, 4 of 5 answered by Ben Ashby | `d` |
| e | Upload on behalf (the tree as drop target) | `e` |
| f | Not yet published · September (BD1 from close plan v3) | `f` |
| g | Screening flagged · Amex (R2) | `g` |
| h | Rerunning screening (R2) | `h` |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, b, c, d | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/CLS-03.spec.ts`) | C-01 §5.4 |
| e, f, g, h | C (report only) | not run | — |
| host | D | — | T9 close-review widths 790 = 310 + 480 · 576 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| Linked fulfilments · opens SHL-21 | SHL-21 | designed (handoff link graph) |
| Open citation (SHL-07) | SHL-07 | designed (handoff link graph) |

## Deviations and gaps

- **DV-3 · Summary label.** With `closes.agent` off or the `intake` mode not cleared, the card reads "Totals from the file" over the same code-computed totals and citations, never "Summarized by Accrued Agent".
- **DV-6 · Planned links.** "Linked (n)" counts C5 fulfilments; its target SHL-21 is planned until K-04.
- **DV-7 · Client wording.** "Draft follow-up" opens template wording; Send reminder composes from the POR-20 Reminder template (DEC-74) and a person sends.
