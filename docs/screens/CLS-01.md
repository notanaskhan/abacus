# CLS-01 · Closes index — August 2026

- **Epic / task:** C-01 · C-01-T33 (TASK-8035) · SPEC-655 AC-1 to AC-6
- **Template:** T1 (filter bar · status tiles · full-width table), reusing TPL-01's frame
- **Route:** `/closes?period&status&preparer&reviewer&attest&q` behind `closes.engine`
- **Reads:** `GET /v1/closes` (rows, tiles, summary; through `visible()` and walls) and
  `GET /v1/closes/running` (the running pill and popover)
- **Persona · clock:** Priya Raman (Partner, reviewer on closes) · Mon Sep 14, 2026, 9:24 AM CT
- **Handoff:** `CLS-01-closes-index-portfolio.md`, `CLS-01-revision.md` (Board, wave 5)

## States → data

| State | Data condition | Scenario |
|---|---|---|
| a default | 22 closes, tiles 3 · 11 · 5 · 3, "22 closes · 51 open issues · 2 past due · 3 running" | `a` |
| b filtered | the In progress tile: 11 rows, "Showing 11 of 22" | `b` (`status=in_progress`) |
| c past due | Status │ Past due: Copperleaf (4 days), Bluebird Bakery (2 days) | `c` (`status=past_due`) |
| d attest | Attest │ Attest clients: "No attest clients this period" | `d` (`attest=true`) |
| e loading | `GET /v1/closes` never answers: skeleton tiles and rows | `e` |
| f row hover | C11's row with "···" (Open · Start run · View plan) | `f` (interact `hoverRow("C11")`) |
| G–I board | List · Board toggle and the Board (revision) | hidden while `board.enabled` is off |

## Parity

Tier C on a, b, c, e (locked by C-01-T50). Hover and open-menu states are out of pixels except f,
which runs through its interact script.

## Deviations

- **DV-a (DEC-5019).** The reconciled percentage is code's, half up from the two counts; three
  artboard cells (Kettle & Kiln 66%, Maple & Main 44%, Northfield 58%) read 67%, 43% and 57%.
- **DV-b (QC-7).** Copperleaf is due Tue Sep 8 (BD5) and Bluebird Bakery Thu Sep 10 (BD7), so
  the due cells read those dates; the past-due days (4 and 2, business days) are the artboard's.
- **DV-c.** Row order: the fixtures keep the artboard's order (C1 … C22); the live service
  orders rows by client name.
- **DV-d.** "1099 / W-9 tracker ›" targets CLS-13 (planned); "+ New close…" opens ENG-03 when
  the route offers it.
