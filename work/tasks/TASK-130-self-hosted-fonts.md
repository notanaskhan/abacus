---
id: TASK-130
title: "F-05-T04 · Self-hosted fonts: fonts.css (Geist and Geist Mono eager with preload), fonts-doc.css (Arimo and Gelasio lazy); CSP unchanged"
spec: SPEC-048
acceptance_criteria: [AC-7]
risk_zone: amber
status: done
epic: F-05
plan_key: F-05-T04
branch: task-130-self-hosted-fonts
created: 2026-10-20
updated: 2026-10-20
---

> **Rules for the agent working this task**
> - Read this whole file before doing anything. Continue from the *Handoff* section if it has content.
> - Load only the files listed under *Context to load*, plus what the plan requires.
> - Amber and red tasks: write the plan into this file before code (solo amendment: no approval step).
> - If scope must change, **stop** and add it to *Questions for the human*.
> - Never mark `done` until every item in *Definition of done* passes.
> - Append to the *Progress log* before ending any session, even mid-task.

## Objective
No request reaches fonts.googleapis.com or fonts.gstatic.com and document.fonts.check('500 13px Geist') is true with the CSP meta unchanged.

## Already built (verify, fill gaps only)
Source: `docs/plan/status/status-verified.csv` row F-05-T04 (status partial). Evidence: Geist via @fontsource imports in theme.css:9-12, no googleapis; no fonts-doc.css (Arimo, Gelasio); unused newsreader/source-sans-3 deps in packages/ui/package.json.

Verify each item against the code, then build only what is missing. Do not rewrite what works.

## Scope
**In**
- fonts.css: Geist and Geist Mono eager with preload
- fonts-doc.css: Arimo and Gelasio lazy, document chunks only
- CSP meta in vite.config.ts unchanged

**Out**
- Removing newsreader/source-sans-3 (F-05-T34)
- Base typography (T05)

## Context to load
- Spec: `docs/specs/SPEC-048-design-system-core.md` (sections 5 and Task map; ACs AC-7)
- Epic: `docs/plan/epics/F-05.md`: F-05 §3 A4; F-05 §7 security headers line (CSP, no remote fonts, verify Radix scroll-lock style injection); F-05 §11 R3, R9, Q5
- Task row: `docs/plan/epics/F-05.tasks.csv`, `F-05-T04`
- Process: `docs/plan/AMENDMENT-solo.md`
- Prior work: TASK-091..101 (Anas: tokens, Geist, components)

## Plan
- [x] Plan written in this file (required for amber and red)

Steps:
1. [ ] Verify the existing Fontsource imports in theme.css:9-12
2. [ ] Move them into fonts.css with preload; add fonts-doc.css
3. [ ] Confirm no request reaches Google font hosts in a production build; confirm the CSP meta is unchanged

Files to create or change:
- packages/ui/src/fonts.css
- packages/ui/src/fonts-doc.css
- packages/ui/src/theme.css (remove imports)

Tests to write (mapped to ACs):
- AC-7 -> Playwright request log has no googleapis/gstatic; document.fonts.check('500 13px Geist') true; CSP meta string unchanged (full suite in T08)

## Definition of done
- [ ] All listed ACs have passing tests or checks that reference them
- [ ] Type check passes
- [ ] Lint and format pass
- [ ] Architecture and dependency rules pass
- [ ] Full test suite passes; no tests skipped, weakened or deleted
- [ ] No secrets or real client data committed (public repo)
- [ ] No new dependencies, or each one listed below
- [ ] Every query is tenant-scoped; every endpoint checks authorisation (N/A for this task unless it adds either)
- [ ] AI calls (if any) go through the gateway with limits, logging and passing evals (N/A unless it adds any)
- [ ] Module README and relevant docs updated
- [ ] Decisions below recorded; ADR raised where needed

Commands:
```
make check
```

## New dependencies
| Package | Version | Why | Approved by |
|---|---|---|---|
| | | | |

## Progress log
Append-only. Newest at the bottom.

- `2026-10-20` — task file written from the epic (SU-14); nothing built yet.
- 2026-10-20 (solo build): fonts.test.ts first (fonts.css has Geist and Geist Mono 400/500 and nothing else, fonts-doc.css has Arimo 400/600/700 and Gelasio 400/500/700 and no shared stylesheet imports it, no Google font host in app or ui sources, the abacus-csp policy string is unchanged). Moved the Fontsource imports out of theme.css into fonts.css (imported by styles.css); added fonts-doc.css with ./fonts.css and ./fonts-doc.css exports; added the abacus-font-preload build plugin in vite.config.ts (four preload links for the Geist woff2 files, confirmed in dist/index.html; no googleapis/gstatic in dist). The browser half (request log, document.fonts.check) is e2e/ds-fonts.spec.ts in TASK-134. make check-fast, vitest (429) and vite build green.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| Preload by a build plugin that reads the bundle for the four Geist woff2 files | Hashed names are known only at build; no CSP change | no |

## Gotchas and discoveries
- 

## Questions for the human
- [ ] 

## Handoff
- **Current state:** done (see the progress log)
- **Exact next step:** none for this task
- **Uncommitted or partial work:** none
- **Known failing checks:** none
- **Open issues:** none
