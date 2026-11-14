---
id: TASK-7934
title: "T-07-T02: ADR P-48 amendment, instrument_clause as the eleventh citation kind (ADR-343)"
plan_key: T-07-T02
spec: SPEC-000  # row: none (ADR task; T-07 §0.1, §11.2 OQ-1)
acceptance_criteria: [AC-1]  # the amendment states the kind stores no instrument text, only ids, regions and a quote hash; T-07-T11 merges nothing before it is Accepted on origin/main
risk_zone: red
status: in-review
branch: t07-t02-clause-citation-adr
worktree: /Users/ayushkbhatia/Accrued/abacus-s43
created: 2026-11-14
updated: 2026-11-14
---

## Objective
Draft the short superseding ADR that amends ADR-166 (P-48) with an eleventh citation kind,
`instrument_clause`, before T-07's window, so T-07-T11 (verifier, migration) and T-07-T12
(determinations) can build on it.

## Plan (red, doc only)
- Files: `docs/adr/ADR-343-citation-kind-instrument-clause.md` (new), `docs/adr/backlog.md`
  (P-48 amendment row and the minted-numbers line), `docs/adr/README.md` (index row),
  `docs/product/decision-log.md` (DEC-4929).
- No code, migration, registry or flag edits (those are T-07-T11's).
- Rollback: revert the PR; nothing reads ADR-343 until T-07-T11.

## Acceptance
- States the locator `{instrument_id, segmentation_id, clause_id, quote_sha256}` and that the kind
  stores no instrument text (only ids, regions and a quote hash): §Decision 2.
- Verifier contract re-reads the words inside the clause regions from the sealed layer: §3.
- `moved` on a superseding instrument version: §5. Display title such as `Art. III(a)`: §4.
- Accepted on `origin/main` once this PR merges; the plan's two-founder week-2 review and the S44
  Contract Monday are replaced by the solo amendment (items 2 and 7), as ADR-166 itself was.

## Progress log
- 2026-11-14: drafted and accepted (DEC-4929). No tests (doc row); docs gates at the S43 end pass.

## Decisions made during this task
| Decision | Reason | Needs ADR? |
|---|---|---|
| DEC-4929 | T-07 OQ-1's proposed option: an eleventh kind, not `document_text` with a label | ADR-343 |
