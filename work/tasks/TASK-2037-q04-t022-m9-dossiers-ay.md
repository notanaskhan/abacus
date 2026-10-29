---
id: TASK-2037
title: Q-04-T022 M9 dossiers part AY; firm-admin briefing on shadow
spec: SPEC-402
acceptance_criteria: [AC-7]
risk_zone: amber
status: blocked
epic: Q-04
plan_key: Q-04-T022
branch: s15c-q04-t022
created: 2026-10-30
updated: 2026-10-30
---

## Objective
Communications, content and integrations sections of each PW1 dossier; the firm-admin briefing on
shadow (no client email, nothing client-facing, agents in shadow); each dossier's AY sections green
and every firm admin's written acknowledgement of the shadow rules.

## Plan (amber: written before the code)
- `docs/ops/pilot/shadow-briefing.md` (versioned, shadow-briefing v1): what shadow means in PW1
  (staff only; no client email; nothing client-facing; agents in shadow, nothing shown, SPEC-036;
  the firm's tools the system of record; leaving always possible), the sentence the admin
  acknowledges in writing, and §3: the evidence for each AY row of the dossier.
- The dossier's AY sections and its "Shadow rules acknowledged" table come from Q-04-T021's
  `abacus_tools.go_live_dossier` (its `--ready` refuses a dossier without the acknowledgement).
- SPEC-402 AC-7; the pilot README's PW1 checklist gains the acknowledgement.

## Blocked on
No PW1 firm signed yet (F-09): no admin to brief, no dossier to fill. F-09-T127's AI disclosure
briefing comes first.

## Progress log
- 2026-10-30: briefing v1, the AY evidence guide, AC built.
