---
id: TASK-7200
title: S0-S25 skipped non-code rows closed out (DEC-4200)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]  # every OPS, VENDOR, DOC and TEST row of S0-S25 has a status backed by evidence or a recorded decision
risk_zone: green
status: in-review
epic: Q-03
plan_key: S0-S25 bookkeeping
branch: s0-s25-nocode-closeout
created: 2026-11-10
updated: 2026-11-10
---

## Objective

Give each of the 785 skipped OPS, VENDOR, DOC and TEST rows of sprints 0 to 25 a status. A row counts
as done only with evidence. The pen-test and accessibility deferrals stand (DEC-1389, DEC-1391). Ayush's
2026-11-10 deferrals are recorded. The two-founder rituals are closed under the solo edition. The
pilot-firm rows are left to the PF-X1 session. Every human and ops row is listed by owner and by what
unblocks it.

## Method

For each row, look for: a commit body on `origin/main` (3e4935e86) naming the id (ranges like
`T182–T186` and `T22/T23` expanded); the `work/tasks/TASK-*.md` whose `plan_key` names it; a file named
after it (`test_q04t004_*`); a mention in `docs/`; `status-verified.csv`; the deferral files. Rows whose
acceptance needs a staging, production or live-firm run are partial, with the open clause in
`status-verified.csv`.

## Result

See `docs/plan/status/S0-S25-leftovers.md` and DEC-4200: 420 built (337 done, 83 partial), 28 newly
deferred, 29 deferred before, 95 rituals cut, 87 pilot-firm rows untouched, 126 human and ops rows.

## Progress log

- 2026-11-10: classified, recorded, `register_ids` clean. `test_validate_docs.py` has one red that is
  already on main and not caused here: `work/tasks/TASK-5901-qbo-revoke-and-tid.md` names a spec that
  does not exist.
