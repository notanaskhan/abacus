---
id: TASK-1720
title: Q-04-T010 Flip ops-request check (flip-precheck)
spec: SPEC-403
acceptance_criteria: [AC-12]
risk_zone: red
status: in-review
epic: Q-04
plan_key: Q-04-T010
branch: s14-q04-t010
created: 2026-10-28
updated: 2026-10-28
---

## Objective
A per-firm flip is a reviewed `flip-<date>-<code>.yaml` request; `flip-precheck` refuses it
before approval unless its journeys are green on staging within 24 hours, it names a shadow run,
the approver is not the operator and the slot is valid for the firm's window. Acceptance (backlog
row): "A flip request whose journey last passed on staging 25 hours ago, or that names no shadow
run, fails CI and cannot be approved."

## Plan (red)
- `abacus_tools/flip_request.py`: `parse`, `precheck`, `argv`, `greens_from`, CLI `precheck`.
- `.github/workflows/ops-request.yml`: `flip-precheck` on PRs adding `flip-*.yaml` (reads the e2e
  workflow's staging job; read-only, pinned actions).
- `release.py ops-request`: a `flag_flip` file becomes the flag CLI's command; `flags.py`
  `--request-sha256`; `flip_guard` accepts the fingerprint in place of the file.
- `deploy/production/ops-requests/README.md`; DEC-809.
- Rollback: revert; no flip request exists yet.
- Human to-do: make `flip-precheck` a required check for `deploy/production/ops-requests/flip-*`.

## Acceptance
| Check | Test |
|---|---|
| 25-hour-old journey fails, 23.9 h passes; no shadow run refused; approver = operator; registry journeys; slot rules; hotfix; pilot code; flag and value | `backend/tests/unit/tools/test_q04t010_flip_request.py` |
| Merged request → flag CLI argv with the fingerprint; the guard records it; a plain request still cannot name the flag CLI | same |
| CLI exit 1 naming the reason; workflow shape (trigger, read-only permissions, pinned) | same (26 tests) |

## Progress log
- `2026-10-28` — Built. 26 passed; flip guard, release, deploy-workflow and release-path suites
  (67) still pass; ruff, pyright, lint-imports, secrets scan, banned patterns.

## Handoff
- **Current state:** PR open, held for the batch (stacked on #578).
