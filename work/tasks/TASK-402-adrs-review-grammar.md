---
id: TASK-402
title: "P-04-T01 · ADR P-07 Review grammar (ADR-160) and ADR P-35 Suggestions, proposals, approval grants and Undo (ADR-161)"
spec: SPEC-046
acceptance_criteria: [AC-5, AC-6, AC-17]
risk_zone: red
status: done
epic: P-04
plan_key: P-04-T01
branch: p04-t01-adrs
created: 2026-10-22
updated: 2026-10-22
---

## Objective
"Both ADRs are accepted with notanaskhan and ayushkbhatia in deciders before the first P-04 migration merges, and they record field ticks as sign-offs on field targets, Undo as a compensating event and the dormant policy actor." Written from chapter 03 sections 3.7 and 4.7, DEC-24, DEC-28 and DEC-36.

## Plan (red zone; documents only)
- Numbers: the plan's aliases are ADR-133 (P-07) and ADR-126 (P-35). ADR-133 is product naming on `main`, and the 116-130 pre-allocation was superseded (SPEC-046 AC-4), so take the next free numbers: ADR-160 (P-07), ADR-161 (P-35). Record the mapping in `docs/adr/backlog.md` (AC-5).
- Files: `docs/adr/ADR-160-review-grammar.md`, `docs/adr/ADR-161-suggestions-proposals-approval-grants-undo.md`; index rows in `docs/adr/README.md` (AC-6); `docs/adr/backlog.md` rows P-07 and P-35; decision-log artefacts for DEC-24, DEC-28, DEC-36 (AC-17).
- No migration, registry, flag, test or product code. Rollback: revert the commit.
- Check: `cd backend && uv run python -m abacus_tools.quality.validate_docs`.

## What changed
- **ADR-160 (P-07, accepted):** the red `review` module and its registration slots; insert-only, human-only `sign_offs` (`ladder`, `field_tick`, `final_approval`; L1-L5) with a JCS content hash and computed staleness (no stale column); R-SO-1 to R-SO-8; **field ticks are sign-offs on `field` targets and flags are review notes**; review notes; one issues service; decision cards (X-13, code-computed options, rationale required, MFA per kind, reassess vs supersede); checkpoints ("Current" derived, restore as new); `field_value_versions` with `fvv_policy_dormant`; the `human_gates` projection; the five-layer human-only pattern; cell addresses and the closed formula grammar. Consistent with ADR-134 (fieldwork rides this grammar).
- **ADR-161 (P-35, accepted):** generic `suggestions` and `proposals` + `proposal_rows` with insert-only human-only decision tables; typed tables stay and project; single-use `approval_grants` with `consume_grant` as the single gate for both dispatchers; **Undo as a compensating `*.undone` event** within 10 s with the effect held by a grant (`409 undo_window_closed`, `effect_started`), superseding chapter 04's deferred commit; **the dormant `policy` actor**, locked off until an accepted P-08.
- `docs/adr/README.md`: two index rows. `docs/adr/backlog.md`: P-07 = ADR-160, P-35 = ADR-161, both accepted, epic P-04. `docs/product/decision-log.md`: DEC-24, DEC-28 -> ADR-161; DEC-36 -> ADR-160.

## Progress log
- 2026-10-22: Read AGENTS.md, AMENDMENT-solo, P-04 epic (sections 0.1, 3, 4, 11), chapter 03 sections 3.7 and 4.7, chapter 09 (X-2, X-13, DEC-24/28/36/53, P-07, P-35), ADR-134. Drafted and accepted ADR-160 and ADR-161 with deciders notanaskhan and ayushkbhatia (solo-edition reading). Index, backlog and decision log updated. validate_docs passes.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| ADR-160 for P-07 and ADR-161 for P-35, not the plan's ADR-133 and ADR-126 | ADR-133 is taken by product naming; backlog.md treats plan numbers as aliases and the 116-130 block as superseded (SPEC-046 AC-4); every other pre-allocated P-ADR was minted fresh | No (recorded in backlog.md) |
| Backlog epic for P-07 changed from Q-02 to P-04 | P-04-T01 drafts it | No |
