---
id: TASK-307
title: "Walkthrough of TASK-300 to TASK-306: the fieldwork list shows the materiality decision; partners aren't notified of their own proposals"
spec: SPEC-305
acceptance_criteria: [AC-1]
risk_zone: green
status: done
branch: task-307-walk-fixes
worktree: spec005
created: 2026-10-20
updated: 2026-10-20
---

## Walkthrough (live, dev stack, Dana Leader on Smoke GL 970232)
1. Palette: ⌘K search for "smoke" — OK.
2. Clients index and record — OK.
3. Propose materiality from a benchmark — OK.
4. Partner decides — OK.
5. Add a significant risk and approve it — OK.
6. Fieldwork shows the decision — OK. Found: the procedures list said "Set".
7. Raise a finding; propose, conclude and communicate its severity — OK.
8. Propose an entry; approve it; client declines (passed) — OK.
9. Representation gaps; add one linked to the passed entry — OK.
10. Notifications drawer: Needs you shows the three partner kinds — OK. Found: the partner was told of their own proposals.
11. Audit log: filter, clear, 100 rows — OK.
12. Source viewer: no cited screening on this engagement, so not exercised live (covered by its tests).

No 4xx or 5xx responses and no page errors.

## Fixes
- The fieldwork list reads the materiality versions: To propose, Waiting on the partner, or Decided.
- Partner-decision events carry `by_user`, and the recipients leave that person out.
