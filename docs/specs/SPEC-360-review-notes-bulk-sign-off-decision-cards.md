---
id: SPEC-360
title: "Review grammar services: review notes, bulk sign-off and decision cards (P-04-T21 to T23)"
status: approved
owner: founder
risk_zone: red
related_adrs: [ADR-005, ADR-031, ADR-050, ADR-160]
related_specs: [SPEC-308, SPEC-313]
created: 2026-10-27
updated: 2026-10-27
---

## 1. Summary
The C3 review-note, bulk sign-off and decision-card routes (`docs/contracts/review-grammar.md` parts 1 and 2) go live behind `review.grammar_api`, on the P-04 F2 to F4 behaviour (`docs/plan/epics/P-04.md` §3) and ADR-160 clauses 4, 6, 8 and 12. Decisions: DEC-500 to DEC-504. Migrations 0210 (sealed note bodies), 0211 (decision card history and analysis requests) and 0212 (the decision verdicts on the human-only list).

## 2. Acceptance criteria
- **AC-1 Review notes (P-04-T21).** Open notes on RA!C14 and RA!C22 block L2 with `open_review_notes` and count 2, and clearing both lets the same reviewer sign. Bodies are sealed and a body read is an access event; lists carry no body; only the raiser withdraws; the agent raises nothing; the assignee (else the target's preparers) gets `review_note_raised`. Tests: `backend/tests/integration/test_p04t21_review_notes.py`.
- **AC-2 Bulk sign-off (P-04-T22, R-SO-7).** Six workpapers with three ineligible return three signed and three excluded with reasons, and a replay with the same key returns the stored result. The same key with another body is 422 `idempotency_key_reused`; reviewers only; a fresh second factor; never the agent; a hidden target is excluded without saying whether it exists. Tests: `backend/tests/integration/test_p04t22_bulk_sign_off.py`.
- **AC-3 Decision cards (P-04-T23).** Only Margaret Okonkwo can decide the Northwind card, a decide without a rationale returns 422 `rationale_required`, and reassessment on $16,861,000 records No change with the $700 difference. The agent raises cards only through its task scope; options are computed by the kind's provider; MFA per kind; a changed reassessment supersedes the card. Tests: `backend/tests/integration/test_p04t23_decision_cards.py`.

## 3. Out of scope
Decision cards in the C13 human-gate projection; recommendation reasons (P-04-T24); the AUD-17, SHL-11 and SHL-12 screens.
