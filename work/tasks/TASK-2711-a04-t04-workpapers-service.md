---
id: TASK-2711
title: A-04-T04 workpapers service (projection, versions, cell edits, export, registrations)
spec: SPEC-620  # A-04 §3.1, §4.3 and docs/contracts/workpapers-core.md
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
epic: A-04
plan_key: A-04-T04
branch: s22-a04-t04
worktree: /Users/ayushkbhatia/Accrued/abacus-s22
created: 2026-11-01
updated: 2026-11-01
---

## Objective
- **[AC-1]** "An L2 sign-off goes stale after a cell edit, two exports of one version are
  byte-identical, and a citation to Exceptions!D2 verifies through C4."

## Scope
**In**: `workpapers/core.py` (record projection by tab and version, workpaper states, versions,
cell edits through `review.api.record_value` with `expected_version` and the override reason,
deterministic export, the `workpaper_cell` citable and field owner); `content_of` keys non-main
sheets and typed values; `workpaper.version_created` outbox event; registrations in `api.py`;
routes in `contract.py`; error codes, activity review, contract doc; tests.
**Out**: drafts and suggestion adoption (A-04-T11), attention-flag routes (T19), procedures and
tailoring (T07), the cockpit rail screen (A-04 screens).

## Plan (amber)
1. Versions: an edit is the paper's next version (`cause` edit); a sign-off still snapshots one.
   `expected_version` is the newest version number; a mismatch is 409 `version_conflict`.
2. A cell whose newest row is the agent's (or a suggestion) needs a reason to override (422
   `reason_required`). `record_value` needs a note for every human value: a plain entry's note is
   "Entered on the workpaper" (code-written, DEC-1762).
3. Staleness stays computed: the content hash now includes typed values and `<sheet>!<cell>`
   keys (SPEC-308 main-sheet content unchanged, so existing sign-offs keep their hashes);
   `workpaper.content_changed` drives the stale detector.
4. Export: openpyxl, fixed properties and ZIP times, formula leads as text (ADR-042, ADR-052).
5. Rollback: revert the PR; the routes fall back to 501 stubs; no schema change here.

## Progress log
- 2026-11-01: built; tests run in the S22 end pass.
