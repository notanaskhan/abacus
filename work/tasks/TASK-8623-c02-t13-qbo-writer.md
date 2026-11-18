---
id: TASK-8623
title: "C-02-T13: QBO W1 writer behind the Writer port, with the scripted fake"
spec: SPEC-700
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
branch: c02-t13-qbo-writer
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-18
updated: 2026-11-18
plan_key: C-02-T13
---

## Objective
Spec section: docs/plan/epics/C-02.md §4.1, §7.1 (QBO W1). Preflight (balanced, after BookCloseDate, mapped and active accounts, DocNumber), JournalEntry create with requestid idempotency, read-back verification, BookCloseDate set [verify], error mapping, fake writer with scripted outcomes; reachable only through execute_write.

## Plan (red)
1. integrations/writers/quickbooks_online.py: QuickBooksOnlineWriter over a QboTransport port (no HTTP client here); preflight; post (preflight, one create keyed by request id, read-back line for line, verify_mismatch otherwise); set_book_close_date; errors mapped to inactive_account, closing_date_locked, rate_limited, needs_reauth.
2. FakeQboTransport: accounts, book close date, scripted create outcomes, requestid replay, and a record of every non-GET call.
3. banned_patterns CONN-001 excludes this one file (ADR-344 sanctions the W1 writer); POST-001 still confines callers to adjustments/posting.py; TJE-001 still covers it.
4. tests/unit/integrations/test_c02t13_qbo_writer.py: posts once under a repeated request with a matching read-back; inactive account fails preflight with no write; closed period, unbalanced and unmapped refused; provider errors mapped; book close date the only other write.

## Progress log
- `2026-11-18` — Built in the S50 sequential stack (DEC-5623). Partial: the live HTTPS transport (Intuit token, egress allowlist) and the execute_write path are C-02-T18/T19; execute_write still refuses every write in S50, so nothing reaches a client. BookCloseDate on Preferences is marked [verify] against the live API. Gates and tests run once at the S50 end pass (build first, test last).
