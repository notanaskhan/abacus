---
id: TASK-1803
title: E2E for the K-01 MVP slice (K-01-T11)
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: K-01
plan_key: K-01-T11
branch: s13r-k01-t11
created: 2026-10-28
updated: 2026-10-28
---

## Objective
KNW-01 a–f walked in the app with axe and INV-1 to INV-5; j01 5w recorded against its owner.

## Plan
- `apps/web/e2e/journeys/knw-01-catalog.spec.ts` (under journeys/ so the harness runs it; DEC-902).
- `J01-firm-onboarding.spec.ts`: j01 5w as `test.fixme` owned by K-01-T07 (KNW-02 not built).
- Full stack and staging `test.fixme` with the reason (flag off in E0, methodology slice opt-in).

## Progress log
- 2026-10-28: written; run in the end-of-batch pass (S13 leftovers).

- 2026-10-29 (review): the fixture walk found the catalog grid's scrolling pane unreachable by keyboard (axe scrollable-region-focusable, serious); CatalogLayout now passes Pane's existing `scrollLabel`. `/knowledge` carries no tab, category or query in its URL, so the walk opens Methodology, the Review queue and the Change log and types "materiality" as a person does. 4/4 on the fixture project.
