---
id: TASK-2022
title: N-01-T15 INB-02 triage sheet
spec: SPEC-380
acceptance_criteria: [AC-25]
risk_zone: green
status: in-review
epic: N-01
plan_key: N-01-T15
branch: s15n-n01-t15
created: 2026-10-29
updated: 2026-10-29
---

## Objective
INB-02 states a, a2, b, c, e, f, g and fixture-only d on the O3 SheetModal (DEC-1062).

Acceptance (backlog row): "Apply stays disabled until every flagged or ambiguous card has a
human choice, and Escape on a dirty sheet asks first."

## Built
- `domain/inbox/{TriageSheet.tsx, copy.ts, index.ts}`; `screens/INB-02/{index.tsx, copy.ts,
  scenarios.ts}`; `fixtures/{seed/inbox-triage.ts, scenarios/INB-02.ts}`; gallery registration.

## Not built here
- INB-01 e's bulk bar: needs a checkable InboxList in the kit (F-05).

## Tests
Build-only (Ayush, 2026-10-29): scenario tests at the end review.

## Progress log
- 2026-10-29: built (S15 group B, build-only). tsc and eslint clean.
