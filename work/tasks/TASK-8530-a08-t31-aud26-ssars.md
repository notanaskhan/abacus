---
id: TASK-8530
title: "A-08-T31: AUD-26 review, compilation and preparation states a-e"
spec: SPEC-657
acceptance_criteria: []
risk_zone: green
status: in-review
branch: a08-t31-aud26
worktree: /Users/ayushkbhatia/Accrued/abacus-s49
created: 2026-11-17
updated: 2026-11-17
plan_key: A-08-T31
---

## Objective
AUD-26 states a-e on T2 with the Agent dock in fixture mode: modes by engagement type, Expectations and Ratios segmented, inquiry cards with Publish and Send reminder, over-threshold row with Ask client, compilation and preparation rails, preparation paper preview. AC: each mode renders from its engagement type and review mode shows no risk register, sampling, confirmations or control testing.

## Plan (green)
1. fixtures/seed/fieldwork.ts: Lakeshore expectations, subtotals, grants explanation, run #4119 narration and tools, six inquiry cards (handoff #aud26); kit-a08-data re-exports
2. screens/AUD-26: scenarios (engagement per artboard), copy, index (SsarsWorkspace on SsarsRail; analytics table, explanation card, inquiries, compilation card, preparation preview with the no-assurance footer per page; narration through AgentText), AUD-26.test.tsx
3. gallery registers AUD-26

## Progress log
- `2026-11-17` — Built; AUD-26 vitest 11 pass, tsc and eslint clean. The preparation preview's page captions read 'FY2025' (the handoff gives no Juniper & Oak year end). Ask client to SHL-14 and the dock composer wire in the live swap (A-08-T32). Gates and tests run once at the S49 end pass (build first, test last).
