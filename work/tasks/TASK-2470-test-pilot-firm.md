---
id: TASK-2470
title: The synthetic test pilot firm PF-X1 (Brightwater Hale) for the ops rows
spec: SPEC-403
acceptance_criteria: [AC-1]  # Ayush 2026-11-01: a seeded test firm stands in for a live pilot firm
risk_zone: amber
status: in-review
epic: Q-04
plan_key: S19-test-firm
branch: s19-test-firm
created: 2026-11-01
updated: 2026-11-01
---

## Objective
Ayush, 2026-11-01 (relayed by the Sprint 21 session): "instead of a live firm, we could seed a
test firm, which could serve as the platform we need to conduct all the ops rows / tasks that
would have otherwise been done with a live firm." About 160 rows wait on a live firm (DEC-1391).
Give a seeded synthetic firm the pilot facts the go-live tooling reads, and record which
pilot-firm clauses it satisfies and which still need a real firm.

## Plan
Ayush chose Brightwater Hale itself (it alone carries the Feld and Ridgeline returns, consents and
the fake CCH that the tax ops rows and the canary J06 walk need; a second copy would collide on
the scenario's global ids).
- `deploy/windows.yaml`: PF-X1, `synthetic: true`, no `real_data_since` (no window applies, the
  platform's guards stay inert, DEC-68); `release_windows` gains the `synthetic` key and refuses
  `real_data_since` on it; `Firm.live_on` is never true for it.
- Pilot-code patterns (dossier, pilot log, on-call, feature requests) accept `PF-X…`.
- `docs/ops/go-live/PF-X1.md` from the template, marked as the test firm.
- `brightwater_hale/pilot.py`: the `pilot` slice, enrolments through `platform.api.enrol_pilot`
  (Feld 2025 return, Northwind EBP audit; shadow; Sep 1, 2026 to Oct 20, 2027; baseline 14);
  `make seed-staging` adds `--slice pilot`.
- DEC-1530 amends DEC-1391's rule 2; the status file and AGENTS.md say so.
- Tests: unit (windows file, synthetic key, slice events), integration (the slice enrols through
  the service; `compute_pilot_week` reads the enrolments).
- Rollback: revert the PR; enrolments are rows in a synthetic tenant only.

## Progress log
- `2026-11-01` — Built in worktree `wt-tf` (the s19-stacked session holds abacus-s19). The
  windows change is a P-29 policy file ("both founders approve"): Ayush's direction is recorded
  as the approval; notanaskhan's co-approval is a human to-do in DEC-1530.

## Handoff
- **Current state:** PR open, held for the batch.
- **Exact next step:** batch merge; then `make seed-staging` on staging (deploy lock) to write
  the enrolments.
