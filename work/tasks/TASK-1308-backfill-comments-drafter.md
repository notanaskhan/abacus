---
id: TASK-1308
title: Back-fill TASK-062 (comments backend) and TASK-072 (guidance drafter checks) from SPEC-032 and SPEC-035 (Q-03-T039)
spec: SPEC-032
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T039
branch: s10-q03-backfill
test_author: ayushkbhatia
test_session: 2026-10-26 s10-q03-backfill
created: 2026-10-26
updated: 2026-10-26
---

## Objective
ADR-078 suites for TASK-062 (SPEC-032 AC-1 to AC-9, the backend) and TASK-072 (SPEC-035 AC-2,
AC-3 and the drafter's declaration), written from the specs, the matrix rows, the error codes and
the tasks' recorded decisions only (`.claude/skills/ac-test-author`). Row acceptance: "A shared
comment passes the scope check and a redaction is a new row, never an edit."

## Plan
- `tests/integration/backfill/test_q03t039_comments_and_drafter.py`, over HTTP:
  - AC-1 threads per item and version; AC-2 default visibility; AC-3 clients see shared only and
    only items they may see; AC-4 grants refuse UPDATE and DELETE, corrections link, another
    author is `correction_not_allowed`; AC-5 mentions of readers only, one `comment.mentioned`
    event naming each once; AC-6 only a firm admin redacts, the stub replaces the text for every
    reader, the comment row is unchanged and the redaction is one new row, `already_redacted`
    on a second; AC-7 a clean shared comment passes the scope check, one naming another client is
    `out_of_scope` with nothing stored and can be kept internal; AC-8 counts and unread per
    reader; AC-9 the body is sealed and the audit carries no text.
  - TASK-072: the declared spec (single call, small tier, propose, task scope, eval suite); AC-3
    a draft failing the checks is recorded but never listed, and an edited approval faces the
    same checks (URL, email, phone, amount, model talk: `edited_draft_refused`); AC-2 a real firm
    gets `ai_drafting_unavailable`, no run and no draft.
- AC-10 (screens) stays with TASK-063's vitest; SPEC-035 AC-1 and AC-7 need a model and stay with
  the evaluation suite.

## Progress log
- 2026-10-26: suite written (no product change); run in the end-of-batch targeted pass.
- 2026-10-26: targeted run green (26 passed across both suites, first run); no defect, no spec drift found; no xfail.
