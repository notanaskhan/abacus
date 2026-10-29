---
id: TASK-2126
title: F-06-T10 TPL-19 frames 1, 2 and 7 on T7-M
spec: SPEC-000  # F-06-T10 row and the TPL-19 handoff; no SPEC defines the specimen
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
epic: F-06
plan_key: F-06-T10
branch: s16-f06-t10
created: 2026-10-29
updated: 2026-10-29
---

## Objective
TPL-19 frames 1 (Home: greeting, return card with progress ring, to-dos, team), 2 (Documents:
DropZone card and the open requests as cards) and 7 (More sheet over Home, no Approvals for a
household) for Claire Feld at 390 × 844.

Acceptance (backlog row): "Frames 1, 2 and 7 render at 390 by 844 with the 56 px firm header and
64 px tab bar, open requests match TPL-07, and no Accrued mark or blue appears."

## Plan (amber)
- `packages/ui/src/templates/portal-mobile-home.tsx` (MobileGreeting, ReturnProgressCard,
  MobileTodoCard, MobileTeamCard); `RequestMobile` gains `dropHint` and `openOnly` (open cards and
  the folded "n received · n provided by <firm>" row); `file-up` joins the portal icon registry.
- Specimen `specimens/tpl19.tsx` (reuses TPL-07's requests, now exported); test
  `templates/tpl19.test.tsx`. No backend, no flag. Rollback: revert the commit.

## Progress log
- 2026-10-29: built (S16 block). DEC-1173. Frames 3–6, 8 (camera path) and 9 (mobile signing)
  are later rows.
