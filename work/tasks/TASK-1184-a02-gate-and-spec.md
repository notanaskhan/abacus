---
id: TASK-1184
title: "A-02-T01: gate check and SPEC-333 Trial balance and ledger connections (TB of record, layers, ties, entity-scoped connections, framework v1, registry skeleton)"
spec: SPEC-333
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7, AC-8, AC-9, AC-10, AC-11, AC-12, AC-13, AC-14, AC-15, AC-16, AC-17, AC-18, AC-19, AC-20, AC-21, AC-22, AC-23, AC-24, AC-25, AC-26, AC-27, AC-28, AC-29, AC-30, AC-31, AC-32, AC-33, AC-34, AC-35, AC-36, AC-37, AC-38, AC-39, AC-40, AC-41, AC-42, AC-43, AC-44, AC-45, AC-46, AC-47, AC-48, AC-49, AC-50, AC-51]
risk_zone: green
status: done
epic: A-02
plan_key: A-02-T01
branch: s8a-tb-of-record
created: 2026-10-25
updated: 2026-10-25
---

## Objective
"The SPEC merges with numbered ACs, ADR-136 (P-17) is Accepted on origin/main, DEC-70 is cited from docs/product/discovery/ledger-choice.md, and the Mon Feb 8, 2027 Contract Monday minutes open both contract issues." (A-02-T01)

## Plan (green zone)
- Gate check against A-02 table 0.1 on this branch's base (origin/s7c-batch):
  - P-17 is repo **ADR-150** (the plan's "ADR-136" alias; repo ADR-136 is engagement work items). ADR-150 is `proposed`, accept-by 2026-11-27. It gates T12, T15 and T16 (integrations) only, none of which is in S8 wave A. Recorded in DEC-315; the TB half proceeds.
  - DEC-70 is `decided` in the decision log; `docs/product/discovery/ledger-choice.md` does not exist yet (it is written at the M3 read, interview-guide step 4). The SPEC cites DEC-70 from the decision log and names the missing file as a human to-do.
  - Contract issues for C9 v1 and C20 v1: agents never open GitHub issues (brief); a human to-do.
- `docs/specs/SPEC-333-trial-balance-and-ledger-connections.md`: numbered ACs from the epic's §3 stories, mapped onto what SPEC-309, SPEC-310 and SPEC-311 already built, with the owning task per AC.

## Progress log
- 2026-10-25: gate checked (DEC-315): ADR-150 (P-17) is `proposed`, gating only T12, T15, T16; DEC-70 decided, `ledger-choice.md` not written yet (M3 read). SPEC-333 written as an outline with AC-1 to AC-51, each naming what SPEC-309 to SPEC-311 built and the row that finishes it. Epic §11.2 answered in DEC-316. `validate_docs` passes. **Human to-dos:** open the C9 v1 and C20 v1 contract issues; accept or amend ADR-150 before T12; write `docs/product/discovery/ledger-choice.md` at the M3 read.
- 2026-10-25: verification on the combined branch: `tests/unit tests/contracts tests/security` 28,895 passed, 5 xfailed; the ledger, retrieval, sign-off segregation, review staleness, TB-of-record and `test_schema_check_db` integration files 579 passed; `make check-fast` clean.
