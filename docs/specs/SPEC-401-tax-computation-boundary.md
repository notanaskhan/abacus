---
id: SPEC-401
title: Tax computation boundary (T-02 pre-window, ADR P-68)
status: draft
owner: ayushkbhatia
risk_zone: amber
related_adrs: [ADR-050, ADR-231]
related_specs: []
created: 2026-10-28
updated: 2026-10-28
---

> **Instructions for coding agents**
> - This spec carries only the pre-window decision task T-02-T36. T-02's own SPEC (S16) supersedes
>   it for everything else and cites ADR-231.

## 1. Summary
Record where tax is computed before any T-02 or T-04 screen shows an engine figure: CCH Axcess
computes tax, credits and filed forms; Accrued shows engine values only from approved imports and
computes only display arithmetic and workpaper figures in code (DEC-77, P-68).

## 2. Problem and context
T-02-T13 (TAX-02 engine summary) and T-02-T18 build on the boundary; T-04 needs it whatever M8
decides. docs/plan/epics/T-02.md §0 (DEC-77, DEC-78), DV-3, DV-9.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| Tax CPA and the builder | Accept P-68 |

## 5. Acceptance criteria
- **AC-1** ADR P-68 is drafted with the next number from the S14 block, records DEC-77 and DEC-78,
  names what Accrued may compute, and `docs/adr/backlog.md` records its number; acceptance by Fri
  May 28, 2027, before T-02-T13 and T-02-T18 merge engine-summary code.

## 6. Open questions
- None. The CPA's acceptance is the remaining step.
