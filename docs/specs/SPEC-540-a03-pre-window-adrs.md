---
id: SPEC-540
title: A-03 pre-window ADRs (P-57 sampling engine, P-63 multi-entity engagements)
status: draft
owner: ayushkbhatia
risk_zone: red
related_adrs: [ADR-006, ADR-050, ADR-132, ADR-160, ADR-340, ADR-341]
related_specs: [SPEC-037, SPEC-316]
created: 2026-10-29
updated: 2026-10-29
---

> **Instructions for coding agents**
> - This spec carries only A-03's S18 pre-window decision tasks, A-03-T23 and A-03-T24. A-03's own
>   SPEC (created at the S20 kickoff) supersedes it for everything else and cites ADR-340 and
>   ADR-341.

## 1. Summary
Record the two decisions A-03 builds on before its window opens in S20: how Accrued draws a
re-performable sample (DEC-81, P-57), and how engagements span several client entities and where
account mapping and consolidation live (DEC-65, DEC-66, P-63).

## 2. Problem and context
A-03's sampler (T02, T04, T05, T07, T10) and its ledger mapping work (T03, T06, T08) need both
decisions accepted by Fri Jul 23, 2027 (S19). Parts of both areas are already built ahead of plan
(journal-entry selection, SPEC-037 and TASK-083; account mapping first slice, SPEC-316 and
migration 0079; `engagement_entities`; entity-scoped connections, migration 0195), so each ADR also
reconciles the plan with what is on `main`. `docs/plan/epics/A-03.md` §0.1, §4.2, §7, §11.

## 3. Actors
| Actor | Role in this feature |
|---|---|
| The builder and the audit CPA | Accept P-57 and P-63 |

## 5. Acceptance criteria
- **AC-1** (A-03-T23) ADR P-57 is drafted with the next number from the S18 block and records
  DEC-81: the in-product sampler, the single RNG primitive, frozen versions with a corpus test, the
  golden fixtures `0x5E2A91` and `0x7C31B4`, server-drawn seeds, sizes from firm content, human
  approval, and import kept as a path. `docs/adr/backlog.md` and `docs/product/decision-log.md`
  record its number. Acceptance by Fri Jul 23, 2027; A-03 T02, T04, T05, T07 and T10 cite it.
- **AC-2** (A-03-T24) ADR P-63 is drafted with the next number from the S18 block and records
  DEC-65 and DEC-66: an engagement's entities, `ledger` owning account mappings and consolidation
  structures while staying dependency-free, the grouping and FS-line taxonomy as versioned firm
  content, one mapping set per entity's trial balance of record, eliminations as adjustments, and
  the connection rule for a multi-subsidiary ledger. `docs/adr/backlog.md` and
  `docs/product/decision-log.md` record its number. Acceptance by Fri Jul 23, 2027; A-03 T03, T06
  and T08 cite it.

## 6. Open questions
- None. Acceptance by the builder and the audit CPA is the remaining step for each ADR.
