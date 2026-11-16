---
id: TASK-8301
title: "T-05-T69: entity screens' parity (57 artboards), axe, grammar, Tier D, keyboard suites, INP"
spec: SPEC-651
acceptance_criteria: [AC-13]
risk_zone: green
status: in-review
branch: lo45-t05-t69
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-16
updated: 2026-11-16
plan_key: T-05-T69
---

## Objective
T-05 §5.4, §5.5 and §10 items 3–4: "parity.json lists all 57 artboards, axe serious and critical
findings are zero, and the INP budget holds in the nightly trace."

## Built
- **Gallery and manifest.** TXP-00, 01, 02, 05, 06, 07, 10 and 11 on `/components/screens/<ID>`
  through the route's entity dispatch; TXP-00, 01, 06 and 10 `fixture` in the route manifest.
  Contract `## Parity` tables (Tier C report for every artboard, Tier D host) and 57 handoff PNGs
  pinned in `docs/design/parity-manifest.json`. The screen parity report has 65 rows (57 + 8 host).
- **Link contract rule 1.** The 16 links between now-built screens are wired with `to.<ID>()`:
  TXP-00 (row names to their Review sub-tab, "n open" → TXP-10, View work → TXP-11, the Links
  band's Files → FIL-01), TXP-01 (section links, a new DocBlocks `link` segment in the kit),
  TXP-07 → TXP-06 and TXP-10, TXP-10 → TXP-11, TAX-02/TAX-03/HOME-02 → TXP-01.
- **`e2e/screens/TXP-entity.spec.ts`.** 57 artboards: render, axe (zero serious or critical),
  and the DOM grammar ("$" only on TXP-02, negatives brick parentheses never a minus, zero "—"
  ink-4, spinners ink-2, no zebra rows, TINs masked).
- **Grammar fixes it found.** WorkbookGrid negatives brick and "—" ink-4; DataGrid text "—" ink-4;
  TXP-07 pane tones; TXP-11 zero "—" (the handoff's row 8).
- **`e2e/visual/tier-d-entity.spec.ts`** (blocking): subbar 42, tabsbar 50 (fixed from 48),
  control bar 44, tally 52, TXP-00 pane header 46 at 14.5/500 with radius 12, Geist 13, grid
  letter row 20 (kit fixed from 26) and row numbers 34.
- **`e2e/entity/workbook-grid-keyboard.spec.ts`**: the grid (arrows, Enter, F2, Esc, announced
  address), O4 (focus trap, Esc, focus returns to "Allocation Structure…"), Segmented (arrows).
- **`e2e/entity/txp11-inp.spec.ts`**: a `TXP-11:load` state (sheet 01's cells repeated to 2,000)
  and the Event Timing trace: 32 ms over 26 interactions against the 200 ms budget.

## Partial
- WorkbookGrid specimen Tier B lock: no handoff artboard draws the bare grid, so no honest
  baseline; the TXP-11a crop is the candidate once a crop box is chosen and measured.
- The four proposed locks (TXP-02a, 05a, 07a, 11a) wait for a measured Tier C run with this
  handoff's baselines (none on this machine; CI fetches them).
- Body line 15.6: the open F-05-T05 decision (fixme, as in tier-d.spec.ts).
- Overlay and interaction artboards (a2, a3, e2 …) render their base frame in the gallery.
- Reduced-motion and forced-colours checks are not separately asserted here.

## Progress log
- `2026-11-16` — Built. TXP-entity: axe clean on all 57; 49 of 57 passed the grammar before the
  last TXP-11 zero fix (the re-run is pending). Tier D 22 passed with the T6/TPL-06 suite;
  keyboard 3 passed; INP 1 passed; vitest routes/screens/fixtures 991 passed. Some runs
  overlapped the S46 session's test lock (taken 10:38Z); the remaining runs wait for it. DEC-5301.
