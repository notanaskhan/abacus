---
id: TASK-8941
title: "Q-05-T26: Independent AC tests for post-issuance and inspector access"
spec: SPEC-711
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
branch: s53-q05t26
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: Q-05-T26
---

## Objective
Independent AC tests (ADR-078) for post-issuance and inspector access: the post_issuance GUC settable only from allowlisted functions, no edit or delete of archived workpapers, EP-only decide with rationale and fresh MFA, the intake destination writes nothing else, grant expiry and revocation, walls over grants, inspectors never write, the firm-scope card reserved to one person.

## Done
- tests/unit/quality/test_q05t26_archive_rule.py: ARCHIVE-001 flags allow_archived_write / app.archived_write outside the allowlist
- tests/integration/backfill/test_q05t26_post_issuance_ac.py (4): manager 403 / partner without fresh MFA 403 / empty rationale 422 on decide with nothing written; manager 403 on reopen-for-reissue; case opens only on an archived audit (409 not_archived, no row); another firm 404 and a client refused
- Not covered here (held by A-07/Q-05 service suites): archived-workpaper edit refusals at the DB guard, intake destination, inspector grants and the firm-scope card — recorded as gaps for the end-pass review

## Progress log
- `2026-11-23` — 2026-11-23: written from SPEC-711 §5 and the matrix; unit rule test passes; integration run in the end pass.
