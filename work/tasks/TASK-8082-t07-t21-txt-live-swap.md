---
id: TASK-8082
title: "T-07-T21: Fixture-to-live swap for TXT-01 and TXT-02 (staging run excluded)"
spec: SPEC-656
acceptance_criteria: [AC-1.1, AC-6.2]
risk_zone: green
status: in-review
branch: t07-t21-txt-live-swap
worktree: /Users/ayushkbhatia/Accrued/abacus-s46
created: 2026-11-15
updated: 2026-11-15
plan_key: T-07-T21
---

## Objective
Wire TXT-01 and TXT-02 to each other and to their live read models: deep links `?clause=` and
`?row=`, the reader's progress with a polling fallback, and the agents-off and consent-required
paths from the read model's `allowed_actions`.

## Built
- `routes/firm/tax-review.tsx`: `?clause=` and `?row=` validated as short labels; TXT-02's clause
  chip opens TXT-01 with the clause lit; TXT-01's Cited by opens TXT-02 with the row lit.
- `TXT01` takes `clause` (lit on arrival); `TXT02` takes `row` (lit and scrolled into view).
- `domain/tax/instrument.ts`: the instrument read model polls every 3 s only while a reader
  progress line shows (the SSE invalidation is the primary path; this is its fallback).
- TXT-01's agents-off (d1) and consent-required (d3) states already render from the read model
  (`reader` facts and `allowed_actions`, T-07-T12); the live service now answers them.
- Test: TXT-02 `?row=` (8 pass in the file).

## Progress log
- `2026-11-15` — Built. **Partial:** "Both screens run live on staging against the scenario" waits
  on a staging deploy of this batch (the AC's staging half); TAX-05 sub-row, SHL-08 and SHL-09
  links ride their screens' own live swaps.
