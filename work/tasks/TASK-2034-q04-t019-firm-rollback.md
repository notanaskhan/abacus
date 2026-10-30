---
id: TASK-2034
title: Q-04-T019 Rollback rehearsal on the production canary; docs/runbooks/firm-rollback.md
spec: SPEC-402
acceptance_criteria: [AC-4]
risk_zone: red
status: blocked
epic: Q-04
plan_key: Q-04-T019
branch: s15c-q04-t019
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Flags off for the canary, A-01 export package for one engagement, `shasum -a 256 -c
checksums.sha256`, import into a blank workpaper folder; the canary rollback completes inside 60
minutes with checksums verified and the runbook's last-rehearsed date set.

## Plan (red: written before the code)
- `docs/runbooks/firm-rollback.md`: decide, flags off (`make flag … ALL_OFF=1`, keeping the
  export on until the packages are out), export per engagement (RB-33 §3), verify in a blank
  folder, close; minute targets; the rehearsal table.
- `abacus_tools.package_check`: unpack into a folder that does not exist, refusing an absolute
  path, a `..` part, a symlink, a duplicate entry or more than `--max-bytes` before writing; verify
  both checksum files, refuse unlisted files, cross-check `manifest.json`; JSON of counts and paths.
- SPEC-402 AC-4; tests `backend/tests/unit/tools/test_package_check.py` (run at the end review).
- Rollback: delete the tool and the runbook.

## Blocked on
The production compute stack and the canary tenant (`infra/envs/production` has no compute yet), so
the rehearsal itself cannot run. When it can, the table at the end of the runbook takes the times.

## Progress log
- 2026-10-30: runbook, package check, AC and tests built; the canary rehearsal waits on production.
