---
id: TASK-425
title: T7 PortalLayout (split, reduced, mobile), MobileTabBar with More sheet, PortalBrand provider with slots only (F-05-T35)
spec: SPEC-048
acceptance_criteria: [AC-3, AC-8]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T35
branch: f05-t35-portal-layout
created: 2026-10-23
updated: 2026-10-23
---

## Objective

"T7g and T7-M at 390px with the 64px bottom tab bar render, Approvals hides for an individual
client, and the brand type has no colour fields." (F-05-T35)

## Scope

**In** (`packages/ui`)

- `brand/portal-brand.tsx`: `PortalBrand`, the view model of `GET /v1/portal/branding` with the
  ADR-163 slots only (name, portal name, logo, mark, address line, help and privacy links, support
  contact, `securedFooter`, sign-in methods, maintenance banner); `PortalBrandProvider` and
  `usePortalBrand`, which throws outside a provider (the portal has no default brand);
  `PORTAL_BRAND_SLOTS`, held to the type by the test.
- `layout/mobile-tab-bar.tsx`: `MobileHeader` (56: firm mark 20, name 15/500, the 28 account glyph
  in a 44 target) and `MobileTabBar` (64: Home · Documents · Sign · Messages · More; icon 20 over
  11; the More sheet with ↑ ↓ Home End, Escape and outside tap, focus return; `forceState="open"`);
  `splitMobileNav`.
- `templates/portal-layout.tsx`: `PortalLayout` in `split` (PortalToolbar, 336 rail, flex pane),
  `reduced` (one centred 720 pane, T7g) and `mobile` (T7-M, 390); `portalNav(kind, counts)` with
  Approvals for entity clients only; `PORTAL_AREAS`.
- Specimen `t7-portal-layout`: split, T7g, T7-M, T7-M with More open, an entity client at 390 and
  at 1400, and the Secured by footer turned on.
- Tier D rows: the mobile header 56 and the tab bar 64.

**Out**

- The C-16 Request kit that fills the panes (F-05-T36) and the T7a to T7f artboards.
- Parity entries: the T7/T7-M PNGs show the Request kit's content; they arrive with F-05-T36.
- `/v1/me.portal.shell` (C5, P-08 portal half): not built. The app passes the variant and the
  client kind until it lands; `F-05-T44` adds the consumer test.

## Plan (amber: written before building)

Files: the three source files above, `specimens/portal.tsx`, the index lines in `brand/index.ts`,
`layout/index.ts`, `templates/index.ts`, `specimens/index.ts`, `tokens/DECISIONS.md`, and
`apps/web/e2e/visual/tier-d.spec.ts`. No migration, no registry or flag edit, no dependency, no API
change. Rollback is a revert of the one commit.

Tests (`templates/portal-layout.test.tsx`, 21):

- brand type has no colour fields → "the brand type has no colour fields" (the slot list equals the
  type's keys both ways, no slot names a colour) and "has no default".
- Approvals hides for an individual client → `portalNav` for both kinds, the 1400 toolbar, the 390
  More sheet.
- T7g and T7-M at 390 with the 64 bar → "T7g reduced", "T7-M renders at 390 with the 56 header and
  the 64 bottom tab bar", "T7-M targets are at least 44 high"; Tier D computed heights in a real
  browser.
- The More sheet's keyboard and dismissal; white label for all three variants with the footer off
  and on.

## Definition of done

- [x] `vitest run src/templates/portal-layout.test.tsx`: 21 passed.
- [x] `tsc --noEmit` for `packages/ui`; `apps/web` shows only the generated client's existing
      `exactOptionalPropertyTypes` errors.
- [x] eslint and prettier on the changed files.
- [x] Tier D rows (`playwright --project=visual tier-d.spec.ts -g portal`): 3 passed.
- [x] `e2e/a11y.spec.ts` over the gallery.

## Progress log

- `2026-10-23` Built and checked as above. ADR-163 (P-11) landed on `main` during the task; the
  brand's slots follow its branding payload.

## Decisions made during this task

Recorded in `packages/ui/src/tokens/DECISIONS.md`, "T7 PortalLayout (F-05-T35)": the bottom tab bar
over the T7-M pills (DEC-45), the 28 phone radius, ink-3 inactive tabs, More reading current for an
area under it, slots-only brand with no default, Approvals by client kind, and the variant passed by
the app until C5's portal half lands.
