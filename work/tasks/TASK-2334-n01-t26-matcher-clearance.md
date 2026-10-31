---
id: TASK-2334
title: N-01-T26 matcher v3 Bedrock rerun, baseline, clearance and shadow stage (code half)
spec: SPEC-380
acceptance_criteria: [AC-11]  # SPEC-380 AC-11 (matcher outputs) and the task row, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T26
branch: s18-n01-t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s18
created: 2026-10-31
updated: 2026-10-31
---

## Objective
"Matcher v3 Bedrock rerun at the protected thresholds, evals/baselines.yaml entry (+10 % gate),
agent clearance record and provider-terms check; shadow stage on for PW1 firms that opted in
(TASK-076), scored against triage_decisions." Acceptance: "A committed Bedrock report passes and
live stage waits on the shadow override rate staying within 8 %."

## Plan
Red zone. Code half here; the operator and founder steps are in
`docs/plan/status/n01-t26-matcher-v3-clearance.md` (no real data, no spend without asking).
- `agents/intake_candidates.py`: only a live run's proposals reach INB-02 (and `ambiguous_candidates`):
  a shadow run's were offered before this change (SPEC-036 D2 gap).
- `communications/triage_outcomes.py` + `communications.api`: each attachment's latest triage
  decision by an instant (identifiers and codes).
- `agents/shadow_score.py`: `evidence.matcher` scored (newest shadow run per attachment vs the
  person's decision); `live_override` likewise over live runs. The live guard (`check_live`) reads it,
  so live waits on override ≤ 8 %.
- `evals/baselines.yaml` (new, protected): matcher small tier $0.015; `evals/matching.py`
  `intake_cost_gate` fails real intake runs past +10 % (or with no baseline).
- `abacus_tools/evals`: `--route bedrock` accepted; the Anthropic key is required for `direct` only.
- Tests: `tests/unit/agents/test_n01t26_matcher_shadow.py`,
  `tests/integration/backfill/test_n01t26_matcher_shadow.py`. DEC-1380.
- Rollback: revert the PR; no migration.

## Progress log
- `2026-10-31` — code half built; unit 8/8 pass, ruff and pyright clean; integration at the end
  review. Open (human/external): provider-terms entry (empty register), Bedrock route parity and
  the paid Bedrock rerun, the clearance flip, shadow stages per opted-in PW1 firm. `[skip ci]`.

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** end review; then the status note's steps 1–6 with the founder.
