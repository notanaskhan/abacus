---
id: TASK-6821
title: "A-07-T53: screen contracts final (DV-1 to DV-9 evidence, per-artboard status, copy keys) and the pilot completion-to-archive guide"
spec: SPEC-644
acceptance_criteria: [AC-DOD-8]
risk_zone: green
status: in-review
branch: s36-a07-t53
worktree: /Users/ayushkbhatia/Accrued/abacus-s36
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T53
---

## Objective
Every A-07 artboard in the manifest shows its final status, and the guide renders from the
database in the in-app help.

## Built
- `docs/screens/AUD-18, 19, 21–25.md`: manifest status final, a "Final status (A-07-T53, S36)"
  section with each artboard's status and the evidence for each deviation it names.
- `apps/web/src/routes/manifest/aud.ts`: AUD-21 to AUD-25 `live` (hosted in AUD-02, no path).
- `docs/help/audit-completion-to-archive.md`: the one-page guide, as an import source.
- DEC-3414.

## Partial / flagged
- **Deviations not in the code (recorded open, not claimed):**
  - DV-2: the screen keeps "Locked · WORM" while OQ-2 is open;
  - DV-3: no L5 menu item yet;
  - DV-4: no "Request EQR…";
  - DV-6: no "2 of 3 required sent".
- **DV-8 is partly applied.** These need their screens' follow-up rows.
- **AUD-18 has no live host**, though A-07-T18's service is live.
- **No in-app help store exists** (no table, route, admin screen or backlog row), so the guide cannot
  render from the database yet. It is an import source only, never seeded (constitution 16). A help
  store needs its own row.
- **The L1–L12 copy lint over these copy files runs at the end pass.**
- **The manifest status change may hit manifest tests:** "live" with path null; checked at the end
  pass.

## Progress log
- `2026-11-11` — Built (S36). Docs and manifest; nothing run.
