# POR-11 · Close requests & transaction questions — Copperleaf August 2026

- **Epic / task:** C-01 · C-01-T41, C-01-T51 · SPEC-655 · contract written in C-01-T55 (TASK-8757)
- **Template:** T7 PortalLayout split (rail 336 + main 1030) + T7-M 390
- **Route:** inside the portal's Documents (its own path is planned); gallery `/components/screens/POR-11`
- **Reads:** `GET /v1/portal/closes/{close_id}/questions` (client fields only: question_id, client_wording, context_line, status, asked_by_name, asked_at, answered_at), the period's requests
- **Writes:** `POST /v1/portal/questions/{question_id}/answer`, uploads, Mark as Done
- **Persona · clock:** Ben Ashby (portal) · Mon Sep 14, 2026, 9:24 AM CT (c 1:15 PM)
- **Handoff:** `POR-11 Close requests and transaction questions/` (folder not on this machine; states from C-01 §2)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a | Default: 9 requests, 7 received, 2 open; 3 questions from Raj Malhotra | `a` (built) |
| b | Answering: check #2281 in the POR-04 question sheet | `b` (built) |
| c | Answered 1:15 PM | `c` (built) |
| d | Savings uploaded 11:05 AM (Overdue clears) | not built |
| e | All done: Mark as Done; "Raj Malhotra will finish the August close" | not built |
| f | July 2026 closed period | not built |
| g | Empty September | not built |

## Parity
| Artboard | Tier (A/B/C/D) | Diff % | Notes |
|---|---|---|---|
| a, e, g | C (locked; C-01-T50) | not run (handoff baselines not on this machine; axe light and forced colors in `e2e/screens/POR-11.spec.ts`) | C-01 §5.4 |
| b, c, d, f | C (report only) | not run | — |
| host | D | — | T7 rail 336 + main 1030; T7-M 390 |

## Links

The designed links of the handoff link graph (link-contract rule 5); each is wired when its target is built (DV-6 names the planned ones).

| From | To | Status |
|---|---|---|
| “Answer…” on check #2281 opens the question sheet (POR-04 frame e shows Sound Electric) | POR-04 | designed (handoff link graph) |

## Deviations and gaps

- **DV-8 · Build.** Rebuilt on R-01's C-16 Request kit and the POR-04 question variant, not the handoff's inline drawing.
- **QC-1.** Front Range ••4410 and ••4428 statements arrive by bank feed, so they have no client rows.
- **INV-4.** No client response carries a firm-only field; the page never shows the firm's workflow words (C-01-T50 spec, POR-11.test.tsx).
- **Gap.** d–g have no fixture scenario yet; they are listed here and in the parity table, unmeasured.
