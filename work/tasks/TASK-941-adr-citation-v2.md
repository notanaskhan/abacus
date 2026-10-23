---
id: TASK-941
title: ADR for P-48 Citation v2 and number provenance - ADR-166 (plan alias ADR-144), accepted under the solo amendment (P-03-T27)
spec: SPEC-322
acceptance_criteria: [AC-1, AC-2, AC-3, AC-4, AC-10, AC-36, AC-37]
risk_zone: red
status: done
epic: P-03
plan_key: P-03-T27
branch: p03-t01-t27-trust-kit-docs
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"ADR-144 is Accepted … before the C4 stub (T02) merges, and it records the ten kinds, verify-before-display, moved and broken states and the reserved annotation_id locator slot." (Solo edition: the builder accepts; no second decider. ADR-144 was taken by P-44, so the number is ADR-166.)

## Plan (red zone, docs only)
- **Files:** `docs/adr/ADR-166-citation-v2-number-provenance.md` (new), `docs/adr/README.md` (index row), `docs/adr/backlog.md` (P-48 row: ADR-166, accepted, DEC-147; minted-numbers line), `docs/product/decision-log.md` (DEC-147).
- **Migrations, registry, flags:** none (P-03-T02 and T04).
- **Tests:** `uv run python -m abacus_tools.quality.validate_docs` (frontmatter and index). The ADR's rules are proven by P-03-T03 and the P-03 independent suites (SPEC-322 AC-1 to AC-5, AC-10, AC-36, AC-37).
- **Rollback:** revert the commit. Nothing in code reads an ADR.

## What changed
ADR-166 records:
- one insert-only `citations` table in `evidence`;
- the ten kinds and their verifier registry;
- verify before display, with the eight `verification_reason` codes;
- no stored quote text (`quote_sha256` only, with quotes re-read from the masked word layer);
- `moved`, `broken` and `relinked` computed from insert-only `citation_events`;
- relink as a human act, enforced in three layers;
- the reserved `annotation_id` locator slot;
- the reserved 501 create;
- the number-provenance rule, enforced in P-10.

## Progress log
- 2026-10-23: drafted from chapter 03 §3.7.2, chapter 05 §5.3.10 and P-03 §§3, 4.2, 4.3 and 6, on origin/main at a4cd07d. The plan's "ADR-144" alias was already ADR-144 (P-44, request status migration), so the ADR took the next free number, ADR-166, and the mapping is written in the ADR and in the backlog row. ADR-066 is extended, not superseded (it is accepted, and its rule still holds). The coordinator said the C4 stub's models carry `relinked` as a fourth state code, so clause 6 names it. This task file landed in the second commit with SPEC-322, because `validate_docs` needs the spec to exist.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-147 | P-48 accepted with the plan's option; the ADR-144 alias maps to ADR-166 | this is the ADR |
