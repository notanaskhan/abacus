---
id: TASK-1809
title: Q-02 runbooks and docs (Q-02-T51)
spec: SPEC-341
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: Q-02
plan_key: Q-02-T51
branch: s13r-q02-t51
created: 2026-10-28
updated: 2026-10-28
---

## Objective
Q-02's runbooks, the compliance-kernel skill, the kernel SPEC closed and SPEC-036's open half handed on.

## Plan
- RB-27 (Accrued incident propagation, 72 hours), RB-14 (legal-hold apply and release failures, was a stub), RB-39 (agent stage promotion and demotion), RB-40 (provider-terms renewal and Bedrock parity refresh); RB-29 already covers the audit-chain mismatch (SEV1). Runbook index updated.
- `.claude/skills/compliance-kernel/SKILL.md`.
- SPEC-341 `done`; SPEC-036 §10: done for AC-1 to 5, 7, 8; AC-6's screen half and AC-9 handed to Q-04-T351.
- Flags: no flag expires inside Sep 1 to Oct 20 (checked over every registry file).
- **Human:** "each runbook is rehearsed once on staging" (staging does not exist yet); alarm links wait for Q-01's alarm resources.

## Progress log
- 2026-10-28: written (S13 leftovers).
