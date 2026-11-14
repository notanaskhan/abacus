---
id: TASK-7957
title: "S43 end pass: gates, targeted tests, security review and one fix round"
plan_key: Q-03-T290
spec: SPEC-000  # row: S43 end pass (Q-03-T290 to T293)
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: s43-end-pass
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

# S43 end pass

Stacked on `f07-t23-tier4-docs` (#1987), the tip of the S43 stack (#1952 to #1987).

## Plan

Build first, test last (the S43 instruction): every S43 row was built and opened as its own PR
with `[skip ci]`; this pass runs the gates and tests once over the whole stack, fixes what they
find in one round on this branch, and the stack merges with one CI run on its tip.

## What ran (locally, 2026-11-14)

- Stage 1: ruff format and lint, pyright (0 errors on every changed file), lint-imports (9 kept),
  banned_patterns, error_codes (`--write`: three new codes), validate_docs, scope_guards,
  tool_registry, seed_contamination, fresh_mfa, generator_coverage, quarantine, feature_requests,
  on_call, register_ids, pilot_log, fakes, mutation and coverage floors, secrets_scan,
  check_dependencies, check-generated, check-heads: all pass.
- Unit tests, `-n 8 --dist loadfile`, over the modules S43 touched (agents, workbench, tax,
  practice, briefing, evals, identity, requests, evidence, synthetic, kernel, quality, api, tools,
  scenarios, ai_gateway, organisations, root unit tests, contracts f07_tier4): 44,215 passed and
  13 failed first; 11 fixed here, 2 are local environment only (below).
- Web and ui: tsc clean, eslint clean on every changed file (13 fixed), vitest `--changed
  origin/main` (ui 113 passed; web 3,374 with 6 fixed here).
- Not run locally (Docker down): integration tests and the DB-bound security matrix
  (`tests/security/test_permission_matrix_generated.py`, testcontainers). The CI run on the
  stack's tip covers them.

## Fix round

- Generated `tests/security/test_route_introspection.py` was hand-edited in W-02-T21: regenerated
  with `abacus_tools.codegen.security_tests` (a protected path; mistake recorded below).
- OWN-001 and BOUND-002 (DEC-4946): drill writer and Today context through agents' slots.
- Portal freeze (DEC-4947): `WorkbookAction` restored; `memo_actions` added.
- L12: `ask` to `post_question`, `history` to `past_briefs`.
- ACTOR-first: `run_artifacts._readable` tests the actor kind before `client`.
- Task files: `spec` must be a bare SPEC id and criteria ids the spec defines (validate_docs).
- Tests carried S43's additions: two new tools in the first-tools sets, three Ridgeline snapshots,
  Run 3 in the entity slice, `only_refs` in the frozen suite's accepted `binders.read` arguments
  (thresholds untouched), `_edited`'s labels optional.
- Web: Regenerate opens a dialog so reads "Regenerate…" (the kit's rule); format.ts and clock.tsx
  in place of `toLocale*` and `Date.now`; TXP-10 and TXP-01 tests query the right elements.

## Security review (red diffs, inline)

W-02-T19 plans and items retry, T-05-T60 export, I-02-T14 Today questions, W-02-T20 artifacts and
drill, I-02-T20 and T-05-T64 eval clearance, the W-02-T21 `_head` change, I-02-T22 subjects.
No open finding. Hardened here: the drill replay lookup answers the session's owner only.
Checked: firm-level `_head` is the initiator's alone (404 otherwise) with the action at firm level;
plan labels are bounded (200) and change no step's effect; the Today turn never plans and its
audit names ids only; availability is read before any write; export's Unmapped gate runs before
the grant is spent and export stays person-only; downloads are audited with a sanitised name;
the briefing call names its TRI subjects.

## Known local-only failures

`tests/unit/kernel/test_classification.py` ac19 and ac20 import every model, including the PDF
renderer, which needs the system `libgobject-2.0` (not installed on this laptop; CI has it).

## Progress log

- 2026-11-14: end pass run and fixed as above; mistake twice-check: hand-editing a generated file
  (route introspection) — the generator exists; `check-generated` caught it.
