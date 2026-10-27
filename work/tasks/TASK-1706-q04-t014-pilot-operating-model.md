---
id: TASK-1706
title: Q-04-T014 pilot operating model and the support desk
spec: SPEC-402
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: Q-04
plan_key: Q-04-T014
branch: s14-q04-t014
created: 2026-10-28
updated: 2026-10-28
---

## Objective
`docs/ops/pilot/README.md`: AY partner-facing owner; N SEV1/2 on-call with a named backup per
window; SLA (2 business hours in season, SEV1 24x7); shared inbox labels (screen ID, pilot code,
severity; no client data); Tue/Thu office hours; pilot codes (names only in the vault); W1–W10
thresholds linked.

## Plan
- Sources: Q-04 §0 (founders, pilot codes), §3.7 AC-7.1 to AC-7.5, ADR-097 severities, RB-27,
  DEC-72 support sessions, `docs/product/discovery/thresholds.md`.
- No Q-04 spec on main yet: SPEC-402 carries this task's AC (Q-04's own spec supersedes it).
- Decided with the plan's defaults: business hours Mon–Fri 8–6 CT; office hours Tue/Thu 11–12 CT;
  SEV2 acknowledgement inside window working hours; out-of-season response 1 business day.

## Per AC
| AC | Evidence |
|---|---|
| AC-1 | `docs/ops/pilot/README.md`; the human checks (agreement wording, a labelled test request) are its "Check before PW1" list |

## Questions for the human
- [ ] Compare the SLA table with the signed founding-partner agreement (not in the repo) and send one test request.

## Progress log
- `2026-10-28` — README, SPEC-402 written; `validate_docs` clean.

## Handoff
- **Current state:** written, PR open, held for the S14 batch.
- **Exact next step:** the two human checks before PW1 (Tue Jun 1, 2027).
