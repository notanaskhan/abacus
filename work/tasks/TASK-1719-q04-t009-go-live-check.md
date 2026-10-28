---
id: TASK-1719
title: Q-04-T009 make go-live-check
spec: SPEC-403
acceptance_criteria: [AC-11]
risk_zone: amber
status: in-review
epic: Q-04
plan_key: Q-04-T009
branch: s14-q04-t009
created: 2026-10-28
updated: 2026-10-28
---

## Objective
`make go-live-check FIRM= LEVEL=shadow|client_facing|tax|season`: the dossier's evidence, read
rather than remembered, as JSON. Acceptance (backlog row): "On the production canary every
shadow-level item reports a value, and a tenant below 100% MFA or with a lapsed provider-terms
review fails with the item named."

## Plan (amber)
- `abacus_tools/go_live.py`: `Facts`, `collect` (public reads as the platform), `evaluate` per
  level (shadow 20 items; client_facing +8 with the Jan 15–Apr 15 blackout; tax +6; season +6),
  `report`, CLI.
- identity: `operator_posture(tenant)` (DEC-808), exported from `identity.api`.
- `Makefile` `go-live-check`.
- Rollback: revert; read-only throughout.

## Acceptance
| Check | Test |
|---|---|
| Every shadow item reports a value; a green firm passes; below-100% MFA and lapsed or missing provider terms fail named; each readable item fails on its own; level composition; blackout edges; season items; frontmatter reads | `backend/tests/unit/tools/test_q04t009_go_live.py` (22) |
| A real firm read as the platform: 0 of 3 staff MFA fails named; reads stay in the firm | `backend/tests/integration/backfill/test_q04t009_go_live_collect.py` (2) |

## Progress log
- `2026-10-28` — Built. 22 + 2 passed; ruff, pyright, lint-imports, banned patterns.
- Not done here: `abacus_tools.go_live` in `release.OPS_COMMANDS` needs the platform-ops
  contract (frozen v1) to name it; until then it runs from the ops shell like `make flag`.
  The production-canary walk waits for the canary.

## Handoff
- **Current state:** PR open, held for the batch (stacked on #576).
