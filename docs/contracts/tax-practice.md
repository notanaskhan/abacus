# Tax practice tools v1 (TP-1) — two-year, standards runs, planning, amendments and AARs

| Field | Value |
|---|---|
| Owner | tax (T-08; SPEC-710) |
| Status | stub (T-08-T04, 2026-11-18; DEC-5603); v1 S54 |
| Code | `backend/src/abacus/modules/tax/practice_tools_contract.py` (`practice_tools_router`) |
| Flags | `tax.two_year`, `tax.standards_runs`, `tax.planning`, `tax.amendments` (default off; off: 404; on: 501) |
| Consumers | TAX-10, TAX-14, TAX-15, TAX-16; N-03 (raise); T-09 (accepted opportunities) |

Every figure, explanation, rationale and name is TRI: agents read it only with §7216 use and ai_disclosure in force (C19). Client 404 → flag 404 → human-only 403 → 501. Δ, Δ%, check differences, savings and amendment changes are code; tax and the imputed underpayment are engine imports or a labelled shadow tie-out (DEC-77).

| Method and path | Action | Notes |
|---|---|---|
| `GET /v1/tax-returns/{id}/two-year?filter=all\|over_threshold` | `tax_return.read` | lines, threshold source and version, tally |
| `POST …/two-year:explain` | `two_year.explain` | 409 `consent_7216_missing` |
| `PUT …/two-year/lines/{line_key}/explanation` · `POST …/explanation:accept` | `variance_explanation.edit` · `variance_explanation.accept` | accept pins `values_hash`; 409 `explanation_stale` |
| `GET …/two-year.xlsx` | `export.create` | deterministic |
| `GET /v1/standards-runs` · `/{rid}` · `/{rid}/items/{work_item_id}/checks` | `standards_run.read` | tiles, progress, checks (`1065-v4/C-17`) |
| `POST /v1/standards-runs` · `POST …/{rid}:rerun` | `standards_run.start` | model-free; 422 `check_code_unknown` on import |
| `POST /v1/standards-check-results/{id}:confirm` | `standards_check.confirm` | manual items, human-only |
| `GET /v1/planning-summary` · `/planning-opportunities` · `/{oid}` | `planning.read` | strip, queue, detail |
| `POST …/{oid}:prepare-raise` · `:raise` | `planning.raise` | database template (P-25 not accepted); a person's send |
| `POST …/{oid}:create-project` | `planning.create_project` | ENG-03 prefill only |
| `POST …/{oid}:decline` · `:dismiss` · `:restore` · `POST /v1/planning-opportunities` | `planning.dismiss` · `planning.create` | reason required; insert-only events |
| `POST /v1/tax-returns/{id}/amendments` · `GET /v1/amendments/{aid}?jurisdiction=` · `PUT …/explanation` · `POST …/proposals:draft` | `amendment.create` · `tax_return.read` · `amendment.edit` | 409 `return_accepted` writes to the original |
| `POST /v1/tax-returns/{id}/aars` · `GET /v1/aars/{xid}` · `POST …/recommendation:draft` | `aar.create` · `tax_return.read` | the election is the signer's `decision.decide` (409 `not_bba_signer`) |

**Examples (foot):** AGI 598,030 = 268,400 + 6,910 + 14,820 + 307,900; 8 flagged; refund due 2,708 = 41,000 − 37,678 − 614; IL (495) = 11,999 − 12,494; 14,800 = 40,000 × 37%.

## Planning, live (T-08-T19, DEC-5916)

The planning routes answer from `tax/planning/service.py`; the flag still gates them (off: 404).

- **Screens** are the system's, on `tax_return.approved`, `filing.acknowledged` (accepted) and `envelope.completed` (`consent_set`), only with `tax.planning` on. Code rules (`tax/planning/rules.py`: `daf_bunching`, `solo_401k`, `dependent_care_fsa`, `qcd`, `roth_conversion`, `reasonable_compensation`) run over the approved engine summary and the CPA-reviewed `tax/compute/parameters/planning/ty<year>.yaml`; estimates and their basis (calculator, input lines by key, parameter version) are code's. One opportunity per (return, rule); a re-screen refreshes only Open and Not screened rows.
- **Consent filter.** A tax service to the same client needs no separate consent (§301.7216-2(h)). Without `use` and `ai_disclosure` in force for the filing unit (both spouses of a joint unit) the row is `not_screened`: no model call, no raise, `consent_envelope_id` names the open consent envelope. A `non_tax_product` row also needs `other_services_use` in force or it is never written.
- **Raise** (`prepare-raise` then `raise`): the owner or the relationship partner; the sheet is the firm's `planning_conversation` template filled by code (`draft_from_agent` is always false until P-25), `recipient_contact_ids` additive (the filing unit's taxpayers). The send is `message.send` (portal, the outbound scope check), one message per recipient; Raised only after it. 409 `planning_template_missing` without a version; 422 `recipient_not_client`; 409 `opportunity_state_invalid` for a move the status does not allow.
- **Create project** answers the ENG-03 prefill with `source_ref = planning_opportunity:<id>`; ENG-03 keeps it on the draft payload (`EngagementDraftPayload.source_ref`, additive) and `engagement.created` carries it (additive); the opportunity becomes Accepted with `project_engagement_id` when the engagement is the same client's.
- **Decline, dismiss, restore** write one insert-only `planning_opportunity_events` row each; dismiss needs its reason; restore returns `previous_status`.
- **Manual add** (`POST /v1/planning-opportunities`): Open, `rule_key = manual.<source>.<hash of source_ref>`, no estimate, no model; the same source item answers its existing row.
- **Strip** (`planning-summary`): live = Open, Raised, Accepted, Not screened; `clients_to_contact` = clients with an Open, Raised or Not screened row; `est_savings` = Σ Open and Raised estimates; `consent_blocked` = clients with a Not screened row; `talking_points` = drafted when any rationale is the agent's, else template.

## The 1065 v4 check library (T-08-T23, DEC-5918)

`tax/standards_checks.py` registers to the standards run's slot: the eight named checks (C-04 `check.k1_count_item_i`, C-09 `check.schedule_k_k1_sum`, C-12 `check.m3_required`, C-15 `check.tb_balanced_mapped`, C-17 `check.m2_line9_schedule_l21`, C-22 `check.partnership_representative`, C-31 `check.section_754_documented`, C-38 `check.ptet_recorded`) and twenty `presence.*` data-presence checks, beside T-08-T14's four `tie_out.*`. Each is a pure function of one return's facts snapshot gathered by code; an exception names the reference it links or raises under (C-17 `tie_out:item_l_m2`, C-31 `decision:section_754`, a presence check `presence:<what>`). The firm's checklist (database content, K-02 import) binds items to these codes; items with no code stay manual. No model is called.
