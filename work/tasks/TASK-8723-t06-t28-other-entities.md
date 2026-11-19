---
id: TASK-8723
title: "T-06-T28: Brightwater Hale other-entity content for TXP-13"
spec: SPEC-702
acceptance_criteria: [AC-1]
risk_zone: amber
status: in-review
branch: t06-t28-other-entities
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-19
updated: 2026-11-19
plan_key: T-06-T28
---

## Objective
other_entities_slice.py: Bluestem's 2025 1120-S (Accepted Mar 13; AAA 1,240,000 + 860,000 + 12,400 - 4,200 - 620,000 = 1,488,200; Arjun Mehta 70% / Sunita Rao 30% rows), Ashford's 1120 provision (2,134,650 + 122,550; 28.9%; b2 off 1,200) and Lakeshore's 990 (4,014,000; 80.0%; 87.4%), every derived figure by E10/E11.

## Plan (amber)
1. scenarios/brightwater_hale/other_entities_slice.py; tests/unit/synthetic/test_t06t28_other_entities.py.

## Progress log
- `2026-11-19` — Built; tests pass (3). Not built: the service-API load (T-06-T42), the AUD-38 preview 121/5/2, TPL-14 a-f and the fake engine import's Ridgeline diagnostics (they ride the hand-off and form-preview tasks); A-03-T16 parts one and two are still in progress. Gates and tests run once at the S51 end pass (build first, test last).
