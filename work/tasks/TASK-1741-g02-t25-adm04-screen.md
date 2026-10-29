---
id: TASK-1741
title: ADM-04 AI policy & approval gates screen at /settings/ai-policy (G-02-T25)
spec: SPEC-349
acceptance_criteria: [AC-31, AC-32, AC-33, AC-34, AC-35, AC-37, AC-38]
risk_zone: green
status: done
epic: G-02
plan_key: G-02-T25
branch: s14-g02-t25
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADM-04 on T12 over the AI-policy contract (G-02-T15/T24): provenance chip, the immediate-controls
band (SPEC-036 opt-in with disclosure dialog and step-up, agent stages, Pause all agents),
fieldsets A to E with locks, the gate popover, the dirty draft, the Save as v4 sheet, Awaiting
approval, published, read-only, scrolled and the version-history drawer; c and f fixture-only.

Acceptance (G-02-T25): "ADM-04 a, b, d, e, g, h, i and j render from scenarios and from the
staging seed, c and f render in fixture mode only while every production policy-acceptance row
reads Off + Lock, no control offers a loosening, and axe is clean in every state."

## What changed
- `apps/web/src/screens/ADM-04/` (`index.tsx`, `copy.ts`, `scenarios.ts`, `ADM-04.test.tsx`).
- `apps/web/src/fixtures/scenarios/ADM-04.ts`: scenarios c and f, and `OPENS`.
- `apps/web/src/routes/firm/settings.tsx`: `/settings/ai-policy` behind `ai_policy.v1`.
- `apps/web/src/routes/manifest/adm.ts`: ADM-04's path.
- `apps/web/src/screens/gallery.tsx`: ADM-04 artboards.
- DEC-831 records the decisions.

## Tests
`ADM-04.test.tsx`: one test per artboard (a–j, band, awaiting, real_firm) plus the no-loosening
tolerance list. axe in every state and the staging-seed render are G-02-T26's journey and parity
task, which this row hands to.

## Progress log
- 2026-10-29: built and tested (14 tests); held for the S14 batch.
