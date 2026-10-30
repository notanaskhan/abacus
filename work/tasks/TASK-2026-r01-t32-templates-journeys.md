---
id: TASK-2026
title: R-01-T32 Template journeys and screen specs
spec: SPEC-317
acceptance_criteria: [AC-4]
risk_zone: green
status: in-review
epic: R-01
plan_key: R-01-T32
branch: s15n-r01-t32
created: 2026-10-29
updated: 2026-10-29
---

## Objective
Playwright: j16 4 (Grace edits, tests and publishes Reminder v4), j12 1 (a Reminder reaches the
sink), the j02 invitation from the database template, screen specs por-20-email-templates and
adm-10-portal-settings, and the M8 walk of j12 core on the production canary.

Acceptance (backlog row): "The steps pass on staging and the j12-core walk passes on the
production canary by Fri May 28, 2027."

## Built
- `apps/web/e2e/screens/{POR-20,ADM-10}.spec.ts`: every artboard, axe at zero serious.
- `apps/web/e2e/journeys/R01-templates.spec.ts`: j16 4 on POR-20's artboards (fixture); j12 1,
  j02 and the canary walk `test.fixme` naming R-01's live swap (staging and canary runs are a
  person's, by M8).

## Progress log
- 2026-10-29: written (S15 group B); run at the end review.
