---
id: TASK-7632
title: "Q-03-T268: supply-chain hygiene 2028 Q2: local scans, B613 fix, CodeQL triage"
plan_key: Q-03-T268
spec: SPEC-000  # row (Q-03-T268; ADR-099; DEC-366)
acceptance_criteria: [Q-03-T268]  # no high or critical finding older than its SLA at quarter end
risk_zone: red
status: in-review
branch: q03-t268-supply-chain
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
"No high or critical dependency or image finding is older than its SLA at the quarter's end."

## Plan (red)
- Run pip-audit, bandit and pnpm audit locally; read code-scanning alerts through the API.
- Fix B613 in `platform/search/scrub.py` (literal bidi characters) as escapes; escape the two S40
  tests that carried them. Record the quarter, the register entry and DEC-4627.
- No migration, flag or route. Rollback: revert (the old pattern matched the same set).

## Security review (inline, red diff)
- `_HOSTILE` matches exactly the old set: C0/C1, U+200B–U+200F, U+202A–U+202E, U+2060–U+2069,
  U+FEFF (asserted on the boundary code points); only the source spelling changed.

## Partial / open (the user's calls)
- js-yaml override (protected-manifest PR, due Dec 3); zlib1g base-digest bump (due Dec 7);
  dismiss CodeQL #10, #22, #28 (false positives); uv.lock refresh; Trivy and Inspector need images.

## Progress log
- `2026-11-12` — Scans run, B613 fixed, quarter recorded (DEC-4627).
