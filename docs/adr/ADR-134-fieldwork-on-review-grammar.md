---
id: ADR-134
title: Fieldwork sign-off, review notes and workpapers ride the review grammar (proposal P-07, epic P-04)
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it. Never work around it silently.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
The repo built fieldwork before the plan's review engine. It holds three fieldwork-only tables: `item_signoffs` (SPEC-040, TASK-100), `review_notes` (SPEC-041) and `workpaper_signatures` (SPEC-037, ADR-131). The plan has one engine for all of this: a red `review` module with `sign_offs` L1-L5, `review_notes` and `review_note_events`, a content hash and computed staleness (DEC-36, P-07; the roadmap and status files call the same epic P-04, tasks T18 and T21). Two parallel sign-off models would give two staleness rules and two segregation checks on the most sensitive records in the product. The glossary also bans `sign_off` today, so the plan's table name is blocked until the glossary changes. Reconcile item 2 (docs/plan/status/reconcile-2026-10.md, "Contradictions") set the default: P-04 is the single engine and fieldwork is its first consumer.

## Decision
1. The `review` module's `sign_offs` and `review_notes` are the only sign-off and review-note records. Fieldwork is the first consumer. **No new sign-off, review-note or signature tables** are added outside `review`.
2. Fieldwork registers its targets through `review.register_reviewable(target_type, provider)`: workpapers, procedure items and rows. The owner supplies the content hash, version, preparer user ids and required levels.
3. The fieldwork tables (`item_signoffs`, `review_notes`, `workpaper_signatures`) are migrated onto the grammar around S10-S11 in one reversible migration (P-38 policy, ADR-135). Until then they stay as they are and take no new columns.
4. TASK-100's rules are kept and become grammar rules: the preparer differs from the reviewer (R-SO-3 segregation), and a sign-off goes stale when the signed content changes. Staleness is computed from the content hash, never updated.
5. ADR-131's states (`draft` -> `ready` -> `reviewed`), its immutability of reviewed versions and the preparer/reviewer roles of its Q2 stand. Only where the signature is stored changes.

## Options considered
### Option A: fieldwork rides the review grammar — chosen
- Pros: one hash, one staleness rule, one segregation check; Home gates and the Board read one source.
- Cons: a migration at S10-S11; fieldwork waits for the `review` services.

### Option B: keep the fieldwork tables and bridge them later
- Pros: no migration.
- Cons: two models for the same act; every consumer handles both.
- Why rejected: the reconcile default is a single engine, and bridging gets harder once real data exists.

### Option C: generalise `review_decisions` (the DEC-36 option a)
- Why rejected: DEC-36 chose a new red `review` module.

## Consequences
**Positive**
- One audit-grade sign-off model for fieldwork, tax, close and statements.

**Negative / costs accepted**
- Fieldwork screens and tests change once, at the migration.

**Follow-up work created**
- **Code:** migrate `item_signoffs`, `review_notes`, `workpaper_signatures` onto `review`; repoint `sign_items` and `fieldwork/notes.py` at the review services. Epic P-04 (tasks T18, T21; EP-12), S10-S11. Services land S10-S16.
- **Specs:** amend SPEC-037, SPEC-040 and SPEC-041 data models to name the review tables. Same epic, S10.
- **Glossary:** allow `sign_off` in `docs/product/glossary.md` for the review module (DEC-36). Epic P-04, S3-S4 with the `review` schema.
- **Matrix:** sign-off and review-note actions in the `review` matrix section (per-module matrix file, ADR-140). EP-12, S10.
- **Registry:** `review.register_reviewable` entries for workpapers and procedure items; `TABLE_OWNERS` moves the three tables to `review`. EP-12, S10-S11.

## Enforcement
- [ ] Architecture rule: no table named `*signoff*`, `*signature*` (workpaper) or `review_notes` is owned by a module other than `review` (schema_check `TABLE_OWNERS`).
- [ ] Test: preparer cannot sign at the reviewer level; a content change marks the sign-off stale (ported from TASK-100 tests).
- [ ] Test: a signed workpaper version cannot change (ADR-131).
- [ ] Reviewer agent checklist item: no new sign-off table.

## Guidance for agents
Until the migration, extend nothing in the fieldwork sign-off tables. New fieldwork work that needs a sign-off or note should call the `review` service or stub its contract (library L02).

**Do**
```
review.register_reviewable("workpaper", provider)   # owner supplies content_hash
```

**Don't**
```
op.create_table("procedure_signoffs", ...)           # a second sign-off model
```

## Revisit when
The migration is done (mark the three tables retired), or the review grammar cannot express a fieldwork rule.

## Related
- P-ID: P-07 in docs/plan/09-decisions-adrs.md section 9.4; the review engine is built in epic P-04. Proposal P-04 (work items and gates) is ADR-136, a different decision. DEC-36.
- Amends: ADR-131 Decision clause 2 (where the signature record lives; states and roles stand) and Enforcement item "workpaper versions and signatures are insert-only" (now satisfied by `sign_offs`); ADR-132 Decision clause 4 (the conclusion is signed through `sign_offs`). All other clauses stand.
- Extends: ADR-004, ADR-005 (P-07 row). Depends on ADR-135 for the migration policy.
- Specs: SPEC-037, SPEC-040, SPEC-041; TASK-100.
