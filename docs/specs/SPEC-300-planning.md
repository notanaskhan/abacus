---
id: SPEC-300
title: "Planning: materiality computed from a benchmark and decided by the engagement partner; the risk register with RMM by code and the partner's approval of significant risks and rebuttals"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-004, ADR-005, ADR-050]
related_specs: [SPEC-037, SPEC-043]
created: 2026-10-20
updated: 2026-10-20
---

## 1. Summary
The plan's AUD-07 (materiality decision) and AUD-08 (risk register), first slice (S08 slices 4 and 6, without the agent).
- **Materiality as a decision.** A manager or the partner proposes a version from a benchmark and its amount. Code computes overall, performance and clearly trivial from the percentages (ADR-050). Only the engagement partner decides the newest version, with a rationale. Sampling waits for the decision (gate G4).
- **The risk register.** The team records risks, R1, R2… on each engagement. Each risk has a level, an area, assertions, inherent and control risk, a significant flag and a fraud flag. Every revision is a new version (ADR-004). Code combines inherent and control risk into the risk of material misstatement (RMM). The partner approves a significant risk, or the rebuttal of a presumed fraud risk.

People decide; the agent does nothing here (ADR-005).

## 2. Acceptance criteria
- **AC-1** A proposal can carry a basis:
  - inputs: benchmark amount, rate %, performance %, clearly trivial %;
  - code computes overall = rate × basis, performance = % of overall, clearly trivial = % of overall;
  - amounts round to the nearest hundred from $1,000 up, otherwise to the dollar, and are never below $1;
  - clearly trivial % ≤ performance %;
  - insert-only, as a new version of `engagement_materiality`.
- **AC-2** Deciding:
  - `materiality.decide` is for the engagement partner only; the agent is denied;
  - the partner decides the newest version, with a rationale (1–2,000 characters);
  - a version is decided once;
  - starting selection with no decided version is refused with `materiality_undecided`.
- **AC-3** Versions are listed newest first, each with a status (proposed, decided or superseded), its basis, who proposed it, and the decision.
- **AC-4** Recording a risk (`risk.assess`: senior, manager, partner):
  - fields: title, area, level, assertions, inherent (low, moderate, high), control (low, moderate, high, maximum), significant, and fraud (none, presumed, rebuttal);
  - a significant risk or a rebuttal needs a rationale;
  - RMM is computed by code: the inherent and control scores add up (low 1, moderate 2, high or maximum 3), and the total gives RMM: 5 or more is high, 4 is moderate, less is low;
  - revising adds a version.
- **AC-5** Approving (`risk.approve`: the partner only; the agent is denied):
  - the partner approves the current version's significant risk or rebuttal, once;
  - a new version needs approval again.
- **AC-6** A Planning tab shows:
  - a materiality card with Propose and Decide, and the earlier versions;
  - the risk register: RMM, flags, and the partner's Approve.

  Fieldwork reads materiality and links to Planning.

## 3. Data
- `engagement_materiality` gains `basis_amount`, `rate_pct`, `performance_pct`, `trivial_pct` and `rationale` (all nullable).
- `materiality_decisions` (insert-only): `materiality_id` (unique), `rationale`, `decided_by`.
- `risks` (insert-only): `engagement_id`, `number` (unique per engagement), `raised_by`.
- `risk_versions` (insert-only): the fields in AC-4, `recorded_by`.
- `risk_approvals` (insert-only): `risk_version_id` (unique), `rationale`, `approved_by`.

## 4. Out of scope
The agent's proposer and drafter, SAS 145 factors, responses and linkage, the fraud brainstorm, reassessment at final with impact lists, prior-year comparisons, the HOME queue entry, and notifications.
