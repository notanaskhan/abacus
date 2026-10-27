---
id: TASK-1450
title: POR-01 and POR-02 docs closed, portal-entry skill notes, Pilot 0 usability log (P-08-T29)
spec: SPEC-320
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: P-08
plan_key: P-08-T29
branch: s11-assurance
created: 2026-10-27
updated: 2026-10-27
---

## Objective
"Both screen contracts show parity, live status and closed deviations, and the skills describe how
to add a portal screen."

## Plan
- `docs/screens/POR-01.md`, `POR-02.md`: manifest status live (the screens read the served
  routes behind the portal flags, on for synthetic firms since P-08-T28); a "Deviations closed"
  line naming each row's decision; the parity rows say what is built and that the Tier C lock is a
  person's sign-off after the first `pnpm visual` run.
- `apps/web/src/routes/manifest/por.ts`: POR-01 and POR-02 `live`.
- `.claude/skills/frontend-feature/SKILL.md` "The portal entry"; a pointer in
  `build-screen-from-handoff` step 4.
- `docs/product/discovery/pilot-0-usability-log-portal.md`: the log's structure (sessions,
  findings, routing to the P-08 reserve, top-10). Findings are a person's after real sessions:
  placeholders only, clearly marked.
- Rollback: revert.

## Progress log
- 2026-10-27: built. Not done here: the parity measurement and lock (needs a browser and a
  human `pnpm visual` sign-off); the Pilot 0 sessions themselves (Jan 2027, human).
