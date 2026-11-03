---
id: TASK-3248
title: AUD-04's agent-drafted cells draw through AgentText (C-02 workpaper and C-01 grid)
spec: SPEC-000  # row
acceptance_criteria: [AC-1]
risk_zone: green
status: in-review
epic: A-04
plan_key: A-04-T27
branch: open-aud04-agent-text
worktree: /Users/ayushkbhatia/Accrued/abacus-s26
created: 2026-11-04
updated: 2026-11-04
---

# TASK-3248 · AUD-04 agent text through AgentText

AC-1: in AUD-04 (a), every cell with `value_source: agent` (key/value rows, grid labels and
grid cells) renders inside `[data-actor="agent"]`; once adopted (b) none does.

Left open by A-04-T27 (S26): WorkpaperPane drew every value as plain text, so agent drafts
skipped `AgentText`'s sanitising (frontend rule 2). The kit gains `agent` on `WorkpaperKv` and
`TableCell` and `labelAgent` on `TableRow`; DataGrid's text cells and the workpaper's key/value
rows draw those through `AgentText` at the grid's own type size.

## Progress log
- 2026-11-04: built; AUD-04 test for (a) and (b).
