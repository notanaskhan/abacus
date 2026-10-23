---
id: TASK-933
title: Journey harness core - assertInvariants UI layer, axeStep, persona adapters, four projects (F-04-T21)
spec: SPEC-307
acceptance_criteria: [AC-7, AC-8]
risk_zone: green
status: done
epic: F-04
plan_key: F-04-T21
branch: TASK-933-journey-harness-core
created: 2026-10-23
updated: 2026-10-23
---

## Objective
The journey harness every J-spec imports (F-04 §3.8, F-04.30 and F-04.32; ch. 04 §9.5): a `journey`
fixture that signs a persona in through its project's adapter and, after every step, runs axe
(serious and critical = 0, forced colors on the first step) and INV-1 to INV-5 on the page. Row
acceptance: "Harness runs in all four Playwright projects with axe serious and critical findings at
zero after every step." SPEC-307 has no harness AC of its own: AC-7 (the business clock) and AC-8
(fixture mode, `?as=` and the clock) are what the fixture adapter stands on; the harness behaviour
is F-04.30 and F-04.32.

## What changed
- `apps/web/e2e/harness/`:
  - `axe.ts`: `axeStep(page, step, {include, forcedColors})` (no rule-disable list; findings
    attached to the report), `settle`, `assertStill` (reduced motion).
  - `invariants.ts`: `assertInvariants(page, ctx)`, UI layer. INV-1 human verbs on
    `data-actor="agent"`; INV-2 agent-set values (`[data-actor="agent"][data-filled]`) need a verified
    citation or "Uncited", and an Uncited value's `data-human-verb` gate must be disabled; INV-3 a
    walled persona's page never names the walled client and no copy reveals a hidden count; INV-4 a
    portal persona never sees an out-of-scope name or "Accrued"; INV-3/INV-4 404 probes through the
    adapter; INV-5 never "<verb> by Accrued Agent". Failures name the step.
  - `personas.ts`: the ch. 04 §6.5 persona list (seed names), Lena Park walled from Ashford.
  - `adapters.ts`: `fixture` (`?as=&clock=`, page clock fixed, a placeholder fixture session in
    sessionStorage), `fullstack` (the local OIDC chooser by name; probes with the SPA's session),
    `staging` and `canary` (hosted WorkOS sign-in registered by F-04-T22 through
    `registerHostedSignIn`; until then they say so).
  - `index.ts`: `test` with the `journey` fixture (`as`, `step`), re-exports.
  - `harness.spec.ts`: the entry step as Hannah Leclerc, and the UI-layer rejections (clean page,
    INV-1, INV-2 ×2, INV-3 ×2, INV-4 ×2, INV-5).
- `apps/web/playwright.config.ts`: projects `fixture`, `fullstack`, `staging`, `canary` over
  `e2e/journeys/**` and `e2e/harness/**` (1440×900, reduced motion, en-US, Chicago);
  `ABACUS_FIXTURES=1` starts the fixture server; staging and canary take `ABACUS_STAGING_URL` /
  `ABACUS_CANARY_URL`. `chromium` no longer picks up journeys or the harness.
- `Makefile`: `journeys` → `--project=fixture`, `journeys-full` → `--project=fullstack`.
- `apps/web/e2e/journeys/README.md`.

## Progress log
- `2026-10-23 05:50` — fixture project: 8/8 (entry step with axe and forced colors, and every
  rejection). staging and canary: the 7 rejections pass; the entry step skips while their URL is
  unset (they run from the nightly and release jobs, F-04-T28). fullstack: the 7 rejections pass;
  the entry step was not run locally (needs `make dev` + `make seed-demo`; other agents held the
  local Docker). apps/web lint and typecheck clean (no new errors outside the known api-client set);
  `make check-generated` green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| The fixture adapter writes a placeholder session to sessionStorage | The SPA's layout redirects to OIDC without a token; fixture mode's API never reads it (ch. 04 §6.5: `?as=` replaces PKCE) | no |
| Staging and canary sign-in is registered by F-04-T22 | It needs the sink reader `mail.latest()`; no credential lives in the repo | no |
| The UI-layer rejections live in harness.spec.ts | They prove the helper fails; F-04-T30 adds the data-layer checker and `invariants.selftest.spec.ts` with injected audit events | no |

## Gotchas and discoveries
- `fetch` is banned in apps/web (ADR-011) including e2e; the probe uses `page.request` with the SPA's
  session headers.
- No new journey specs: J02/J12 skeletons are F-04-T26.

## Handoff
- **Current state:** done, merged.
- **Exact next step:** F-04-T22 registers the hosted sign-in; F-04-T26 writes J02-audit-core and
  J12-core on this harness; F-04-T28 wires the PR fixture job and the nightly projects.
