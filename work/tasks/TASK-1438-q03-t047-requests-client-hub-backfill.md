---
id: TASK-1438
title: "Back-fill TASK-033, TASK-037, TASK-039 and TASK-060 from SPEC-018, -021, -023 and -031 (Q-03-T047)"
spec: SPEC-031
acceptance_criteria: [AC-1, AC-2, AC-3, AC-5, AC-6, AC-7]
risk_zone: amber
status: in-review
epic: Q-03
plan_key: Q-03-T047
branch: s11-trust-tests
test_author: ayushkbhatia
test_session: 2026-10-27, branch s11-trust-tests (S11 lane 7; a clean session following .claude/skills/ac-test-author/SKILL.md, from the spec, contracts and ADRs only)
created: 2026-10-27
updated: 2026-10-27
---

Frontmatter names SPEC-031 (one spec per task file); the suite also covers SPEC-018 AC-1 to
AC-5, SPEC-021 AC-1, AC-2, AC-4, AC-5 and SPEC-023 AC-1 to AC-5 (TASK-033, TASK-037, TASK-039).

## Objective
"Each of the four specs has its ACs covered by named tests and the client hub never returns firm
status codes or agent fields."

## Plan
- **File:** `backend/tests/integration/backfill/test_q03t047_requests_client_hub.py`, over HTTP on
  the migrated Postgres and the compose S3 image; workbooks built with openpyxl.
- No production change, migration, flag, matrix or registry edit. Rollback: delete the file.

## Results (31 tests: 28 pass, 3 strict xfail)
- SPEC-018: AC-1 preview (sheet, headers, 20 rows, mapping; nothing stored or audited); AC-2
  import counts, area from the cell, tier, `request_list.imported` once; AC-3 duplicates
  case/space-insensitive, never changed; AC-4 not a workbook and an unknown sheet are 422 with
  codes, **a mapped column past the sheet is xfail (ED-167)**; AC-5 staff, reviewer, client 403,
  a senior may import.
- SPEC-021: AC-1 versions newest first with provenance; AC-2 attachment, media type, one
  `evidence_version.read` audit, **a fingerprint mismatch answers 500 not 409 `integrity_failed`
  (xfail, ED-167)**; AC-4 send-back shows on the version with its reason and decider, a reviewer
  cannot accept; AC-5 outsider and another firm refused, a client refused an item hidden from them.
- SPEC-023: AC-1 on-behalf upload (`firm_upload_for_client`, note, received, audited, client
  history `added_by: firm`); AC-2 inbox listing with at most three suggestions, duplicate 409;
  **AC-3 a contributor's drop answers 500 (xfail, ED-167)**; AC-4 assign makes evidence, leaves the
  inbox, audits whether a suggestion was followed, an accepted item refuses (409); AC-5 discard.
- SPEC-031: AC-1 the firm's words reach the client; AC-2 empty without template or kind, fixed copy
  for a kind (`kind_default`); AC-3 manager edits audited, staff/reviewer/client refused; AC-5 no
  trial balance, no gap; AC-6 your part 2 · 1 · 135 minutes; AC-7 history newest first, send-back
  reason and note shown, rejection `not_accepted` with no note; Q-03-T047: client-view and your-part
  carry no firm status code and no agent field.

## Spec drift followed
- SPEC-018 AC-5: F-03-T30 (ADR-147) gave `client_service` `request_item.create`.
- SPEC-018 AC-2 tier: SPEC-022's rules may tier a row whose cell is empty; the test asserts the
  file set no override.
- SPEC-021 AC-5: SPEC-020/031 gave `client_admin` `evidence.read` on client-visible items; the
  refusal is tested on a hidden item.
- SPEC-031 AC-6: since P-06 (C5, ADR-147) a client counts only items of a published binder; the
  test publishes the binder.

## Not covered (why)
- UI ACs (SPEC-018 AC-6, SPEC-021 AC-6, SPEC-023 AC-6, SPEC-031 AC-9): screen tests, not HTTP.
- SPEC-021 AC-3 (screening display) needs an agent run (covered by the Q-03-T031 suite);
  SPEC-031 AC-4 (provided by retrieval) and AC-5's gap with a trial balance need connector and
  ledger fixtures; AC-8 (template workbook columns) is the methodology import.

## Progress log
- 2026-10-27: suite written; targeted pass in `-n 2` chunks; three defects found (ED-167, kept as
  strict xfails); seed fixes (an accepted item, the client assignee through its route, a published
  binder). Final: 28 passed, 3 xfailed.
