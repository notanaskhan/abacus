---
id: TASK-8043
title: "A-08-T01: SPEC-657, gate check, AUD-12/13/14/26 and POR-17 screen contracts, vocabulary"
spec: SPEC-657
acceptance_criteria: [AC-0]
risk_zone: amber
status: in-review
branch: a08-t01-fieldwork-spec
worktree: /Users/ayushkbhatia/Accrued/abacus-s45
created: 2026-11-15
updated: 2026-11-15
plan_key: A-08-T01
---

## Objective
Open A-08: the SPEC with numbered ACs and the gate check by P-ID, the five screen contracts for 29
artboards, the glossary and status rows (merged from T04) and the composed design follow-ups
(merged from T40).

## Plan (amber: written before the build)
1. `docs/specs/SPEC-657-a08-audit-fieldwork-depth.md`: gate check, OQ answers, F0–F9 ACs.
2. `docs/screens/{AUD-12,AUD-13,AUD-14,AUD-26,POR-17}.md`; AUD-11 DV-10.
3. **Protected** `docs/product/status-vocabulary.yaml` (eight objects) and `glossary.md`; codegen
   `status_vocabulary` regenerates `_statuses.py` and `status.gen.ts`.
4. Copy lint: "opinion" banned under `screens/AUD-26` and `domain/audits/fieldwork/ssars`.
5. DEC-5028 in the decision log.
Rollback: revert; no runtime reads the new words until T05.

## Progress log
- `2026-11-15` — Planned at the S45 kickoff (#2010); plan above written before building.
- `2026-11-15` — Built. Status codegen ran clean. Tests written (`test_a08t01_vocabulary.py`,
  copy-bans), run at the end pass.
- **Partial (design):** the DF-05 frames (AUD-13 Substantive, AUD-11 MUS) are composed in the
  contracts from existing grammars; Ayush reviews the frames when the screens are built (T28, T13).

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-5028 gate check and OQ answers | Proposed ADR-400/233/157 built on per AMENDMENT-solo | No |
