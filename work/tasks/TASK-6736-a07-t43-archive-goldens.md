---
id: TASK-6736
title: "A-07-T43: golden tests (ADR-078) for the A-07 content, projector and the archive scenario"
spec: SPEC-314
acceptance_criteria: [A-07 F2, F3, F6, F7]
risk_zone: amber
status: in-review
branch: s35b-a07-t43
worktree: /Users/ayushkbhatia/Accrued/abacus-s35
created: 2026-11-11
updated: 2026-11-11
plan_key: A-07-T43
---

## Objective
Every figure above holds on make seed-demo and the tests fail on a one-day or one-row drift.

## Plan
- `backend/tests/golden/scenario/brightwater_hale/archive_figures.json` (new): the book,
  transcribed from A-07 §1, F2, F3, F6 and F7.
- `backend/tests/golden/scenario/test_a07t43_archive_figures.py`: the content, the clocks and the
  slice against the book. It covers:
  - Oct 9 + 60 = Dec 8, with a one-day drift and the firm-zone late-evening case;
  - Archive in 47 days on Oct 22, and the lock 5 days before the deadline;
  - retention to Oct 9, 2033, with the records floor in 2031;
  - 6 of 10 on the EQR checklist, 12 of 17 on the completion checklist with its tags, and 8 of 9 on the archive checklist;
  - 26 workpapers in A–E;
  - SUM 34,150 = 18.1% of 189,150;
  - DF-27: representations 1–11 general, 12–15 by trigger;
  - the template variables resolve;
  - T22's projector inert while external or with the flag off.
- `backend/tests/integration/test_a07t43_archive_golden.py`: the loaded tenant at 10:05 on
  Oct 9. It checks the binder (26 workpapers, 24 source documents, 23 run logs, 5 independence
  confirmations) and Northwind's letter (12, 13 and 15 on; 14 off).
- `apps/web/src/fixtures/contracts/archive-figures.test.ts`: the fixtures against the book.
  Fixed the drift it found in `seed/audit-completion.ts`:
  - AUD-24 d released at 10:07, not 4:12 PM;
  - Hannah Leclerc locks, not Margaret Okonkwo;
  - AUD-25 b is 5 days from the deadline, not 12.

## Partials (flagged)
- The integration golden stops at the 10:05 snapshot: the archive itself (the binder index
  version, the checklist's live 8 of 9, the seal) opens on `report.released`, which needs the
  relay; the figures are pinned at the binder the index is built from.
- The report builder takes the family's published template, so Granite Peak's FS report can't
  pick "BH Report · FS Nonissuer Unmodified v4" over the EBP one (an A-07-T27 gap; noted, not
  fixed here).

## Progress log
- `2026-11-11` — Built. The content and fixture goldens pass (17 and 5 tests). The integration
  golden is written and runs at the end pass.
