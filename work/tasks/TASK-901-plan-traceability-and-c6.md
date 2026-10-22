---
id: TASK-901
title: "Trace the parallel stream's work to plan rows; C6 v0 contract doc; fresh MFA on trace export; manifest paths"
spec: SPEC-318
acceptance_criteria: [AC-6]
risk_zone: amber
status: done
branch: task-901-traceability
worktree: agentwt
created: 2026-10-22
updated: 2026-10-22
---

## Plan keys
P-09-T11, Q-02-T45 (partial); plan traceability for the rows listed in reconcile-2026-10.md.

## Plan
- **Plan rows:** 19 rows in `docs/plan/backlog.csv` move from todo to partial, by in-place line edits. Each has an evidence row in `status-verified.csv` and a reconcile addendum.
- **Task files:** TASK-321 to TASK-461 and TASK-900 each gain a "Plan keys" section.
- **C6 doc:** `docs/contracts/agent-runs.md` records v0 as live and lists what v1 changes. The register row is updated.
- **Fresh MFA:** `run_trace.export` now needs `mfa_recent`, as P-09-T11 asks. The trace drawer shows "Confirm it's you" when that's missing.
- **PDF export** is deferred: there is no PDF renderer on the dependency allowlist, and C11 is planned for S18.
- **Route manifest:** ENG-12, WB-09 and AUD-19 now point at the legacy screens, following the ENG-01/02 precedent. AUD-31 is left alone because mapping sits inside the Trial balance tab.
- **Comments:** stale TASK-346 references become TASK-460.
- **Rollback:** revert the PR.

## Progress log
- spec318runs (5 tests, including the MFA prompt) and the route manifest tests pass.

## Definition of done
- [x] Matrix pins, independence and app-gates tests pass.
- [x] check-fast passes.
