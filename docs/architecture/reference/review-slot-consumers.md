# Review-grammar slot consumers (P-04-T61)

Each epic that puts work in front of a reviewer registers with `review.api` at import of its
module's `api.py`. Never write sign-offs, decisions or gate rows yourself. This note names, per
consuming epic, the slot it registers and its first reviewable or decision kind. Slots are
defined in `backend/src/abacus/modules/review/slots.py`; the how-to is the "Registering with the
review grammar" section of `.claude/skills/backend-module/SKILL.md`.

| Epic | Slot(s) | First kind | Where |
|---|---|---|---|
| A-04 Risk & planning | `register_decision_kind`; `register_gate_kind` | `planning_materiality` (then `materiality_reassessment`, `significant_risk`); gate `fraud_minutes_approval` | `assurance/materiality.py`, `assurance/risks.py`, `assurance/api.py` |
| A-05 Testing (EBP, sampling) | `register_reviewable` + `register_reviewable_facts`; `register_gate_kind` | reviewable `attribute_test`; gate `sample_set_approval` | `workpapers/api.py`, `sampling/api.py` |
| A-06 Completion | `register_decision_kind`; `register_reviewable` + facts; G5 through `replace_gate_provider` | `deficiency_severity` (then `sum_conclusion`); reviewables `sum_schedule`, `fs_package` | `assurance/completion_decisions.py`, `assurance/review_targets.py`, `reporting/review_targets.py`, `assurance/gates.py` |
| A-07 EQR, release & archive | `register_archive_lock` | none registered yet: the archive lock (P-04-T59, DEC-2065) is its first; A-07 registers the check when its archive task lands | `review/api.py` exports the slot |
| T-01 Tax compliance rails | `register_gate_kind` | `ready_to_transmit` (then `import_pending_approval`) | `tax/engine_sync.py` |
| T-02 Extension-season kit | `register_decision_kind` (planned) | none registered yet: the first is the extension decision on `filing_extension` (SPEC-643); until then T-02 reads gates only | — |
| T-04 Return workspace | `register_gate_kind`; `register_reviewable` (planned) | gate `tax_final_approval` | `tax/approval.py` |
| I-01 Home & approvals | reads only: `GET /v1/human-gates`, `review.api.open_notes`; `register_suggestion_owner` through `agents` | no kind of its own; every gate kind above surfaces on HOME-02 | `review/gates.py`, `agents/gates.py` |
| P-09 Agent transparency | `register_field_citations` | field citations for agent-drafted fields (`agents/field_citations.py`) | `agents/field_citations.py` |
| P-10 Agent runtime v2 | `register_checkpoint_proposal_hooks`; `register_suggestion_owner` | checkpoint proposals (`agents/proposals.py`) | `agents/proposals.py`, `agents/gates.py` |

Other registrations on main (not one of the consuming epics above): `trial_balance` and
`mapping_set` reviewables (A-02, A-03), `workpaper` reviewable and the field owners
`TB_FIELD_OWNER` and `CELL_OWNER` (W-xx), envelope gates `envelope_send` and
`envelope_countersign` (N-02).

Rules every consumer keeps:

1. **Facts are a hash of what the sign-off approves**, nothing else. A hash that moves when the
   content did not causes a stale storm (runbook `docs/runbooks/review-grammar.md` §3).
2. **A decision kind names who decides** (`reserved_role`) and its human-only action (migration
   0661 for A-06); an agent context never decides (ADR-005).
3. **A gate kind answers from the owner's records**, so `reproject_human_gates` can rebuild it.
4. **Stale sources:** add your change event to `STALE_SOURCES` in `review/stale.py` with the
   payload key that names the target.
