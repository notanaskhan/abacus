---
id: TASK-1213
title: AUD-01 audits index on T1 with the R2 tabs bar — a–f on the live read model, g and h as fixture scenarios (A-01-T11)
spec: SPEC-330
acceptance_criteria: [AC-1, AC-18, AC-19]
risk_zone: green
status: done
epic: A-01
plan_key: A-01-T11
branch: s8b-audits-ui
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Six live scenarios and two fixture scenarios pass their revision acceptance checklists and axe."

## Plan
- `packages/ui/src/templates/index-list.tsx`: optional `tabs`/`tabsEnd` (44 px bar) and `groupOf` (rowgroup bands); tests in `index-list.test.tsx`.
- `apps/web/src/domain/audits/list.ts`: filters, URL params, `useAuditIndex` over `auditsIndexInfiniteOptions`, the Type label.
- `apps/web/src/screens/AUD-01/{index,copy,scenarios}.ts(x)`, `AUD-01.test.tsx`; `fixtures/scenarios/AUD-01.ts` (a–h).
- Fixtures: `seed/audits-index.ts` (type and office filters, entitled segments, type facet, wave-7 rows A28–A33); `handlers/audits.ts` (`epoch`).
- Route `/audits` in `routes/firm/audits.tsx` behind `audits.cockpit`; nav area Audits routed; manifest path; gallery artboards.

## Progress log
- 2026-10-25: built; 26 AUD-01 tests pass (a–h, error, acceptance, Stories 1.2 and 1.4 with a Lena Park test wall, route flag-off and URL filters, AVOID). Decisions in DEC-340. Missing from the live contract (recorded, not built): `type_label` (SOC report type, IA programme), a drafted-PBC count (Harlow & Pike "12 drafted"), and `facets.partner`/`office`/`period` on `GET /v1/audits`. Axe and parity run with A-01-T28.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-340 | Count line, Type label, chips without facets, wave-7 fixtures, IndexList props | No |
