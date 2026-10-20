---
id: ADR-144
title: Request status enum migration, follow-up rename and the wrong_document reason
status: accepted
date: 2026-10-20
deciders: ayushkbhatia
risk_zone: red
---

> **Instructions for coding agents**
> - Accepted ADRs are binding. Code that contradicts one must not be written.
> - If a task seems to require breaking an ADR, propose a new ADR that supersedes it.
> - Never edit an accepted ADR. Propose a new one that supersedes it.

## Context
In the repo, request item status `received` means what Accrued shows as "Uploaded - needs review". The Accrued word "Received" means accepted. Leaving that inversion in code is a correctness hazard for every binder, portal and evidence screen. The repo also names the follow-up objects `reminders`, against the glossary's own `follow_up` rule. Plan decision DEC-09 settles the enum; this ADR is P-44 in the plan's ADR backlog.

## Decision
- **Migrate the stored codes** (no mapping layer). Request item codes become `draft · requested · uploaded · received · returned · not_applicable`, with `overdue` derived and never stored, plus the close and client label sets.
- **Mapping** (plan section 9.5.6): `open` becomes `draft` (not client-visible) or `requested`; `received` and `ready_for_review` become `uploaded` (screening is a sub-state); `needs_revision` becomes `returned`; `accepted` becomes `received`.
- **One pre-launch migration** through the REVIEW-001 paths, also adding reason code `wrong_document`.
- **Rename in the same window:** `reminders` and `reminder_items` become `follow_up_schedules` and `follow_up_items`; `/reminders` routes become `/follow-ups`.

## Options considered
### Option A: migrate the stored codes — chosen
- Pros: code and display agree; no inverted word survives.
- Cons: touches requests, evidence and agents hand-off paths in one window.

### Option B: a mapping layer
- Pros: no data migration.
- Cons: `received` keeps two meanings.
- Why rejected: the inversion stays in code.

## Consequences
**Positive**
- One meaning per word across code, API and UI; status pills read from the generated vocabulary.

**Negative / costs accepted**
- A red-zone migration across three modules; the old-code branch in the web app must be removed with it.

**Follow-up work created**
- Code: migration `0059_request_status_v2` and the switch in requests, evidence and agents (epic F-03, S1; task F-03-T15); follow-up rename (F-03-T16, S2); binder cardinality migration lands in the same window (F-03-T14, S1).
- Specs: SPEC-018 and SPEC-021 are re-read against the new codes; epic specs cite codes from the vocabulary file (AUD-03, BND-01..03, POR-03/04).
- Glossary: add `received` (accepted) and `uploaded` (needs review), and the `follow_up` names (F-03, S1).
- Matrix: none.
- Registry: `docs/product/status-vocabulary.yaml` carries the new request codes; the generated enums, CHECK strings and `packages/ui/src/status.ts` follow (ADR-138; F-03, S1).

## Enforcement
- [x] Test: vocabulary drift check in `make check-fast` (ADR-138).
- [x] Test: migration passes up, down and up before merge (ADR-135).
- [x] Lint rule: banned-pattern L12 fails a new `reminder` identifier outside UI copy.
- [ ] Advisory only: none.

## Guidance for agents
Use the generated status enum. `received` means accepted. Never store `overdue`.

**Do**
```python
item.status = RequestItemStatus.UPLOADED   # needs review
```

**Don't**
```python
item.status = "received"   # old meaning: uploaded
```

## Revisit when
The first real firm goes live (ADR-135's pre-launch window ends).

## Related
- Plan: P-44 (section 9.4.2); DEC-09 (decided); DEC-74 (open at time of writing; only the rename is used here); Q-04. DEC-31 (open, binder cardinality) lands in the same window and is not decided here.
- Amends the glossary meaning of `received` and the request specs' status words; no existing ADR clause is overridden.
- ADRs: ADR-138 (status vocabulary is the contract), ADR-135 (pre-launch migration policy).
