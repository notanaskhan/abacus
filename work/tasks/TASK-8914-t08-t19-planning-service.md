---
id: TASK-8914
title: "T-08-T19: Planning service: rules, calculators, consent filter, raise, project, dismiss"
spec: SPEC-710
acceptance_criteria: [AC-1]  # the backlog row's acceptance, quoted under Objective
risk_zone: amber
status: in-review
branch: s53-t08t19
worktree: /Users/ayushkbhatia/Accrued/abacus-s50
created: 2026-11-23
updated: 2026-11-23
plan_key: T-08-T19
---

## Objective
Row: "Planning service: code screening rules and savings calculators on CPA-reviewed parameter files, section 7216 consent filter (both spouses; non-tax products need other_services_use), screens on return approval and consent completion, portfolio summary, raise on human send, create-project prefill and acceptance, dismiss and restore, TXP-01 memo opportunities and the TXT-03 Add to planning entry." Acceptance: "Daniel's portfolio reads 58 clients, $1.2M and 1 consent-blocked, Ferris is Not screened with no model call, and Feld's savings compute to about 1,810."

## Done
- tax/planning/: calculators.py (DAF bunching, deferral savings, brackets), rules.py (six rules, code rationale), service.py (screens, consent filter, strip, queue, detail, prepare-raise, raise via message.send, create-project prefill, accept on engagement.created, decline, dismiss, restore, manual add, subscribers, narrator slot for T-08-T26)
- tax/compute/parameters/planning/ty2025.yaml (PROTECTED; CPA review pending)
- practice_tools_contract: eleven TAX-15 routes live; TaxPracticeRaiseSheetOut.recipient_contact_ids additive
- tax/api.py: planning subscriptions chained onto filing.acknowledged and envelope.completed; tax_return.approved and engagement.created; planning_conversation template key registered
- engagements: EngagementDraftPayload.source_ref and EngagementCreated.source_ref (additive)
- organisations: entity_type_of, open_consent_envelope, unit_signer_contacts
- communications: template_draft (version in use as editable text)
- errors opportunity_state_invalid, recipient_not_client, planning_template_missing
- docs/contracts/tax-practice.md planning section; DEC-5916
- tests: tests/unit/tax/test_t08t19_planning.py (10 pass), tests/integration/test_t08t19_planning_service.py (end pass)

## Progress log
- `2026-11-23` — Built in full. Human remainders: the tax CPA signs the TY2025 planning parameters (reviewed_by), and the firm loads its Planning conversation template text (database content). The 58-client / 71-opportunity portfolio is T-08-T39's scenario slice; the strip's arithmetic is proven here. Citations on the rationale arrive with T-08-T26's suggestions. End pass: integration test, make generate.
