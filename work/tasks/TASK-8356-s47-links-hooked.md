---
id: TASK-8356
title: "S47 end pass follow-up: S47 links helpers on their controls: TXT-04 header actions and ADM-08's integration name"
spec: SPEC-none
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
branch: s47-links-hooked
worktree: /Users/ayushkbhatia/Accrued/abacus-s47g04
created: 2026-11-16
updated: 2026-11-16
plan_key: S47-end-pass
---

## Objective
Spec section: link-contract rule 1; S47 end pass TASK-8337/8338 helpers. S47 links helpers on their controls: TXT-04 header actions and ADM-08's integration name.

## Plan (green)
1. TXT-04 live: Intake (TAX-03), Checkpoints (SHL-16) and Export to CCH Axcess (TAX-09) in a header row, through `links.ts`.
2. ADM-08: the CCH Axcess Tax band title opens WB-11 on the integration (`links.integrationOverlay`).

## Progress log
- `2026-11-16` — Built in the S47 sequential stack. tsc, eslint, TXT-04 (8) and ADM-08 (9) tests clean. Not hooked (need data the live reads lack): TXT-04 request (binder and contact), provenance (field keys), files and 4768 links; AUD-12 issueOverlay (per-entry results). Gates and
  tests run once at the S47 end pass (build first, test last).
