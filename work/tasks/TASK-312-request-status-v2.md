---
id: TASK-312
title: "F-03-T11 + T15 [mig 0071]: request status v2 — draft · requested · uploaded · received · returned · not_applicable, across backend and web"
spec: SPEC-306
acceptance_criteria: [AC-5]
risk_zone: red
status: done
branch: task-312-request-status
worktree: spec005
created: 2026-10-20
updated: 2026-10-21
---

## Plan
- Migration **0071**:
  - Codes rewritten per §9.5.6:

    | Old code | New code |
    |---|---|
    | `open` | `draft` (firm-only) or `requested` |
    | `received`, `ready_for_review` | `uploaded` |
    | `needs_revision` | `returned` |
    | `accepted` | `received` |

  - CHECK takes the new codes. `not_applicable` must carry its reason (`request_items_na_whole`).
  - A BEFORE INSERT/UPDATE trigger keeps draft and requested in step with client visibility and stamps `requested_at`.
  - New columns: `requested_at`, `sent_at`, the not-applicable facts, `client_ignored_at`, `incorporation_state` (+ by/at).
  - New review reasons `wrong_document` and `wrong_year`.
- Backend:
  - requests, evidence, connections and engagements read and write the new codes;
  - the `RequestItemOut`, `ItemHitOut` and decision `item_status` fields use the generated `RequestStatus`;
  - the upload's audit action is now `request_item.uploaded`;
  - the screener's proposal values (`ready_for_review`, `needs_revision`) are unchanged: they're the agent's output, not a status.
- Banned pattern **REQ-002**: a request status compared with, filtered by or set to a retired code fails check-fast. It covers the requests, evidence, connections and engagements modules.
- Web (T11 and T15 together):
  - the `STATUS.request` and `clientRequest` vocabulary;
  - `join.ts`, Board (status chips and filters), DueDates, ClientEngagement, Overview, InboxPanel, ItemDetail and the gallery;
  - fixtures mapped to the new codes.
- Behaviour change, deliberate: an `uploaded` item takes further evidence. The old `ready_for_review` refused it, but both are now one state. Retrieval still refuses `returned` and `received`.
- Rollback: downgrade 0071.

## Definition of done
- [x] Local data rewritten: 82 requested, 45 uploaded, 3 received.
- [x] up/down/up passes (schema_check).
- [x] Unit (12,209) passes.
- [x] Integration passes: engagements, evidence, retrieval, ledger, board reads, walls, screening and the workflows (about 1,000 cases).
- [x] Web passes (418).
- [x] REQ-002 tests pass.
- [x] check-fast passes.
