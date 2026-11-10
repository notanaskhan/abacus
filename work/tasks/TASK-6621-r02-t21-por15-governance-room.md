---
id: TASK-6621
title: "R-02-T21: POR-15 Governance room frontend"
spec: SPEC-646
acceptance_criteria: [AC-5, AC-7]
risk_zone: green
status: in-review
branch: s34-r02-t21
worktree: /Users/ayushkbhatia/Accrued/abacus-s34
created: 2026-11-10
updated: 2026-11-10
plan_key: R-02-T21
---

## Objective
POR-15 a to f render from live data for Victoria Lam, and the reduced shell offers no route to
management's requests.

## Built
- `apps/web/src/screens/POR-15/` (index, copy, scenarios, test) on T7's reduced shell
  (`governanceNav`: Communications, Reports, Questions for you with the server's count).
  - Rail: the body's name and subject, the room's letters (server status words through
    `governance_room_letter`; sub-lines from sent, due and acknowledged dates), the Committee band
    with each member's acknowledgement.
  - Paper pane: T10 card (firm and address from the brand, the long date, "Members of the …",
    the approved sections with "- " lines as lists, the signature), Download PDF, the private
    thread under the letter, the sticky acknowledge bar (Ask the auditor… and Acknowledge with
    `seen_hash` + Idempotency-Key; 409 toasts and refetches).
  - Questions for you: the room's inquiries, long answers, the privacy note, Send answers
    through T-02's questionnaire service (each answer at the version read with If-Match, then
    submit).
  - Reports: the room's released deliverables with Download (the latest version).
  - Empty (no letter sent), not allowed (a grant that opens no room: 404) as designed states;
    390 with a segmented control (Communications, Questions for you) and a full-width Acknowledge.
- `fixtures/seed/portal-por15.ts` and `fixtures/scenarios/POR-15.ts` (a to f, NOT_ALLOWED),
  replacing R-02-T13's unused two-state placeholder.
- Portal routes `/governance` and `/governance/$communicationId` read `?tab=`; Communications
  moved from the planned nav map to production's (the planned map is now empty).

## Progress log
- 2026-11-10: built; tests run at the S34 end pass.
- Copy conflict: the handoff's planning letter has a "How we use technology" section naming the
  product and its agent, while the screen bans both words and the portal never renders the
  product's name (AGENTS.md frontend rule 7). The fixture omits that section; the live letter is
  the firm's approved text from AUD-22, so a firm letter carrying it would render it. Follow-up
  for A-07's letter template: the portal paper should drop or reword that section (decision for
  the template owner; not changed here).
- Partial: the rail's "· from Margaret Okonkwo" on the planning row is not on `RoomLetterRowOut`
  (no sender); the row reads "Sent Sep 18". After Send answers the screen shows "Answers sent"
  (the inquiries list has no answered state yet).

- 2026-11-10 (partial narrowed): the room's letter rows carry `sent_by` (the person whose send put
  the letter in the room, `governance_communication_sends.sent_by`), and POR-15's rail reads
  "Sent Sep 18 · from Margaret Okonkwo" as the handoff draws it. The "How we use technology"
  section stays a decision for A-07's letter template owner.
