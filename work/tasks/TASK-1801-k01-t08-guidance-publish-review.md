---
id: TASK-1801
title: Guidance-draft publish path lands in Needs review (K-01-T08)
spec: docs/plan/epics/K-01.md (AC3.8)
acceptance_criteria: [AC3.8]
risk_zone: red
status: in-review
epic: K-01
plan_key: K-01-T08
branch: s13r-k01-t08
created: 2026-10-28
updated: 2026-10-28
---

## Objective
With `methodology.lifecycle` on, TASK-074's "publish drafted guidance" creates the template's next version through `methodology.api` in Needs review (Margaret's queue), never current; off, it behaves as before.

## Plan (red)
- `methodology/service.py` `publish_drafted_version`: read the flag, pass `for_review` to `insert_version` (K-01-T06's landing), audit `needs_review`, emit `methodology.review_requested` for the quality partners.
- No migration, no route or matrix change; the guidance-drafting eval, prompt and unit suite unchanged.
- Tests: `tests/integration/backfill/test_k01t08_guidance_publish_for_review.py` (on and off).
- Rollback: revert; versions already in review stay in review and are approved through the lifecycle.
- DEC-901.

## Progress log
- 2026-10-28: built; tests run in the end-of-batch pass (S13 leftovers).
