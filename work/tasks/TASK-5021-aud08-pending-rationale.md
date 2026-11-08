---
id: TASK-5021
title: AUD-08 drawer - the rationale card reads the pending suggestion
spec: SPEC-620
acceptance_criteria: [AC-21]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T26
branch: s25c-a04-rationale
worktree: /Users/ayushkbhatia/Accrued/abacus-s25c
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5021 · AUD-08: a pending rationale shows Adopt, an adopted one does not

Found while reviewing A-04-T24 (TASK-5020). `risks.drawer` took `rationale_suggestion_id` from
`field_timeline`, which holds adopted values. So in production a pending rationale never showed
Adopt, an adopted one did, the card showed the row's text rather than the proposed text, and
`seen_version` was fixed at 1. The fixture hid this by giving variant f both fields.

## Objective
AUD-08 f: "R8's rationale ... arrive as pending suggestions with three citations", with Adopt ·
Edit · Discard only while one waits.

## Plan (amber)
- `assurance/risks.py`: `_pending_responses` becomes `_pending_of(ctx, engagement_id, field_key)`,
  keeping its `proposal.read` check. `Drawer.rationale_suggestion` is the newest pending rationale.
- `assurance/planning_contract.py`: `SuggestedRationaleOut`; `rationale_suggestion` replaces
  `rationale_suggestion_id`. Regenerated client.
- `screens/AUD-08/RiskDrawer.tsx`: adopted text in ink, proposed text in ink-2 through `AgentText`,
  and the suggestion's own version on Adopt and Discard.
- Flags, migrations, the permission matrix: no change. Rollback: revert the commit.
- Stacked on `s25c-a04-t24`, which adds the pending read this reuses.

## Acceptance
- [ ] A pending rationale is drawn with its text, citations and version.
- [ ] An adopted rationale offers no Adopt.
- [ ] The newest pending one is drawn; a shadow run's never is.
- [ ] Without `proposal.read`, none is read.
- [ ] A re-draft keeps the adopted wording in view, and Adopt sends the suggestion's version.

## Decisions made during this task
DEC-2481.

## Progress log
- 2026-11-06: built, with tests written first. Not yet run: the owner held this session's tests so other sessions get the CPU. Run the T24 test command plus `src/screens/AUD-08` before the PR.
- 2026-11-07: Merged main, which took this row's first number while it was held; other sessions then held the next ones, so it moves to a block clear of them. End test pass with T24: targeted backend tests 857 passed, AUD-08 web tests 13 passed, tsc, eslint and check-fast. Fixed on the way: the re-draft test read a request method the fixture does not have, and the rationale check moved out of a className (ADR-065 lint).
