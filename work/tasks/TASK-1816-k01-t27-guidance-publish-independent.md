---
id: TASK-1816
title: Independent AC tests for K-01-T08's guidance-draft publish path (K-01-T27)
spec: SPEC-008
acceptance_criteria: [AC-1]
risk_zone: red
status: in-review
epic: K-01
plan_key: K-01-T27
branch: s13r-k01-t27
created: 2026-10-29
updated: 2026-10-29
---

## Objective
ADR-078 suite for K-01-T08 (DEC-901), written from the K-01-T27 row and KNW-02, not from `test_k01t08_guidance_publish_for_review`: it fails if a published guidance draft becomes the current version, skips Margaret's review queue, or is approved by the agent principal.

## Plan
- `backend/tests/integration/backfill/test_k01t27_guidance_publish_independent.py`:
  - lifecycle on: the draft is `needs_review` and not the default; the current version stays published and the default; the draft is in the quality partner's `GET /v1/knowledge/review-queue`, the current one is not;
  - the agent principal (an `agent` actor for Margaret) calling `approve_version` is refused (`Forbidden`), audited once as `decision.refused_non_human` on her behalf, no `methodology_version.approved` row, nothing moves;
  - lifecycle off: TASK-074's behaviour (the drafted version is published and current).
- No product change. Rollback: delete the file.

## Progress log
- 2026-10-29: written and run once: 3 passed.
