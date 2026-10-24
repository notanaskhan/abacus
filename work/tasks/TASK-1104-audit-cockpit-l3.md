---
id: TASK-1104
title: Audit cockpit L3 in apps/web/src/domain/audits on the F-05 kits, fixture mode (A-01-T06)
spec: SPEC-330
acceptance_criteria: [AC-15]
risk_zone: green
status: done
epic: A-01
plan_key: A-01-T06
branch: s7-a01-audit-wedge
created: 2026-10-24
updated: 2026-10-24
---

## Objective
"The rail renders registered rows only, every disc carries text, and the TPL-02 specimen still passes."

## Plan
- `apps/web/src/domain/audits/`: `messages.ts`, `rail.ts` (projection bands → Rail kit links and phases; sub-line and idle-pill grammars from the registry), `SectionRail.tsx`, `AuditBar.tsx` (no Auto mode without the capability), `BlockedSectionCard.tsx`, `DockHost.tsx` (Agent · Viewer, DF-04), `AuditCockpit.tsx` (T2 `RecordCockpit` host), `queries.ts`, `index.ts`.
- Fixture mode: `fixtures/seed/audit-cockpit.ts` (Northwind run, idle, pills), `fixtures/handlers/audits.ts` (index, cockpit, Source Documents; walls 404).
- Tests: `domain/audits/audits.test.tsx`; TPL-02's own suite unchanged.

## Progress log
- 2026-10-24: built; `vitest run src/domain/audits src/fixtures src/routes` 22 files pass (327 tests incl. 21 new), `packages/ui` tpl02, record-cockpit and record suites 36 pass, `tsc` and eslint clean. The link-contract rule 5 read "DF-29" in AUD-01's Links table as a target: the rows now say "Deviations" instead (T01 contract fix carried here). Planned rows keep the kit's chevron (DEC-264 follow-up).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-264 | L3 composition, grammars, capability-gated controls, planned links | No |
