---
id: TASK-1225
title: Screen contracts ADM-01, ADM-02 and ADM-03 with the DF-07 ADM-02g design and the status rows (G-01-T01)
spec: SPEC-024
acceptance_criteria: [AC-8]
risk_zone: amber
status: done
epic: G-01
plan_key: G-01-T01
branch: s8b-admin-kit
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"Every artboard and the new state g are listed with production or fixture status, and the C2 rows
merge with N's approval."

## Plan (amber)
- **Files:** `docs/screens/ADM-01.md` (built by G-01-T07: a–f fixture, Prod), `docs/screens/ADM-02.md`
  (a–f and the DF-07 state g, built by G-01-T10), `docs/screens/ADM-03.md` (a–h to build in
  G-01-T14; h Prod only on the service-line decision), each from `docs/screens/_TEMPLATE.md` in the
  format of ENG-01 and ADM-10: states with persona, clock, snapshot, data condition and status;
  API with matrix actions; status words; copy keys; links (planned or live); acceptance from the
  handoff checklists and revision R2; figures with their seed tests; AVOID; deviations; parity
  tiers; open gaps.
- **Deviations recorded:** DEC-43/DF-14 (walls helper), DEC-35/DF-24 (14-day expiry), DEC-73 (wall
  toast and "Awaiting …"), the walls step-up row (R-5), ADM-03e partner actions (AC11.2), and the
  offshore copy after TASK-1207: ADM-03d's banner, the offshore group helper and ADM-02c's invite
  helper said offshore members see 0 clients; since DEC-319 was narrowed they see what their roles
  reach and only assignment and reveals are gated. The contracts carry the product's words and
  the parity masks.
- **Decisions:** DEC-352 (decision log).
- **Status vocabulary:** the C2 rows the epic names (`membership`, `invitation`, `wall_approval`,
  `annual_independence`) are already in `docs/product/status-vocabulary.yaml`; nothing to add.
- **No code, migrations, registry or flag edits.** Rollback: revert the commit.
- **Tests:** none (docs); `validate_docs` for this task file.

## Progress log
- 2026-10-25: written on `s8b-admin-kit` from origin/main 9d7826d7. The handoff folders for ADM-01,
  ADM-02 and ADM-03 (README, spec, revision R2 for ADM-03, screenshots) and G-01 §2–5 were the
  sources; TASK-1207 for the offshore narrowing. DEC-352 recorded.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-352 | The offshore copy, ADM-03e partner actions, the DF-07 g design and the other copy deviations | No |
