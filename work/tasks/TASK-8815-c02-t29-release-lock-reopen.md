---
id: TASK-8815
title: "C-02-T29: Release, client approval, lock and reopen"
spec: SPEC-000
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s52-c02t29
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-20
updated: 2026-11-20
plan_key: C-02-T29
---

## Objective
Priya's release at 4:25 PM publishes to POR-09 with an approval item for Tess Moreno and Ben Ashby, a manager's release is refused, and Lock is refused before the client approves.

## Done
- closes/release.py: release (partner, live human, fresh MFA, preconditions re-checked under the close lock, P-04 L2 sign-off on close, Approved, single-use grant issued and consumed, C11 render_final via the release approval provider, released_by/at), deliver (after the final render: C10 publish kind close_package with the AR-C 70 legend and approval_kind fs_package, Deliverable ready template row to owner and approver of record, Delivered), lock (409 client_approval_required), reopen (close_reopenings, In review, close.reopened)
- FsPackageApprovals C18 provider (Approved by client, package_client_approved to the releasing partner) registered from closes.api
- PackageAssemblyWorkflow release mode; close_package kind's approval provider is the release
- routes release, lock, reopen; reviewed audit actions
- unit tests test_c02t29_release.py

## Progress log
- `2026-11-20` — Plan (amber, protected release path): service, provider, workflow mode, routes, tests; rollback revert (no migration). DB-backed walk (POR-09 item for Tess Moreno and Ben Ashby) at the end pass.
