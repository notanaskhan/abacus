---
id: TASK-2025
title: A-02-T34 Journey E2E for the trial balance and connections
spec: SPEC-317
acceptance_criteria: [AC-4]
risk_zone: green
status: in-review
epic: A-02
plan_key: A-02-T34
branch: s15n-a02-t34
created: 2026-10-29
updated: 2026-10-29
---

## Objective
j04 2 (Granite Peak TB on AUD-06), j02 6 (Tess connects QuickBooks and the bank feed), j03 7
(Northwind TB with three ties), POR-16 reconnect; INV-1..5 and axe after every step.

Acceptance (backlog row): "The named steps pass on staging with INV-1..5 and axe clean, and every
unbuilt step is test.fixme naming its owning epic."

## Built
`apps/web/e2e/journeys/A02-tb-connections.spec.ts`: the fixture project walks each step on its
screen's artboard (scenario and persona of the state); full stack, staging and canary are
`test.fixme` naming A-02-T24/T28's live swaps (staging walk by M8). The staging half of the
acceptance is a person's run once staging serves A-02 live.

## Progress log
- 2026-10-29: written (S15 group B); run at the end review.
