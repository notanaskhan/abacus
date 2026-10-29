---
id: TASK-2104
title: K-02-T13 KNW-04 read states a–h
spec: SPEC-500
acceptance_criteria: [AC-13, AC-14]
risk_zone: green
status: in-review
epic: K-02
plan_key: K-02-T13
branch: s16-k02-t13
created: 2026-10-29
updated: 2026-10-29
---

## Objective
KNW-04 read states a–h on the T12 SettingsLayout at `/knowledge/standards`, on fixtures, with one
scenario and test per state (K-02 §5; docs/screens/KNW-04.md).

## Plan
- Contract (additive): `entries`, `tax_year`, `labels`, `caption`, `approver_name`, `cells`; `make generate`.
- `apps/web/src/fixtures/seed/standards.ts`, `handlers/standards.ts`, `scenarios/KNW-04.ts`
  (a–h, `draft_hidden`, `no_examples`, `flag_off`); `fixtures/standards.foot.test.ts`.
- `apps/web/src/screens/KNW-04/{index.tsx, copy.ts, scenarios.ts, KNW-04.test.tsx}`.
- Route `/knowledge/standards` in `routes/firm/knowledge.tsx`; manifest path (planned, DEC-195);
  gallery and `screen-scenarios.ts` registration.

## Acceptance
| Check | Test |
|---|---|
| a–h states, figures foot | `KNW-04.test.tsx` (one describe per artboard), `standards.foot.test.ts` |
| Draft hidden from staff | `hides the draft from Cole Hart` |
| Empty examples | `shows the designed empty state…` |
| Flag off (AC-14) | `draws the T12 frame with the not-turned-on state…` |

## Progress log
- 2026-10-29: built (S16 block). tsc and eslint clean on the touched files; vitest runs at the
  batch's end review. Screenshots a–h read for copy and figures. DEC-1154.
