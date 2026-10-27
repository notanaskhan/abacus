---
id: TASK-1422
title: POR-20 email templates screen with the interim EmailPreview (R-01-T25)
spec: SPEC-345
acceptance_criteria: [AC-6]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T25
branch: s11-comms
created: 2026-10-27
updated: 2026-10-27
---

## Objective
Twelve POR-20 scenarios (a–l) pass, lint findings show inline on their block, and Publish stays
disabled while the lint has a finding. Grace's edit, test and publish full stack on staging is
not possible from this lane (no staging access): said in the report.

## Plan
- Route `/settings/portal/email-templates/$templateKey` (`?w=600|390|phone`), lazy-loaded
  (the firm bundle is at its budget), behind `portal.settings_editor` for writes only (the flag
  off renders read-only from `allowed_actions`).
- `src/screens/POR-20/{index.tsx, copy.ts, scenarios.ts, POR-20.test.tsx}`,
  `src/domain/communications/{EmailPreview.tsx, templateBlocks.ts, variables.ts}`,
  `src/fixtures/handlers/email-templates.ts`, `src/fixtures/seed/email-templates.ts`,
  `src/fixtures/scenarios/POR-20.ts`; manifest `POR-20` fixture with its path.
- Data only through the generated client; template words only from the fixtures' seeded rows
  (no template text in `copy.ts`).
- EmailPreview: the server's deterministic HTML in a sandboxed `iframe srcdoc` (no scripts, no
  same origin, a CSP that forbids every fetch), plain text on demand.
- Tests: one per artboard, avoid list, Publish disabled with a finding.

## Progress log
- 2026-10-27: planned (S11 lane 5).
- 2026-10-27: built on fixtures; 15 vitest cases green (a–l, the lint acceptance, sandbox, avoid).
  The manifest keeps a null path: link-contract's rule 2 holds every POR- id to the portal tree
  (DEC-567). Not done here: the staging full-stack run, Playwright, gallery registration.
