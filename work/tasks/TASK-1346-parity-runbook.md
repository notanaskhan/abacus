---
id: TASK-1346
title: Parity docs and runbook (F-05-T61)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-10]
risk_zone: green
status: in-review
epic: F-05
plan_key: F-05-T61
branch: s10c-fe
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"A new session can refresh baselines and lock a template from the runbook alone."

## Plan
- `docs/design/parity.md`: pieces, refresh, add a board, lock a template, gallery how-to, F-06
  hand-off. DECISIONS.md: the T60 and T61 headings.

## Progress log
- 2026-10-27: Written from the tools as they are (crop_handoff, baselines, parity.spec, tier-d,
  a11y). Noted two gaps the plan assumed: the parity spec reads no `data-parity-mask`, and the
  `/components/parity` overlay page is not built. The capacity ledger is not in this repo's
  reach for this session (the plan pack lives outside it); the task log is these files.
