---
id: TASK-1152
title: ADM-01 Settings home & firm profile on the T12 frame — /settings/general, fieldsets A–D, dirty, Discard, Save with step-up, validation, read-only, toast, leave guard, At a glance (G-01-T07)
spec: SPEC-024
acceptance_criteria: [AC-5]
risk_zone: green
status: done
epic: G-01
plan_key: G-01-T07
branch: s7-g01-people
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"Scenarios a–f pass with axe and AY's design-fidelity review signs off."

## Plan
- `screens/ADM-01/` (index, copy, scenarios, test) on `SettingsLayout` (T12), reading `GET /v1/firm/settings/overview`, the three sections, `GET /v1/firm/offices` and `GET /v1/firm/members` through the generated client; `PATCH /v1/firm/settings/{section}` with the version read.
- `packages/ui` SettingsLayout gains `aside` (the 330 At a glance column) and `bare` (inside the app's own shell, no second toolbar).
- Route `/settings/general` behind `firm_settings.v2`; `/settings/$section` answers "not built yet"; manifest ADM-01 `fixture` at `/settings/general`; gallery entry for the e2e/axe harness.

## Progress log
- 2026-10-24: built; 9 screen tests (a–f, leave guard, not-allowed) and the whole web suite (1,466) pass. The People line of Plan & seats reads the People glance row, which now carries `partners` and `operations` (identity's `_people` provider).
- Deferred: the Playwright spec with axe (`e2e/screens/ADM-01.spec.ts`) is G-01-T16's; the gallery entry is ready for it. The `/admin/people` and `/admin/walls` redirects wait for ADM-02 and ADM-03 (T10, T14) so they never land on a planned page. Offices (fieldset B) render once `GET /v1/firm/offices` is live (T08; 501 until then, so the fieldset is absent live). "Replace…" logo and "+ Office" are planned controls (hidden in production). `firm_settings.v2` is not yet switched on for the Dev and synthetic firms (a founder switch, as `clients.v2`).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-288 | ADM-01's frame, nav and step-up choices | No |
