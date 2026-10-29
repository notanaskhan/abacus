---
id: TASK-2035
title: Q-04-T020 PW1 on-call rota in docs/ops/on-call.md
spec: SPEC-402
acceptance_criteria: [AC-5]
risk_zone: red
status: blocked
epic: Q-04
plan_key: Q-04-T020
branch: s15c-q04-t020
created: 2026-10-30
updated: 2026-10-30
---

## Objective
N primary for SEV1/2, AY named backup, quiet hours in writing, firm QI contact per pilot code, test
page; a test page reaches N and escalates to AY after 15 minutes, and every PW1 day has a named
backup.

## Plan (red: written before the code)
- `docs/ops/on-call.md`: rules (SEV1 pages both 24x7; SEV2 escalates after 15 minutes; SEV3 never
  pages; quiet hours 9 PM–7 AM CT and weekends, suspended in deadline weeks), the PW1 window, the
  week-by-week rota, the firm QI contacts as vault references, the test-page record. `updated:`
  frontmatter, which `go_live`'s `operations.on_call_current` already reads.
- `abacus_tools.quality.on_call` in check-fast: every window day covered once, backup a different
  founder, rows inside their window, pilot codes only, no phone or email, `updated:` present.
- SPEC-402 AC-5; tests `backend/tests/unit/quality/test_on_call.py` (run at the end review).
- Rollback: delete the checker and its Makefile line; the file stays.

## Blocked on
- The paging tool (Q-01-T41, Better Stack: status page, uptime checks and SEV1/2 paging) is not
  provisioned, so the test page cannot be sent. When it is: route SEV2 to N with a 15-minute
  escalation to AY, send the test alert, fill the test-page row.
- The QI contact per firm: no PW1 firm is signed yet (F-09); the vault entry is named when it is.

## Progress log
- 2026-10-30: rota, rules, checker, AC and tests built; the test page waits on Q-01-T41.
