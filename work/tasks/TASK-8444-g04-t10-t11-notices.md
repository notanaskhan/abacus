---
id: TASK-8444
title: "G-04-T10: rest: support reply notice, plan request kinds and the C13 gate"
spec: SPEC-680
acceptance_criteria: [AC-47, AC-40]
risk_zone: amber
status: in-review
branch: s48r-g04-notices
worktree: /Users/ayushkbhatia/Accrued/abacus-s48
created: 2026-11-17
updated: 2026-11-17
plan_key: G-04-T10
---

## Objective
G-04 §4.8 lists plan_request.awaiting_partner, .decided and .applied and support.replied; none was catalogued, the reply email after 5 unread minutes was not built and the awaiting request raised no C13 gate (platform cannot import review).

## Plan (amber)
1. support: opening the thread moves the person's read mark (support_conversation_reads); a staff reply emits support.reply_held held 5 minutes (outbox not_before); its consumer emits support.replied only when the reply is still unread.
2. plan_usage/console: PlanRequestAwaitingPartner (approver), PlanRequestDecided (requester), PlanRequestApplied (requester and billing contact); awaiting_plan_requests read.
3. notifications.catalogue: four kinds (in-app and email; support content-free "Accrued Support replied").
4. review.firm_gates: plan_change_request decision gate, firm-scoped, assigned to the approver; C13_EVENTS rows.
5. Unit tests.

## Progress log
- `2026-11-17` — Built (S48 rest, DEC-5431). The support notice is one C16 event after 5 minutes unread (in-app and email together): C16 has no per-channel delay, so the in-app row does not come earlier. Email bodies are DB templates to import per environment. Gates and tests run once at the S48 end pass (build first, test last).
