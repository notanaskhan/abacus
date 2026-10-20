---
id: TASK-314
title: "F-03-T08: module pre-registration — 16 empty packages, the plan's module graph, fail-closed registration slots"
spec: SPEC-306
acceptance_criteria: [AC-1]
risk_zone: red
status: done
branch: task-314-preregistration
worktree: spec005
created: 2026-10-21
updated: 2026-10-21
---

## Plan (ADR-140; chapter 03 §2.2–2.4)
- **16 new packages**: methodology, review, collaboration, workpapers, adjustments, signatures, integrations, reporting, assurance, attest, tax, closes, notices, workbench, practice, portal.
  - Each has an empty `api.py` (`ROUTERS = ()`), an empty `registry.py`, and a README naming its zone and future tables.
  - All are in `MODULES` (30 modules, including today's `fieldwork`).
- **`MODULE_DEPENDENCIES`** becomes the plan's graph, with identity and platform under every module.
  - Today's real edges are kept: agents → fieldwork, and fieldwork's own (it splits into workpapers and assurance later).
  - Tests check the graph is acyclic, that nothing imports the edge modules, and that shared engines never import a service line.
  - The BOUND-002 tests that pinned the old map now pin the plan's.
- **Fail-closed slots**:
  - `engagements.register_work_item_kind` / `work_item_provider`: unregistered gives 409 `unknown_work_item_kind`;
  - `engagements.register_gate_provider` / `gate_fact`: unregistered is unmet;
  - `identity.register_scope_resolver` / `resolve_scope`: unregistered is denied;
  - `identity.register_consent_check` / `consent_given`: unregistered is not given;
  - `platform.register_search_projection` / `search_document` (the C15 slot): unregistered is not indexed.
- The import-linter layering contract now covers the new packages.

## Not in this task
- The `_protected.py` and CODEOWNERS edits. The solo edition (SU-06) dropped code owners, and protected paths now lock only secrets, generated files and applied migrations.
- The slots of later epics (review, collaboration, evidence, agents, communications, notifications) arrive with their modules.

## Definition of done
- [x] `tests/unit/api/test_preregistration.py` (8) passes.
- [x] The unit suite (12,229) passes.
- [x] import-linter: 4 contracts kept.
- [x] check-fast passes.
