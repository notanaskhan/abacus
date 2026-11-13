---
id: TASK-7816
title: "Full-stack journeys: J04's trace to source and pbc-ai on the Sep 24 pass (P-03-T25, P-04-T45)"
spec: SPEC-000  # rows P-03-T25 and P-04-T45
acceptance_criteria: [AC-20]  # the journeys that read seeded data pass on the local full stack
risk_zone: amber  # an additive field on the agents contract, a seed slice, SHL-07 on AUD-03
status: in-review
branch: lo38-j04-trace
worktree: /Users/ayushkbhatia/Accrued/abacus-lo38-j04
created: 2026-11-13
updated: 2026-11-13
plan_key: P-03-T25
---

## Objective
Make J04's "trace to source" (P-03-T25) and "pbc-ai through SHL-10" (P-04-T45) run on the full
stack's Sep 24 pass. Both were `fixme` on the full stack (TASK-7813, TASK-7814).

## What blocked them
1. No slice seeds a Granite Peak FY2026 PBC upload that the agent screened, with a flagged check, a
   verified citation and a pending C3 proposal.
2. Hannah Leclerc is not on Granite Peak's FY2026 team (`team_of(A2)`: MO, OH, SB, CH, and Caleb
   Dunn from Sep 10).
3. AUD-01's row opens AUD-02, not AUD-03. Nothing in the SPA links to AUD-03: AUD-01's PBC cell is
   plain (AUD-03 is still `planned` in the manifest). A gate's row on HOME-02 does open it
   (`AUD-03?auditId=…&item=…`, assurance `review_gates.subject_route`).
4. Found here: AUD-03 hosts no SHL-07 cited cell (`[data-cited]`). Only the KNW-03 and gallery
   artboards mount `CitedCell`.
5. Found here: the backend never fills `ScreeningCardOut.proposal_ref` (P-04-T42 added the field
   and the "Review…" button; the button hides while it is null).
6. Found here: AUD-03's rows never carry `screening` live (only fixtures set it), so the glyph and
   the card never show on the full stack.
7. Found here: a typed proposal's read never names who decided (`decision` was always null), so
   SHL-10's re-read after Approve said "Approved" without the person.
8. Found here: the seed leaves `screening.card`, `evidence.viewer_v1` and
   `evidence.citations_v2` off, and the loader's upload had no masked rendition (SHL-08 pages
   404).

## Plan
- **Seed** (`pbc_screening` slice, opt-in, after `sampling`): through the services, as the people
  the design names, before 10:20 AM on Sep 24 (DEC-4814):
  - Granite Peak's letter E14 recorded as signed (Luis Ferrante Sep 3, Margaret Okonkwo Sep 16)
    through `record_letter_v2`, so G3 is met.
  - Granite Peak's PBC list published by Omar Haddad (Audit Manager on A2) on Sep 17.
  - Luis Ferrante uploads a corporate card statement to "Bank statements (year-end month +
    subsequent month)" in the portal on Tue Sep 22 (DEC-4814, synthetic).
  - The upload reviewer's real path in the loader's process: extraction, checks, words, PII scan,
    `create_review_run`, `review` on the fake gateway with one recorded answer
    (`responses/granite_card_statement.upload_review.json`), then `compose_for_item`. Code
    verifies the quotes; the aggregate flags "Does this answer the request?".
- **Backend:** `ScreeningCardOut.proposal_ref` becomes the typed C3 ref `upload_review:<id>` of
  the composed review whose shown `irrelevant` flag makes the file "Wrong document", while it is
  pending (the adapters' own state) and not hidden by shadow. The field is a string (it was typed
  UUID but never filled; the SPA already reads a string). `make generate`.
- **SPA:** AUD-03's screening card renders each flag's verified reason in an SHL-07 `CitedCell`
  over the flag's citation (by id), with `CitationPopoverContainer` and "Open source" opening
  SHL-08 on the cited region.
- **J04 spec:** persona Omar Haddad (added to `personas.ts`); the walk is HOME-02 → the Granite
  row's Open → AUD-03 with the request selected; both tests tagged `SEP_24_PASS` with
  `seededAt(...)`; the fullstack `fixme` comes off, the fixture one stays.
- **Nightly:** `pbc_screening` on the Sep 24 seed line of `.github/workflows/e2e.yml`.
- **Tests:** unit tests for the slice's events and the recorded answer's quotes; screening card
  `proposal_ref`; AUD-03 cited reason.
- **Rollback:** drop the slice from the seed line; the field returns null.

## Delivered
- `pbc_screening` slice (DEC-4814): flags, Granite's list published Sep 17 (bootstrapped), Luis's
  card statement uploaded Sep 22 through `evidence.api.upload_synthetic`, the reviewer's own path
  on the fake route with `review_answers/granite_card_statement.json`, then the aggregate.
- `ScreeningCardOut.proposal_ref` = the pending `upload_review:<id>` (string; `make generate`).
- `RowFacts.screening` from an agents-registered verdict provider (`register_screening_verdicts`).
- Typed proposal reads name the decider (`evidence.api.standing_decisions`).
- AUD-03: the flag's verified reason is an SHL-07 `CitedCell` button (citations by id), with the
  popover host and "Open source" to SHL-08.
- J04: persona Omar Haddad; walk HOME-02 "Approvals & sends" → Evidence version → Open → AUD-03;
  both tests `@sep24` with `seededAt`; `pbc_screening` on the nightly's Sep 24 line.
- Tests: `tests/unit/synthetic/test_task7816_pbc_screening_slice.py`; proposal_ref and verdict
  provider in `test_p06t20_screening_aggregate.py`; read-after-verdict in
  `test_p04t25_proposal_adapters.py`; AUD-03 c's cited reason in `AUD-03.test.tsx`.

## Verified locally (2026-11-13)
- Fresh `make db-reset` + Sep 24 seed with `pbc_screening`: 565 events, first try.
- `--grep @sep24` J04: 2 passed. All `@sep24`: J03 7 and 7b pass with the slice loaded (J04's pair
  needs a fresh load: pbc-ai's approval decides the seeded upload, so a second run finds no gate).
- Fixture project J04: 6 passed, 11 fixme (unchanged).
- `tests/unit/synthetic` 530 passed; `tests/unit/scenarios` 151 passed; integration
  `test_p06t20_screening_aggregate.py`, `test_p04t25_proposal_adapters.py`,
  `test_p04t28_proposals_independent.py` 66 passed; vitest AUD-03 and SHL-07 42 passed.
- Not run: `make check`, the full integration and vitest suites, the E0 nightly pass.

## Follow-ups
- HOME-02's "Upload review" (Agent outputs) row reads `/v1/proposals/<uuid>` without the typed
  `upload_review:` prefix, so its detail says "This item couldn't load" (404).
- AUD-01's PBC cell still does not link to AUD-03 (AUD-03 is `planned` in the manifest).

## Progress log
- 2026-11-13: plan written; studying the stack.
- 2026-11-13: built. Found on the way: no seeded audit has a CLI-07 acceptance record or a
  recorded letter, so G1 and G3 never read met; `upload` and `publish_binder` refuse. The slice
  bootstraps the publish (as Northwind's list is) and uploads through `upload_synthetic`
  (DEC-4814). The reviewer's request hash was captured from the fake responder's refusal and
  recorded in `review_answers/`. A load that fails inside an event leaves audit rows under its
  trace, so a rerun counts the event as loaded: recover with `make db-reset`, not a second load.
  Local loads under a load average near 25 hit the isolated child's wall-clock timeout in the
  standards import (`IsolationFailed`, not this change); a rerun resumes.
- 2026-11-13: the first live runs found gaps 6 to 8 above; fixed. A local fixture run must not
  reuse a running `make dev` vite (it serves the full stack): run it on a free
  `ABACUS_PORT_OFFSET`. Two sessions wrote the test lock in the same minute at 02:25; check the
  file's content after writing it.
