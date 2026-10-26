---
id: TASK-1309
title: Back-fill TASK-073 and TASK-074 (drafted guidance in the product; template drafting) from SPEC-035 (Q-03-T040)
spec: SPEC-035
acceptance_criteria: [AC-4, AC-5, AC-6]
risk_zone: red
status: in-review
epic: Q-03
plan_key: Q-03-T040
branch: s10-q03-backfill
test_author: ayushkbhatia
test_session: 2026-10-26 s10-q03-backfill
created: 2026-10-26
updated: 2026-10-26
---

## Objective
ADR-078 suite for TASK-073 and TASK-074 from SPEC-035 (Q2, Q3, Q5 and AC-4 to AC-6). Row
acceptance: "A non-synthetic firm can never display model-drafted guidance to a client principal
in any test" (ADR-111 until ADR P-25's conditions hold).

## Plan
- `tests/integration/backfill/test_q03t040_drafted_guidance.py`, over HTTP; drafts seeded as the
  drafter records them (its run and passed checks):
  - AC-4 approve writes `drafted` text and who approved; an edited approval keeps the person's
    words; discard records a decision and changes nothing; `draft_already_decided` twice;
    Q5 bulk without `confirmed_read` is `read_not_confirmed`; staff and clients never decide or
    read drafts.
  - AC-5 / Q2 on a synthetic firm: clients see approved drafted guidance only while the firm
    admin's setting is on; the firm always sees it.
  - ADR-111 on a real firm: the setting is refused (`drafted_guidance_not_allowed`), and even
    with drafted text and the column forced on underneath, no client read carries it.
  - AC-6 a later firm edit becomes `firm` guidance.
  - Q3 template drafting is the firm admin's and refused for a real firm
    (`ai_drafting_unavailable`).

## Progress log
- 2026-10-26: suite written (no product change); run in the end-of-batch targeted pass.
- 2026-10-26: targeted run green (26 passed across both suites, first run); no defect, no spec drift found; no xfail.
- 2026-10-26: security review M fixed: the ADR-111 test also reads the portal binder list, binder and request (all 200) and finds no drafted text.
