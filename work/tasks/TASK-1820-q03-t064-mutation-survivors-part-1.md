---
id: TASK-1820
title: Mutation survivors part 1, identity/authz (Q-03-T064)
spec: SPEC-000  # chapter 10 §10.4.4 and the Q-03-T064 row; each file cites the contract it is written from
acceptance_criteria: [AC-1]  # Q-03-T064: identity/authz to its M8 target (85%) or an approved equivalence note per survivor
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T064
branch: s13r-q03-t064
created: 2026-10-29
updated: 2026-10-29
---

## Objective
New tests for surviving mutants in identity/authz (then kernel and evidence), written from the contracts; the score rises toward M8's 85% (QD-4), or a survivor gets an equivalence note AY approves.

## Starting point (weekly run 40625075584, 2026-10-28)
identity/authz 62.2% (1,203 killed, 548 survived, 182 with no covering unit test). Survivors by function: `line_reach` 88, `authorise_own` 85, `authorise` 69, `condition_facts` 52, `visible_by_role` 47, `line_reader` 36, `visible_clients` 35, `visible_scope` 27, `authorise_on_condition` 26, `holds_engagement_role` 25, then 19 or fewer each. Mutation runs only the container-free suites, so functions reached only by integration tests survive: that is the pattern here.

## Part 1 (this PR): 173 of the 548 targeted
- `tests/unit/identity/test_q03t064_authorise_own.py` (14): `authorise_own` had no unit test. Each refusal layer (relationship for support, a client user, an agent or system actor, no membership or a client one; role for a refused or overridden cell or a conditional rule; attribute for stale or missing MFA at the 15-minute boundary), the cell a firm role, a partner level or neither takes, the check recorded only when allowed.
- `tests/unit/identity/test_q03t064_line_reach.py` (21): `_line_reader_cell`, `_may_read_lines`, `_line_reader` fact by fact, and `_line_reach`'s SQL compiled with literal binds, every clause of the rule pinned (enabled, visible to the line, never audit; active onshore non-admin staff holding the line; attest-free; no team role; no override of the staff cell).

## Next parts
`authorise`, `condition_facts`, the `visible_*` builders and `holds_engagement_role` (SQL-shape tests as above), then kernel and evidence. The new score comes from the next weekly run (or a local `mutmut run` narrowed to identity/authz); equivalence notes go in this file for AY.

## Progress log
- 2026-10-29: part 1 built; 35 passed. A local identity/authz run on main first needed two main fixes (#698 for `test_app_gates`; the audit target placements for N-01/N-02 kinds are open, see the session report).
