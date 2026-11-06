---
id: TASK-5131
title: I-01-T23 Gate sources and presenters landing S13 to S29, activity allowlist, retire Review.tsx and the home flags
spec: SPEC-000  # row (I-01-T23)
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: I-01
plan_key: I-01-T23
branch: s29-i01-t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s29
created: 2026-11-06
updated: 2026-11-06
---

## Objective
Every gate subkind reads in words on HOME-01 and HOME-02, opens its host, and no I-01 flag stays live.

## Plan
signatures/gate_sources.py (`envelope_send`, `envelope_countersign`), notices/gate_sources.py (`notice_response_send`), presenters with titles and routes, GATE_SUBKIND_TITLE, hosts SIG-01 and NOT-02. Migration 0687 widens home_activity_items.event_type; SOURCES take envelope.send_approved, envelope.completed, inbound_message.recorded. EnvelopeDrafted event. Remove home.dashboard and home.approvals; delete legacy/Review.tsx, /review redirects to HOME-02. SPEC-004's UI assertions move to HOME-02: queue listing AC-1 to AC-3 to HOME-02.test.tsx, take and release AC-4 and AC-5 to AUD-03 and BND-02, decide AC-6 to AC-8 to HOME-02.detail.test.tsx; legacy/DecisionActions.tsx stays with its test until R-01 retires it. Rollback: re-add the flag rows; the routes still resolve.

## Progress log
- 2026-11-06: built. tests/unit/test_home_gate_subkinds.py passes (2). Tests pinned to flag-off behaviour move at the end pass: HOME-01 rows, c13_home stub, TAX and HOME-02 send footer.

## Decisions made during this task
DEC-2427
