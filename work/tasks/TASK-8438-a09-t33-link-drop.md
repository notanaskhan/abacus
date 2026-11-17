---
id: TASK-8438
title: "A-09-T33: rest: POR-23 picker links a drop to its deliverable"
spec: SPEC-658
acceptance_criteria: [AC-7]
risk_zone: amber
status: in-review
branch: s48r-link-drop
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: A-09-T33
---

## Objective
A drop with no deliverable was kept but could never be linked. POST /v1/portal/component-rooms/{id}/drops/{evidence_version_id}/deliverable links the person's own drop to one of this room's deliverables (component_deliverable.upload).

## Plan (amber)
1. evidence.api.component_upload_of: a component_auditor_upload version's item, engagement and portal person; None for any other version.
2. component_room.link_drop: own drop, this engagement, this room's deliverable, not already linked, else 404; then receive_deliverable (409 when the deliverable is closed).
3. Portal route and contract row; unit tests for the link and the five refusals.

## Progress log
- `2026-11-17` — Built (S48 rest). The other T33 note (the PDF without a C10 publish) is not scope: A-09 asks for the C11 PDF and a download, which T33 serves; C10 is not named for the instructions. Gates and tests run once at the S48 end pass (build first, test last).
