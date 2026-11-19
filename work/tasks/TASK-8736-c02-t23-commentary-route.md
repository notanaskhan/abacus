---
id: TASK-8736
title: "C-02-T23: CLS-08 commentary page, commentary edit and the Deliverables route"
spec: SPEC-701
acceptance_criteria: [AC-6, AC-7]
risk_zone: amber
status: in-review
branch: s51p-c02-t23-commentary-route
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: C-02-T23
---

## Objective
Finish C-02-T23 (TASK-8711) as far as the server now serves: CLS-08 draws the commentary page from the package read, Edit opens commentary only (figures locked) and saves through PATCH …/package/commentary, and the screen is mounted at /closes/$closeId/deliverables inside the close shell.

## Plan (amber)
1. screens/CLS-08: commentary page (heading, paragraphs), inline edit with ValueRow paragraph and Save/Cancel, commentaryMutation; copy rows.
2. Python export cas_delivery_slice.cls08_package carries the handoff's page-6 commentary verbatim; make fixtures (only scenario.cls08-package.json changed); TS scenario reads it and answers the commentary PATCH.
3. routes/firm/closes.tsx closeDeliverablesRoute and the shell's Deliverables tab; manifest CLS-08 live with its path.
4. CLS-08.test.tsx: three pages with the legend, renumbering, the commentary edit.

## Progress log
- `2026-11-19` — Built. Not built: the cash-flow page (the handoff gives no cash-flow figures) and the AR/AP aging pages (the ledger holds no open AR/AP items to age yet; the export's buckets stay fixture-only), citation markers to SHL-07 on each figure, and the release dialog (C-02's release service is not built; the route stays 501). Gates and tests run once at the S51 end pass (build first, test last).
