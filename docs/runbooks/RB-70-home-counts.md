---
id: RB-70
title: Home counts (count mismatch, projector and activity rebuild, flag rollback)
owner: builder
alarms: []
last_rehearsed: never
rehearse_by: 2028-03-03
---
# RB-70 · Home counts

| Field | Value |
|---|---|
| Owner | the builder |
| Task | I-01-T26 (I-01 §8.3); the count rule is I-01-T25's test |
| Alarm | none yet: a count mismatch is reported by a person or the count-equality test |
| Contract | `docs/contracts/home-and-gates.md` (C13 v1, frozen) |

**The rule.** Every surface reads one count source, `GET /v1/human-gates/counts`: HOME-01's "Waiting on you" header, its summary line and the Approvals badge, HOME-02's band headers, SHL-04's Approvals tab and I-02's brief. A difference between any two is a defect, never "eventual consistency": find which surface stopped reading the source.

## 1. A count mismatch

1. Ask which two surfaces differ, for which person, at what time. Reproduce as that person on staging (or PF-X1, the synthetic firm), never with a real firm's data in a ticket.
2. `GET /v1/human-gates/counts` and `GET /v1/human-gates?assignee=me` as the person: `total` must equal the list's `total`, and the bands must sum to it.
   - **They agree, a surface does not:** that surface computes its own number. Fix the surface (it must read `total`); I-01-T25's `apps/web/src/domain/home/countEquality.test.ts` holds every surface to the source in fixture mode, so add the case there first.
   - **They disagree:** the projection is stale or a source is mis-registered (go to 2).
3. A walled client's gates are left out of both the list and the counts, and nothing says any were (INV-3). A person who "expects" a gate from a walled client is not seeing a bug.

## 2. Rebuild the gate projection

`human_gates` is rebuildable from the owners' records (C13, DEC-320; `review-grammar.md` §4):

```bash
cd backend && uv run python -m abacus_tools.reproject_human_gates <tenant-id>
```

It reruns every registered gate source over the firm's records and writes the projection in place; snoozes and reassignments are kept (their own insert-only tables). Then repeat §1 step 2.

## 3. Rebuild the client activity

HOME-01's client activity is `home_activity_items`, a 90-day projection (I-01-T12, DEC-900):

```bash
cd backend && uv run python -m abacus_tools.reproject_home_activity <tenant-id>
```

## 4. Roll back

`home.approvals` (HOME-02 live) is per firm: turning it off sends rows back to their host gates (DV-3; `RB-48-home-approvals-flip.md`). The counts endpoint itself has no flag: it is the one source, so a rollback never changes what the badge says, only where a row opens.

## 5. After an incident

Record the case in `countEquality.test.ts` (a persona and the action that split the counts), and the cause in the task file's progress log.
