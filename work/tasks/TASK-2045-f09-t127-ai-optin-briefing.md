---
id: TASK-2045
title: F-09-T127 PW1 firm AI opt-in briefing
spec: SPEC-049
acceptance_criteria: [AC-37]
risk_zone: red
status: blocked
epic: F-09
plan_key: F-09-T127
branch: s15c-f09-t127
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Walk each PW1 firm admin through the TASK-076 disclosure (providers, region, no training,
sub-processors) before any shadow run; each admin has seen it before Tue Jun 1, and the opt-in
itself is recorded in the product by the firm.

## Built
`docs/ops/pilot/ai-optin-briefing.md`: the walk through the product's own disclosure panel (each
part and what the admin must understand; the text itself is the register's, never restated), the
firm's own opt-in in the product and how `make go-live-check` reads it, and the record by pilot
code. SPEC-049 AC-37. Docs only.

## Blocked on
A signed PW1 firm, and a current Bedrock entry in the provider terms register (M7) so the
disclosure has something to show.

## Progress log
- 2026-10-30: the briefing walk and record written.
