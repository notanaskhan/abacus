---
id: TASK-7601
title: W-02-T01 SPEC-653 Workbench sessions; ADR check; Q1–Q3, Q6, Q7 settled; upstream inventory
plan_key: W-02-T01
spec: SPEC-653
acceptance_criteria: [AC-1]  # the SPEC names every endpoint, tool, flag and the settled questions
risk_zone: red
status: in-review
branch: w02-t01-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s40
created: 2026-11-12
updated: 2026-11-12
---

## Objective
SPEC-653 from W-02 §1 to §8 and chapter 05 §5.2.4, §5.2.5, §5.3.7 and §5.4.6: the acceptance
check of the epic's ADRs against the repository's numbers, Q1 (DEC-87 list membership), Q2
(aggregate tax counts), Q3 (ApprovalCard Edit…), Q6 and Q7 settled, and the inventory of what P-10,
F-07, P-09, P-04 and N-01 shipped.

## Plan
- `docs/specs/SPEC-653-w02-workbench-sessions.md` (new). Decision DEC-4601. No code.
- Rollback: revert; nothing reads a SPEC.

## Findings
- The epic's ADR numbers are plan reservations; the repository's are ADR-235 (P-23), ADR-233
  (P-22), ADR-234 (P-46), ADR-230 (P-24), ADR-169 (P-47), ADR-161 (P-35), ADR-232 (P-15), ADR-186
  (P-49). ADR-232 to ADR-235 are proposed (DEC-3016, Ayush's acceptance).
- No P-10 cut item to absorb (badge stream and side queue shipped).
- No firm-level Files folder exists (N-01 folders are per work item or per client): W-02-T23
  decides between adding one and shipping "Attach it to this session only" alone (§11 R5).

## Partial
- Counsel's confirmation of Q2 is a real-firm gate (no live firm, DEC-1391); W-02 runs only on
  synthetic tenants, so nothing waits on it in W-02.
- "Approved by both founders": one builder; Ayush's acceptance of ADR-232 to ADR-235 is open.

## Progress log
- `2026-11-12` — SPEC-653 written (DEC-4601).
