---
id: TASK-434
title: White-label and portal-isolation tests - import-boundary lint for portal entries, crawler over portal specimens at 1400, 720 and 390 (F-05-T39)
spec: SPEC-048
acceptance_criteria: [AC-5, AC-10]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T39
branch: f05-t39-white-label
created: 2026-10-23
updated: 2026-10-23
---

## Objective

"Portal specimens show no Accrued text unless secured_footer is on and portal entries cannot import
firm shell or firm screens (INV-4)." (F-05-T39)

## Plan (amber: written before building)

Files:

- `packages/ui/eslint-design-rules.js`: `portalTextSyntax` (a string, template chunk or JSX text
  containing the product's name, any case) and `UI_PORTAL_FILES`, shared by both configs.
- `packages/ui/eslint.config.js`: the text ban on the package's portal surfaces and specimens.
- `apps/web/eslint.config.js`: `PORTAL_FILES` (`src/entries/portal.tsx`, `src/portal/**`,
  `src/routes/portal/**`) and `PORTAL_SCREEN_FILES` (`src/screens/POR-*/**`) take
  `portalImportRestrictions` (no `src/shell`, no firm routes or root layout, no firm screen, no
  legacy screen, no gallery, no `@abacus/ui/specimens`) and the text ban, on top of their usual
  rules. The legacy `src/routes/portal.tsx` stays in the firm bundle until P-08-T28 and is not
  covered.
- `packages/ui/src/specimens/index.ts`: `surface: "portal"` on the portal specimens;
  `apps/web/src/gallery/pages.tsx` marks their sections `data-surface="portal"`.
- Tests: `apps/web/src/lint/white-label.test.ts` (both configs through ESLint's API),
  `apps/web/src/gallery/white-label.test.tsx` (the crawl in jsdom over every portal specimen),
  `apps/web/e2e/ds-white-label.spec.ts` (the crawl in a browser at 1400, 720 and 390), added to the
  CI gallery step in `.github/workflows/ci.yml`. The jsdom crawl also proves it bites (a planted
  name in text and in an attribute is found; the footer's is not).

No migration, registry, flag or dependency. Rollback is a revert. The rules only tighten; nothing
existing is weakened (AGENTS.md rule 13).

## Tests mapped to the acceptance string

- "portal entries cannot import firm shell or firm screens" → `white-label.test.ts`, "INV-4: portal
  entries cannot import the firm shell or firm screens" (14 refused imports across the entry, the
  portal tree, portal routes and a POR screen; the allowed ones; the firm keeps its shell).
- "no Accrued text unless secured_footer is on" → the jsdom crawl (each portal specimen, and the
  footer only where a frame turned it on), the browser crawl at three widths, and the L7 text ban
  in both configs.

## Definition of done

- [x] `vitest run src/lint/white-label.test.ts src/lint/eslint-rules.test.ts`.
- [x] `vitest run src/gallery/white-label.test.tsx`.
- [x] `playwright --project=chromium ds-white-label.spec.ts`: 3 passed (1400, 720, 390).
- [x] eslint and prettier on the changed files; `validate_docs`.

## Progress log

- `2026-10-23` Built and checked as above. No portal entry exists yet (P-08-T07): the import rules
  apply to its paths as they land, and the tests lint virtual files at those paths.

## Decisions made during this task

| Decision | Reason | Needs ADR? |
|---|---|---|
| Portal specimens are marked in the registry (`surface: "portal"`) rather than listed in the tests | A new portal specimen joins the crawl without editing a test | no |
| Legacy screens and the gallery are outside the portal's import boundary | They belong to the firm bundle (ADR-163 decision 1: the portal bundle has no firm chunk) | no |
