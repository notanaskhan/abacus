---
id: TASK-2819
title: A-04-T11 workpapers.section_drafter capability
spec: SPEC-620
acceptance_criteria: [AC-1, AC-6]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T11
branch: s23-a04-t11
worktree: /Users/ayushkbhatia/Accrued/abacus-s23
created: 2026-11-01
updated: 2026-11-01
---

## Objective

A-04 §3.1 AC1.1, §6 AC6.1: the single section-drafter capability (spec, workflow, gate). It drafts cited workpaper values as suggestions only, and validates the pack by code before any model call.

## Acceptance (backlog)

On the fake model a draft writes cited suggestions only, an uncited value is dropped and flagged Unsupported, an uncleared real firm gets 409 drafting_not_enabled, and the seeded pack error fails the run before any model call.

## Plan

- **Spec** `agents/specs/workpapers.section_drafter.yaml` v1. Five modes; the four non-default modes are `AgentMode`, which `spec.py`'s literals now accept. Compiled into `_specs.py` by `make regenerate`.
- **Prompt** `ai_gateway/prompts/workpapers.section_draft/v1.txt`, the base prompt for every mode.
- **Handoff** `SectionDraft`: cells by reference; a value is text or a fact reference; citations name a step `S<n>`, or a document `D<n>` and its page.
- **Workflow** `SectionDraftWorkflow` and activity `section_draft.draft`. Input: identifiers and codes only.
- **Drafter** `agents/section_draft.py`:
  - `start`: the route's slot. 409 `drafting_not_enabled`, `action_cap`; one run per idempotency key.
  - `draft`, in order:
    1. Load context.
    2. Validate the pack.
    3. Call the gateway.
    4. Verify citations through C4 (v2 rows anchored on the run).
    5. Check number provenance.
    6. Write the suggestions.
    7. Finish the run.
- **Workpapers**:
  - `drafting.py`: `draft_paper`, `apply_cell_suggestion` (the person's adoption writes the next row and the next version) and `paper_engagement`.
  - The drafter slot.
  - `procedures.bound_steps`, and a pack validation scoped to the paper.
- **Methodology** `VersionStep.text`.
- **Matrix:**
  - `section_draft.run` for the agent through its task scope.
  - `workpaper.read` for the agent through its task scope.
- **Audit:** `section_draft.started` and `section_draft.failed`.
- **Tests:**
  - `tests/integration/backfill/test_a04t11_section_drafter.py`.
  - The A-04 stub test moves the draft route to SERVED.
- **Rollback.** No migration. Reverting the module code returns the route to 501. Runs and suggestions already written stay; they are insert-only history.

## Decisions made during this task

DEC-1868.

## Progress log

- `2026-11-01`: built spec, prompt, workflow, drafter, applier, docs and tests. The tests have not run yet; they run in the end pass, by the build-first rule.
  - Deferred:
    - The replay history goes to T41.
    - Mode prompts and mappings go to T22–T35.
    - The eval suite goes to T14.
