---
id: TASK-091
title: Design foundation, step 1 — the plan's tokens and Geist fonts replace the SPEC-016 "Atelier" theme, and the shared components are restyled (pill buttons, panes on rings, recessed fields, band table headers, the new dialog, error and empty states, the atom agent mark)
spec: SPEC-016
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-091-design-foundation
worktree: spec005
created: 2026-10-19
updated: 2026-10-19
---

## Objective
Make the app look polished with one change, following the plan's `cross/design-foundations.md`: greige surfaces, espresso ink, olive/ochre/brick statuses, Geist 400/500, no serif, and rings instead of borders.

## Scope
**In**
- `packages/ui/src/theme.css`: the plan's tokens (surfaces, ink ladder, dark fills, status families, match colours, radii, shadows e1/e2/e3/pop/menu/modal). Geist and Geist Mono are self-hosted (Fontsource; CSP unchanged).
  - Tailwind's size scale is mapped onto the plan's type roles.
  - `font-semibold` and `font-bold` render at 500.
  - The SPEC-016 token names stay as aliases, so every screen takes the new look at once.
- Restyled shared components: Button, Badge and StatusPill, Card, Panel, Input and Label, Table/Th/Td, Dialog, Alert, EmptyState, Skeleton, Spinner, Rail.
- `AiTag` becomes the atom agent mark, with "AI" kept for screen readers.
- Selected and internal-note styles on five screens no longer use heavy accent or dashed borders.

**Out (later steps)**
- Shell (step 2): the icon rail becomes the toolbar; the compact record header with one agent-status control.
- New components: DataTable grammars, Drawer, citation popover, source viewer, toast with Undo.
- Lint changes from plan §3.5; resetting Tailwind's default namespaces; removing the Source Sans 3 and Newsreader packages; a superseding spec for SPEC-016 §4.

## Plan
Approved by founder (2026-10-19, "proceed with step 1"). Paths: `packages/ui/**`, `pnpm-lock.yaml`, `docs/architecture/dependency-allowlist.yaml`. Approval file: `work/approvals/TASK-091.yaml`, expires 2026-10-26.

## Definition of done
- [x] Web tests pass (353); the screens checked on the dev stack.
- [x] `make check-fast` passes.
