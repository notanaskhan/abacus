---
id: TASK-9028
title: "K-03-T22: SHT-01 row drawer (?ov=row:<key>)"
spec: SPEC-721
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: green
status: in-review
branch: s54-k03-t22-row-drawer
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-27
updated: 2026-11-27
plan_key: K-03-T22
---

## Objective
SHT-01 e: the O2 480 row drawer with Details and its Why card (two citation chips opening SHL-07), Comments (C-29), Agents, Evidence, Requests and To-dos (C-30); Adopt (L1) opens SHL-12 at L1 and Raise exception opens AUD-15.

## Done
- GET /v1/sheets/{sid}/rows/{rid} returns the row, its facts, the agent's reason and its links (Postgres test)
- SHT-01e renders SURL-05 word for word with two citation chips that open SHL-07
- Adopt (L1) opens ?ov=signoff:sheet_row:<id>:L1
- The drawer survives reload and closes on Back
- Fixture from the Python scenario (scenario.sht01-drawer.json)

## Progress log
- `2026-11-27` — 2026-11-27: built per DEC-6033. Backend read on Postgres (test_k03t22_row_drawer_reads_facts_reason_and_links), the agent's reason through agents.api.suggestion_view (ED-171 hides shadow or missing runs, which the test hit first). Drawer at screens/SHT-01/RowDrawer.tsx, registered as the `row` overlay. The kit's key cell opens it. 7 drawer tests plus SHT-01's 5 green, packages/ui 1582 green, sh1 contract tests 30 green. Mistake: overwrote the test-run lock without checking it first; next time check before writing.
