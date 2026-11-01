---
id: TASK-2713
title: A-03-T15 AUD-11 c, e and f and SHL-14 c
spec: SPEC-580  # A-03 F3, F4 US-4.2; docs/screens/AUD-11.md, SHL-14.md
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-03
plan_key: A-03-T15
branch: s22-a03-t15
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "State c shows 125 requests 100 to POR-03 25 to POR-14 and creates them, state f
  foots 24 + 1,102 + 786 = 1,912 and 24 + 16 = 40, and SHL-14 c offers only approved versions."

## Scope
**In**: AUD-11 c (`GenerateSheet.tsx`, O3), e (a person's draw polling `…/draw`, rows 70 ms apart,
reduced-motion safe), f (general-ledger source rows, strata, the size line, the HR tooltip);
SHL-14 c (`SampleWave.tsx`: approved-version picker, participants card, preview, Create); AUD-03's
Sample-driven band from the server (requests' `source_documents` groups the sample wave); fixtures,
artboards, tests; SHL-14 screen contract row.
**Out**: parity and E2E (A-03-T19); seed-demo content (A-03-T16).

## Progress log
- 2026-11-01: built on the A-03-T13 fan-out; tests run in the S22 end pass.
