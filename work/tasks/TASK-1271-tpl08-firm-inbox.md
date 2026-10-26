---
id: TASK-1271
title: TPL-08a to TPL-08e firm Inbox specimen (F-05-T58)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T58
branch: s9b-kit-screens
created: 2026-10-26
updated: 2026-10-26
---

## Objective
"Waiting rows total 23 (19 visible plus 4), the 2024 1095-C is flagged 2024 vs 2025, and the empty
filter offers Clear filters." `t8-data.ts` (TASK-1228) deferred TPL-08 to this task.

## Scope
**In**
- `packages/ui/src/specimens/tpl08.tsx`, `tpl08-data.ts`: `tpl-08`, artboards `tpl-08a` to
  `tpl-08e` for Kevin Osei on the T8 `InboxLayout`, from the File Kit `w0` and `w0-filed` datasets
  the boards mount (DEC-384): the Feld thread open with both 1095-Cs waiting and the 2024 one
  tagged "2024 ≠ 2025", row hover File…, the unmatched Sound Electric sender, the filed thread
  (2025 filed to Health & Medical, 2024 ignored as the wrong year) and the empty Ridgeline filter.
- Kit additions (backward compatible; T8's 8 tests still pass): `InboxRow`/`InboxList` `onFile`
  and `hovered`, a sender-only second line, `InboxAttachment` four states with `tag` and
  `result`, `ReadingHeader.context`.
- Registry entry `tpl-08`; parity `tpl-08.a` to `.e` at Tier B with a deviation.

**Out**
- INB-01 to INB-04 (the screens), the INB-02 triage sheet File… opens.

## Definition of done
- [x] 9 tests in `templates/tpl08.test.tsx` (acceptance and one per artboard)
- [x] tsc, eslint, prettier for `packages/ui`; tsc for `apps/web`
- [ ] Playwright not run locally: v1.63 wants chromium 1243, only 1248 is cached

## Rollback
Revert the commit; no migrations, generated files or flags.

## Progress log
- 2026-10-26: built and tested. Decisions in `tokens/DECISIONS.md` (F-05-T58) and DEC-384.
