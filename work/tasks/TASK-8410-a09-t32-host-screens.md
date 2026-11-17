---
id: TASK-8410
title: "A-09-T32: Host screens live before the window"
spec: SPEC-658
acceptance_criteria: [AC-1, AC-7]
risk_zone: green
status: in-review
branch: a09-t32-host-screens
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T32
---

## Objective
Spec section: docs/plan/epics/A-09.md §5. Host screens live before the window: AUD-02 h Group band, AUD-01 group rows and tag, ENG-03 g toggle, AUD-06 g entity strip unmasked, SHL-18 f shared-thread anchor, portal landing /component-room under the reduced shell.

## Plan (green)
1. AUD-02 h: fixture scenario (Harlow & Pike, revision h's three Group rows and copy) through `harlowCockpit`; the live rail draws the API's `group` band rows (A-09-T30).
2. AUD-06 g: the TB pane reads `GET /v1/audits/{wid}/group/entities` behind `assurance.group_audit` and draws the strip from live entities (the planned-only fixture strip stays for other builds).
3. POR-23: `/component-room` routes to the new live screen (reduced shell, one nav item 'Group audit'): intro, n of N, the sent instructions and Acknowledge (confirm dialog, Idempotency-Key), deliverables in client words, Questions with the composer; `GET /v1/portal/component-rooms` (the person's rooms) added for the landing.
4. AUD-01 tags come from the API (A-09-T30's `group` and `component_auditor` sources); ENG-03 g's toggle already exists (A-09-T07).
5. Tests: `apps/web/src/screens/POR-23/copy.test.ts`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack. tsc and eslint clean; client regenerated. Partial: ENG-03 g does not yet pick component entities (the backend accepts `component_entity_ids`); AUD-01's nested component rows under the group row and SHL-18 f's shared-thread anchor chip are not drawn; POR-23 uploads (file picker and drop zone) and the full-letter reader are not wired on the page (the routes exist); no POR-23 fixture scenarios or Tier C parity yet; AUD-02 h's tie chip 'Balanced · 50,760,000' is not drawn (the row model has no chip). Gates and tests run once at the S48 end pass (build first, test last).
