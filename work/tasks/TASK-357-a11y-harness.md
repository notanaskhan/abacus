---
id: TASK-357
title: Accessibility harness — axe on every specimen and open overlay, forced colors, reduced motion, keyboard, target size (F-05-T24)
spec: SPEC-048
acceptance_criteria: [AC-3]
risk_zone: green
status: done
epic: F-05
plan_key: F-05-T24
branch: f05-t24-a11y
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"axe runs on every /components route and blocks on any serious or critical finding once DEC-11 is
recorded." DEC-11 is recorded, so the harness blocks.

## Scope
**In**
- `apps/web/e2e/a11y.spec.ts`, run in CI's gallery job beside `components.spec.ts`:
  - axe scoped to each specimen section (a failure names the specimen);
  - axe with every overlay the O1 to O6, C-22 and C-23 specimens open;
  - forced-colors emulation: axe, panes and pills keep a 1px edge, discs keep their colours;
  - reduced motion with an overlay opened and closed: `document.getAnimations()` stays empty;
  - keyboard: the first 60 focus stops show the outline and Tab never sticks;
  - target size (SC 2.5.8) over every control in the gallery.
- `packages/ui/src/base.css`: the forced-colors edges (plan 04 §3.8) the check found missing.

**Out**
- Screen-level a11y (each screen's own scenarios, chapter 04 §9 "Screen smoke"): with each screen.

## Definition of done
- [x] The 7 checks pass locally against `VITE_UI_GALLERY=1 VITE_FIXTURES=1` vite
- [x] `make check-fast` passes

## Progress log
- 2026-10-22: built. First run found the forced-colors edges missing; added to base.css.
