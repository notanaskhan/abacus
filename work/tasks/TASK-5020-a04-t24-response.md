---
id: TASK-5020
title: A-04-T24 remainder - a drafted response lands on risk_linkages when a person adopts it
spec: SPEC-620
acceptance_criteria: [AC-21]
risk_zone: red
status: in-review
epic: A-04
plan_key: A-04-T24
branch: s25c-a04-t24
worktree: /Users/ayushkbhatia/Accrued/abacus-s25c
created: 2026-11-06
updated: 2026-11-06
---

# TASK-5020 · A-04-T24: the EBP-03 response

TASK-3011 left the response column waiting for A-04-T25's linkage target (DEC-2060). A-04-T25 has
landed. **The check:** nothing further is missing. `risk_linkages` already has `suggestion_id`, and
the app role may write it; no migration is needed.

## Objective
"R8's drafted rationale and EBP-03 response arrive as pending suggestions with three verified
citations."

## Plan (red)
- `draft_mappings.py`: column F on the `risk` sheet, landing on `response`; the fact
  `response_targets`.
- Prompt `workpapers.section_draft.risk@v2`; spec version 12; regenerated specs and eval suites.
- `risks.py`: the applier's response branch writes the live link under `risk.link`;
  `linkage` and `drawer` read pending responses; `_write_link` shared with `link_response`.
- `agents`: `pending_suggestions`, a read for a target's owner, leaving out shadow runs.
- Contract: `LinkCellOut.suggestion_id`, `RiskDrawerOut.response_suggestion`; client regenerated.
- AUD-08's drawer: the Response card with Adopt · Edit · Discard.
- Rollback: revert. No migration; pending suggestions on `response` then have no applier branch, so
  dismiss them first.

## Acceptance
| Check | Test |
|---|---|
| Column F lands on the risk; the fact lists the targets | `tests/unit/agents/test_a04t24_risk_mode.py` |
| Free text never becomes a target | `test_ac4_6_a_response_names_a_registered_section_or_nothing` |
| Pending: drawn suggested, no row written | `trust_kit/test_a04t24_response.py` |
| Adopted: the live link naming the suggestion, under `risk.link` | same |
| A shadow run's value never shows | same |
| The drawer | `AUD-08.test.tsx` f |

## Decisions made during this task
DEC-2385.

## Progress log
- 2026-11-06: built. Security self-review findings fixed: `response_targets` is an identifier fact and supports no number, a response cell holds one of a closed list or is dropped as `not_a_choice`, and reading a pending response needs `proposal.read`. The first gate's two integration failures and the validate_docs failure are fixed too. Not yet run since those fixes: the owner held this session's tests so other sessions get the CPU. Run the targeted tests and check-fast before the PR.
