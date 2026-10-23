---
id: TASK-935
title: Foundation journey test on the J02 data path, Copperleaf (F-03-T35)
spec: SPEC-047
acceptance_criteria: [AC-11, AC-13, AC-15]
risk_zone: red
status: done
epic: F-03
plan_key: F-03-T35
branch: TASK-934-model-foundation-journey
created: 2026-10-23
updated: 2026-10-23
---

## Objective
"The test walks client, prospect, accepted, contracted, 12 close work items, request uploaded and received, with every invariant asserted" (F-03-T35; F-03 sections 1 and 3.1 to 3.5; chapter 10 section 10.6).

## Plan
- Test only: `backend/tests/integration/test_model_foundation_journey.py`. No product code, migration, registry or flag changes.
- How it runs:
  - `create_app()` runs as the app role with the fake identity provider, using the S3 gateway and the local key service, as in `test_evidence.py`;
  - `create_work_item` goes through `engagements.api` (it has no route);
  - seeding (people, the wall, the client grant) goes through the shared `Seeder`.
- The walk:
  - Copperleaf's "2026 Close" is created through `POST /v1/engagements`, which also creates the client;
  - G1 is recorded with fresh MFA, then independence;
  - G3 is recorded (the signed letter);
  - 12 closes are created and listed on `/v1/work-items`;
  - a request is created; Tess Moreno (`owner` grant) uploads, so it reads `uploaded`; Priya accepts through the decision route, so it reads `received`.
- Invariants:
  - INV-1: the agent principal is refused `acceptance.record` and `evidence.accept`. No final-verb table that has `actor_kind` holds an agent row, and the one review decision is Priya's.
  - INV-3: Lena Park, walled, gets 404 on the engagement, its requests, uploads and work items. It is missing from her lists and from her counts, and she has no access event on the client.
  - INV-4: Tess lists only her request. Ashford's engagement, requests and uploads refuse her with no data, an upload to Ashford stores nothing, and her access events stay on her grant.
  - INV-5: every audit row in the window is `human` or `system`. Each person-made change names Priya or Tess as appropriate: creation, acceptance, letter and the 12 closes are Priya's; the upload is Tess's; received is Priya's. The prospect-to-accepted move has its outbox event.
- Rollback: delete the file.

## What changed
- 1 passing walk and 4 strict xfails. Each xfail names a bug the walk exposed. The walk goes round each one in the open and asserts everything else.
  1. New engagements start `active`, not `prospect`. `insert_engagement` sets no status, and migration 0069 kept `DEFAULT 'active'` (F-03 section 1, story 1.2). The walk sets `prospect` through the Seeder before G1.
  2. Recording the signed letter does not move `accepted` to `contracted`. `transitions.LIFECYCLE` has the system move, but nothing calls it from `record_letter` (F-03 section 4). The walk asserts the letter is signed and nothing blocks client data, and leaves the status alone.
  3. A client user gets 403 for another client's engagement and 404 for one that does not exist, so the answer reveals whether the engagement exists (F-03 story 5.2, POR-02e; DEC-43). The walk asserts the refusal and that no data is returned.
  4. `POST .../request-items` on an engagement with no work item yet answers 500. The default binder's `request_lists` insert violates its work-item foreign key. The walk gives Ashford a close first.
- Not done here: "legacy journey.spec.ts green on staging". That needs the staging run after the S4 batch, by the builder.

## Progress log
- 2026-10-23: the new test passes (1 passed, 4 xfailed). Each xfail fails for its named reason under `--runxfail`. ruff format and check, pyright, banned_patterns and secrets_scan pass on the file.
