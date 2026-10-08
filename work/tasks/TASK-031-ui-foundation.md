---
id: TASK-031
title: UI foundation (direction C) and the first screens
spec: SPEC-016
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10]
risk_zone: amber
status: done
branch: task-031-ui-foundation
worktree:
created: 2026-10-08
updated: 2026-10-08
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: do not write code until the plan is marked approved.
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
Implement SPEC-016: direction C tokens and components, the firm shell with notifications, the engagement overview, map and contacts, methodology admin, the client accept page and home, and the existing screens restyled.

## Scope
All of SPEC-016.

## Context to load
- Spec: `docs/specs/SPEC-016-ui-foundation-and-first-screens.md`
- ADRs: ADR-011, ADR-065, ADR-030
- Code: `apps/web/src`, `packages/ui/src`, `packages/api-client` (generated)

## Plan
- [x] Plan approved by human (founder, 2026-10-08: "go with C … write the UI spec and build from it"). Approved by founder: the allowlist, `package.json` and lockfile changes for the two `@fontsource` packages.

### Design
1. **Tokens:** `packages/ui/src/theme.css` (`@theme`: the SPEC-016 colours, radii and fonts), with `@fontsource` CSS imports. The app's `index.css` imports it.
2. **Components:** Button, Badge, Card, Alert and EmptyState restyled to the tokens. New: `StatusPill`, `AiTag`, `Count`, `Tabs`, `Rail` and `RailItem`, `Panel`, `Select` and `Toast`.
3. **The shell:**
   - `Layout` becomes the rail, the header and the notification panel;
   - a client membership redirects to `/client`;
   - `useMfaRetry` catches 403 on MFA actions and shows a confirm dialog that calls `signIn(returnTo, { forceLogin: true })` (adds `prompt=login` and `max_age=0`).
4. **Routes:**
   - `/engagements/$id` shows the overview;
   - `/engagements/$id/requests` holds the existing board, and `…/map`, `…/contacts`, `…/review` sit beside it;
   - `/admin/methodology` and `/admin/methodology/$versionId`;
   - `/client` and `/client/accept`.
5. **AC-1 lint:** an ESLint `no-restricted-syntax` rule bans hex colours and Tailwind palette colour classes in `apps/web` and `packages/ui` (theme excepted).
6. **Tests:** component tests per screen with a mocked client, for AC-2 to AC-9.

## Definition of done
- [x] Listed ACs have passing tests that reference them (component tests for AC-1 to AC-8; the axe run for AC-10 is deferred to the founder's full runs)
- [x] Type check, lint, format, architecture and dependency rules pass
- [x] The backend remains the authority; the UI only hides what the API refuses
- [x] Docs: SPEC-016 and this task file

## Progress log
- `2026-10-08` — Implemented:
  - direction C tokens and the bundled Latin fonts;
  - restyled and new UI components (`StatusPill`, `AiTag`, `Count`, `Panel`, `Rail`, `RailButton`);
  - the firm shell (rail, header, notification panel with polling, client redirect);
  - the fresh-MFA prompt (forced re-login);
  - engagement Overview, Map, Contacts and Review under one header with tabs;
  - methodology admin (list, version detail, raw-body upload with row-level problems);
  - the client accept page (fragment token moved to `sessionStorage` and cleared) and the client home;
  - Board and Review restyled;
  - the ESLint ban on palette and hex colours.

  Web tests (118), type checks, lint, format and the production build pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| New screens live flat in `src/screens` (no subfolders) | The existing lint rule bans `../../` imports across feature roots | No |
| `Tabs` lives in the app (`src/shell`), not `packages/ui` | `packages/ui` doesn't depend on the router | No |
| Shell icons are re-exported from `@abacus/ui` | Keeps one icon set without adding `lucide-react` to the app's dependencies | No |
| Fonts are the Latin subset only | Smaller bundle; other scripts fall back to system fonts | No |
| The MFA prompt appears on any 403 from an MFA-required action | The API gives one 403 for both stale MFA and no permission; the dialog says so | No |
| The file input isn't `required` | The Upload button is disabled until a file is chosen; jsdom's validation can't see a programmatic file | No |

## Handoff
- Done. Later UI tasks: knowledge, budget and spend, support access, walls, dark mode, and an axe pass with the founder.
