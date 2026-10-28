---
id: SPEC-360
title: "Review grammar services: review notes, bulk sign-off, decision cards, proposals, the C3 freeze and checkpoints (P-04-T21 to T27, T32)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-031, ADR-050, ADR-160, ADR-161]
related_specs: [SPEC-308, SPEC-313]
created: 2026-10-27
updated: 2026-10-28
---

## 1. Summary
The C3 review-note, bulk sign-off and decision-card routes (`docs/contracts/review-grammar.md` parts 1 and 2) go live behind `review.grammar_api`, on the P-04 F2 to F4 behaviour (`docs/plan/epics/P-04.md` §3) and ADR-160 clauses 4, 6, 8 and 12. Decisions: DEC-500 to DEC-504, then DEC-600 to DEC-608 for proposals, the typed adapters, the notification kinds and the freeze (P-04-T24 to T27). Migrations 0210 (sealed note bodies), 0211 (decision card history and analysis requests), 0212 (the decision verdicts on the human-only list), 0230 (proposal and suggestion state guards) and 0231 (their verdicts on the human-only list).

## 2. Acceptance criteria
- **AC-1 Review notes (P-04-T21).** Open notes on RA!C14 and RA!C22 block L2 with `open_review_notes` and count 2, and clearing both lets the same reviewer sign. Bodies are sealed and a body read is an access event; lists carry no body; only the raiser withdraws; the agent raises nothing; the assignee (else the target's preparers) gets `review_note_raised`. Tests: `backend/tests/integration/test_p04t21_review_notes.py`.
- **AC-2 Bulk sign-off (P-04-T22, R-SO-7).** Six workpapers with three ineligible return three signed and three excluded with reasons, and a replay with the same key returns the stored result. The same key with another body is 422 `idempotency_key_reused`; reviewers only; a fresh second factor; never the agent; a hidden target is excluded without saying whether it exists. Tests: `backend/tests/integration/test_p04t22_bulk_sign_off.py`.
- **AC-3 Decision cards (P-04-T23).** Only Margaret Okonkwo can decide the Northwind card, a decide without a rationale returns 422 `rationale_required`, and reassessment on $16,861,000 records No change with the $700 difference. The agent raises cards only through its task scope; options are computed by the kind's provider; MFA per kind; a changed reassessment supersedes the card. Tests: `backend/tests/integration/test_p04t23_decision_cards.py`.
- **AC-4 Proposals and suggestions (P-04-T24; ADR-161; DEC-600 to DEC-602, DEC-607).** A proposal with one unsupported row cannot be approved until that row is removed or cited, and approval records Proposal approved by Samuel Ito with one field version per row. Approve with edits needs a citation note per edit; reject takes a reason code; route names another approver; a follow-up is recorded; suggestions are adopted (as proposed or edited) or dismissed; 409 `proposal_changed`; 422 `uncited_change`; 503 with no owner to write; never the agent or the platform. Tests: `backend/tests/integration/test_p04t24_proposals.py`.
- **AC-5 Typed adapters (P-04-T25; DEC-603, DEC-604, DEC-608).** Accepting a Granite Peak screening flag through the proposal route writes the same review_decisions row AUD-03 writes today, and a shadow-stage firm sees no proposal. Tests: `backend/tests/integration/backfill/test_p04t25_proposal_adapters.py`.
- **AC-6 Notification kinds (P-04-T26; C16; DEC-605).** Each of the seven kinds fans out once per recipient with walls re-checked, and no template text is committed; facts and pending are read at read time from the subject's owner. Tests: `backend/tests/integration/backfill/test_p04t26_review_notifications.py`, `backend/tests/unit/notifications/test_catalogue.py`.
- **AC-7 C3 services v1 freeze (P-04-T27; DEC-606).** The register marks C3 services v1 frozen by Fri Apr 16, 2027, and removing a field fails the snapshot diff. Tests: `backend/tests/contracts/review_grammar/test_c3_frozen.py`.
- **AC-8 Checkpoints (P-04-T32; ADR-160 clause 9; DEC-85, DEC-804).** Restoring Checkpoint 3 creates Checkpoint 7 and deletes nothing, and approving Checkpoint 6 records one decision that SHL-16 and SHL-10 both show; Current is the newest approved or saved checkpoint, the diff is code-computed, a stale hash is 409 `checkpoint_changed`, and only a person with a reviewer function approves, rejects or restores. Tests: `backend/tests/integration/backfill/test_p04t32_checkpoints.py`.

## 3. Out of scope
Decision cards and generic proposals in the C13 human-gate projection; recommendation reasons; Undo and the effect hold (P-04-T29); the AUD-17, SHL-10, SHL-11 and SHL-12 screens.
