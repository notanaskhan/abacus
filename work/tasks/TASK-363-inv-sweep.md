---
id: TASK-363
title: Independent INV-1 and INV-5 tests over every specimen (F-05-T31)
spec: SPEC-048
acceptance_criteria: [AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T31
branch: f05-t30-attribution
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"A role sweep finds no approve, sign off, release, send, post or decide control on an agent-owned
element and no row reads Approved by Accrued Agent." Written from plan 04 rule 9, lint L6 and
F-05 H1 (ADR-078).

## Scope
`apps/web/e2e/inv.spec.ts` over every /components specimen, in CI's gallery job:
- no human-only verb control inside `[data-actor="agent"]`;
- every human-only verb control is a `HumanAction` (`data-human-verb`);
- no text reads "Approved/Signed off/Released/Sent/Posted/Decided/Adopted by Accrued Agent".

## Findings
Six specimen controls carried Approve, Sign off or Send outside `HumanAction` (C-00 overview and
panes, C-22 dialog, the C-21 live board's trigger). Fixed in the same change.

## Harness notes
The gallery's axe checks now wait for one-off entrance animations (a Reveal mid-fade read as low
contrast), and the reduced-motion check ignores transitions reduced motion has clamped to 0.01ms
(Chromium lists them as running for a frame).
