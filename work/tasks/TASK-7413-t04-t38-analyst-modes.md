---
id: TASK-7413
title: "T-04-T38: tax.return_analyst v1 modes k1_treatments and residency: code facts in, rationale and verified citations out; SALY comparison; residency options with a recommendation, conflict flag and an internal client-question draft; propose-only"
spec: SPEC-649
acceptance_criteria: [AC-7, AC-8]  # AC-7.1, AC-7.3, AC-8.2, AC-8.4
risk_zone: red
status: in-review
branch: s38-t04-t38
worktree: /Users/ayushkbhatia/Accrued/abacus-s38
created: 2026-11-12
updated: 2026-11-12
plan_key: T-04-T38
---

## Objective
On the fake model the Ridgeline proposal carries 7 treatments with code-computed figures only, the
150-day variant returns Action required with option 2 recommended, and neither mode can confirm,
approve or send.

## Plan (red)
- `tax/analyst_modes.py` (red): `k1_treatments_mode` (C17 `tax.read_prior_year` first, so
  §7216 gates; the model's rationale settled to code's numbers; one
  `tax.propose_pass_through_treatments` proposal with code's resolved values for the still-proposed
  treatments), `residency_mode` (C17 gate, the determination's facts, code's
  `tax.compute_residency_facts` recommendation and conflict, the model's rationale, one
  `tax.propose_residency` proposal, `action_required` with the internal client-question draft on a
  conflict), `AnalystModeWorkflow` (one activity), `start_mode`, `return_facts`.
- Prompts `tax.return_analyst.k1_treatments@v1`, `tax.return_analyst.residency@v1`.
- Spec `tax.return_analyst`: reads, two computes, two propose tools; task scope `k1_treatment.read`,
  `residency.read`, `proposal.create`; plan `required_when_writes` (codegen's rule for propose).
- `tax.read_prior_year` rows gain `resolved_text` and `prior_text` (additive).
- Routes `POST …/k1-activities/{id}/treatment-runs` and `POST …/residency/proposal-runs` live (202).
- Tests `tests/unit/tax/test_t04t38_analyst_modes.py` (6 pass): seven treatments, code's values
  only, an invented number dropped; consent waits; 150 days → Action required, option 2, the
  question; 281 days → proposed, no question; the spec cannot confirm, approve or send.
- Rollback: revert; no migration.

## Partial
- Triggers (a K-1 activity created or released, organizer answers) need a run started without a
  person's request (a system-initiated capability run, ADR P-49's standing policy); today a person
  starts each mode from TXI-02 or TXI-03.
- The model's per-treatment rationale is returned by the run, not yet stored beside the treatment
  (no rationale column; the proposal carries the values and SHL-10 shows the ApprovalCard).
- Real-model runs: T-04-T43 (evaluation account).

## Progress log
- `2026-11-12` — Built (S38). 6 unit tests pass; lint and types clean.
