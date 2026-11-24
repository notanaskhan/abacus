---
id: TASK-8916
title: "T-08-T23: 1065 v4 check library: eight named checks and data-presence checks"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t23
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T23
---

## Objective
Row: "1065 v4 check library: the eight named checks (K-1 count, Schedule K equals sum of K-1s, M-3 test, TB balanced and unmapped 0, M-2 line 9 equals Schedule L line 21, partnership representative, section 754 documented, PTET recorded) and data-presence checks for the rest, each with anchors and golden cases." Acceptance: "Ridgeline fails C-17 off 6,200 and C-31 with anchors that match its open issues, and every bound check is a pure function with a golden test."

## Done
- tax/standards_checks.py: Facts snapshot + gather (I/O once per return), eight named pure checks with anchors and issue references, twenty presence checks, registration
- registered at tax api import (32 codes with T-08-T14's tie-outs)
- golden tests tests/unit/tax/test_t08t23_check_library.py (30 pass): Ridgeline fails exactly C-17 (off 6,200, tie_out:item_l_m2) and C-31 (decision:section_754)
- firm content draft outside the repo: refdata-drafts/firm-standards/1065-review-checklist-v4.draft.json (42 items, 30 bound), generator _s53tools/checklist_v4.py
- docs/contracts/tax-practice.md check-library section; DEC-5918

## Progress log
- `2026-11-23` — Built in full. Human remainder: import the v4 checklist through K-02 (firm content). The scenario slice T-08-T39 tags Ridgeline's open issues with these references.
