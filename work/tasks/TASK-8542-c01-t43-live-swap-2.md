---
id: TASK-8542
title: "C-01-T43: live swap 2: CLS-04, CLS-05, CLS-06 and CLS-10 (code side)"
spec: SPEC-655
acceptance_criteria: []
risk_zone: green
status: in-review
branch: c01-t43-live-swap-2
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-18
updated: 2026-11-18
plan_key: C-01-T43
---

## Objective
Live swap 2: CLS-04, CLS-05, CLS-06 and CLS-10 to live endpoints; the SHL-08, SHL-10 and SHL-12 overlays filled into T57's pre-window overlay seams with new closes files only; C-20 states; link-contract entries.

## Plan (green)
1. domain/closes/ReadFrame.tsx: closeReadFrame, the C-20 frame live swap 1 drew inline on CLS-03 and CLS-09 (403 role notice, 404 walled, else error with Retry), no record data
2. CLS-04, CLS-05, CLS-06 and CLS-10 return the frame for a refused or failed primary read (account tree, reconciliation, issues, flux)
3. Link contract rule 1: CLS-02 rail, CLS-04 (bank account to CLS-05, issue to CLS-06), CLS-06 (account, linked records to CLS-03/04/05) and CLS-10 (Issue to CLS-06) open their designed links through to.<ID>(); the closes route no longer passes those handlers
4. Manifest: CLS-04, 05, 06 and 10 live
5. Overlay seams (DEC-5527): SHL-08, SHL-10 and SHL-12 already render close sources through their generic frames (P-03-T14, P-04-T42, P-04-T48); the handoff draws no close-only frame, so close-seam-slots.tsx keeps passing through and no T57 seam file changes
6. Tests: domain/closes/ReadFrame.test.tsx; link-contract.test.ts rule 1 green

## Progress log
- `2026-11-18` — Code side built 2026-11-18 (S49 open rows): tsc and eslint clean; closes + routes vitest 142 pass. Not done here: the staging run with real auth and the Sep 19 promotion slot (a staging step). Gates and tests run once at the S49 open-rows end pass (build first, test last).
