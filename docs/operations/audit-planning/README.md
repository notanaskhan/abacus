# Audit planning runbook (A-04-T39)

For the planning screens AUD-04, AUD-05, AUD-07, AUD-08, AUD-09 and AUD-10. Not yet rehearsed on
staging: rehearse once before a real firm uses them.

## A section draft is stuck or failed
1. Open the run from the rail row (`Failed — see run`). AUD-09 d quotes the run's reason verbatim.
2. `capacity_timeout`: the run never got a slot. Retry from the row when load falls.
3. `gateway_error`: check the provider-terms entry and the kill switch before retrying.
4. A run never reopens on its own. Retry creates a new run; the failed one stays on the record.

## Pack error
A methodology pack that fails validation stops the run before any model call (AC6.1), at no cost. Fix
it in Knowledge (KNW-03) and publish a new version; a draft reads the published version only.

## Kill switch
`model_route_block` stops agent calls for a route or a firm. Screens keep working by code, and rows
show manual entry. Turn it off only after the cause is understood, and record why.

## Card supersession
Reassessing materiality supersedes the open card. The partner decides the current card; a decision on
a superseded version answers 409 with the current version.

## G4 reopens
An edit to a register row after approval reopens G4. The register needs routing and the partner's
approval again; nothing here overrides it.

## Consumer notes
- A-05: `register_mode_mapping`, `register_sign_off_guard` (`assurance.api`) for a mode and a hold.
- A-06: `review.api.register_reviewable`, `register_decision_kind` for a target and a card.
- A-07: `assurance.gates.register_gate_provider` for G6 to G9.
- A-09: the C8 reads (`adjustments.api.entries_of`).
- K-03: `methodology.api` versions; a section's steps cite them.
- P-10: a section draft's run moves to run and step records with no behaviour change.
