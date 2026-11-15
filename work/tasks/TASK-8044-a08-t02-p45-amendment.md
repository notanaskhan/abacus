---
id: TASK-8044
title: "A-08-T02: ADR P-45 amendment (public respondent access) and link-principal threat model"
spec: SPEC-657
acceptance_criteria: [AC-7]
risk_zone: red
status: in-review
branch: a08-t02-p45-amendment
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T02
---

## Objective
Put the `/v1/confirm/{token}` family on the ROUTE-001 exception list with its controls, and add
the link-principal threats to the threat model, as proposed amendments both deciders accept.

## Plan (red: written before the build)
1. ADR-152 amendment section (proposed): the five paths, `LINK_PRINCIPAL` marker, padded uniform
   answers, OTP lockout, WAF rule 6, the `confirmation_links` control, single-object scope.
2. ADR-064 amendment section (proposed): enumeration, phishing, brute force, hostile upload,
   scope escape and replay with their controls.
3. DEC-5029. No code: the exception list itself changes in A-08-T06 with the stub routes.
Rollback: revert the two sections.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Drafted (DEC-5029). **Waits on acceptance by Ayush (both founders in the plan).**
