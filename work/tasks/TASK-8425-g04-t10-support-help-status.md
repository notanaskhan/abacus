---
id: TASK-8425
title: "G-04-T10: Support, help, status and publications backend"
spec: SPEC-680
acceptance_criteria: [AC-44, AC-45, AC-46, AC-47, AC-50, AC-53, AC-54, AC-55]
risk_zone: amber
status: in-review
branch: g04-t10-support-help-status
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T10
---

## Objective
Spec section: docs/plan/epics/G-04.md §3, §4. Support, help, status and publications backend: per-user chat thread with computed availability; staff queue and replies; help articles read and search with screen context; firm status from incidents and W-01 integration health; incident posts; two-person publish of help articles.

## Plan (amber)
1. `platform/support.py`: the caller's one open thread (OWN) with availability from the `support_hours` setting (online inside a weekly window; the 7-day median first response from 5 samples; else the next opening); send (1-4,000 characters, 30 per 10 minutes, the thread opens on the first message; audit carries ids and a length, never the body); help list/search grouped with the screen's articles first as Suggested and schema-v1 blocks only; firm status as the worse of the open incident and the firm's own integration health; the staff conversation list, detail and reply in the firm's context as the staff member (`platform_support.reply`).
2. Slot `platform.api.register_firm_health`, filled by `integrations/firm_health.py` (W-01 install status).
3. Migration 0947: EXECUTE on the G-04 owner writers to `abacus_ops`; `abacus_tools.platform_console` posts, updates and resolves incidents and drafts, publishes (approver is never the drafter, enforced by the function) and withdraws help articles.
4. Routes: SHL-05's five firm routes and the console's three support-queue routes live; the console's incident and publication routes stay 501 (ops-only writes, ADR-156).
5. Tests: `tests/unit/platform/test_g04t10_support.py`.

## Progress log
- `2026-11-17` — Built in the S48 sequential stack (DEC-5417). Lint, pyright, banned patterns clean; app and worker import. Partial: the content-free 'Accrued Support replied' email after 5 unread minutes is not built (needs a delayed check and a C16 kind); session cards and the empty-thread suggestions are empty; reference-set publication stays K-02's operator command; the console's incident and publication routes answer 501 because their writers are ops-only (the operator command runs them). Gates and tests run once at the S48 end pass (build first, test last).
