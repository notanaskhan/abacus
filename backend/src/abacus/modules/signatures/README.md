# signatures

Zone: red. Epic N-02 (Envelopes and e-signature). Contract: C7 v1.1, frozen
(`docs/contracts/c7-envelopes.md`; N-02-T45). Provider: DocuSeal (ADR-342; `docusign` stays
readable on drafts made before it); record mode needs no provider.

Owns: envelopes, their documents, signers and events, signing sessions, signature evidence
(packages, signed images, the legible reproduction), envelope policies, the status poll and the
DocuSeal webhook. Every write is a person's except a draft (`envelope.draft`, agent draft-only and
unreachable in 2027) and the system-only supersede marker; the database backs each rule (INV-1).

## Files

| File | What |
|---|---|
| `contract.py` | C7 models and routes: `/v1/envelopes*`, `/v1/envelope-policies*`, `/v1/portal/envelopes*` |
| `hub.py` | SIG-01's read models and the drawer's actions (list, summary, drawer, void, reveal IP, evidence download) |
| `builder.py` | SIG-02: drafts, edits, checks, Send (an approval grant) and Undo |
| `sources.py` | the envelope-source registry and the G3 letter gate (`engagement_letter`) |
| `consumers.py` | v1.1 for T-01 and T-02: contracted sources, `supersede_for_amount_change`, `extend_retention`, `envelope_summaries_for`, the e-file gate |
| `imports.py` | record-mode import and staged files (scanned before storage) |
| `provider.py`, `docuseal.py`, `docuseal_firm.py` | the `EsignProvider` port, the DocuSeal adapter (W7) and which install a firm's envelope goes through |
| `workflows.py`, `activities.py` | `EnvelopeWorkflow` v1: send after the grant is consumed, completion, evidence |
| `status_poll.py`, `webhook.py`, `webhook_routes.py` | provider truth by polling; the webhook only hints a poll (ADR-152 amendment) |
| `fallback.py` | envelope policies (stricter-only against the floor) and the handwritten fallback (DF-11) |
| `portal.py`, `signer_facts.py` | POR-06's signing for the named contact; the signer's MFA floor and Sign to-do |
| `integrity.py` | the evidence package's retention types, legible page and nightly re-hash (N-02-T38) |
| `reminders.py`, `events.py`, `audit_targets.py`, `registry.py` | reminders, outbox events (identifiers only), audit owners, tables |

## Interface (`api.py`)

- `register_envelope_source(EnvelopeSource(kind, documents, signers, retention_record_type, gate,
  checks, completed_label, draft))`: a source registers once at import; `consent_set` and
  `tax_return` must provide `draft` (v1.1). See `.claude/skills/backend-module` "Registering an
  envelope source and a gate".
- `envelope_summary_for(ctx, source_kind, source_id)`, `envelope_summaries_for(ctx, work_item_ids)`,
  `envelope_gate_facts(ctx, gate_kind, target_ref)` (G3, `efile_authorization`).
- `supersede_for_amount_change(tenant, envelope_id, binding_id)` (system only),
  `extend_retention(tenant, envelope_id, until)` (forward only).
- Outbox: `envelope.send_approved`, `envelope.completed`, `envelope.declined`,
  `envelope.expired`, `envelope.superseded`, `envelope.signer_signed`,
  `envelope.signer_verification_failed`.

## Flags and switches

`signatures.envelopes` (hub, import, portal reads), `signatures.esign_provider` (sending through
DocuSeal; off: record mode stays), `signatures.kba_8879`, `engagements.letter_composer`. The W7
capability `esignature_envelope_send` is enabled in `docs/architecture/write-capabilities.yaml`
(DEC-1280); a firm sends only with its switch on and a connected install.

## Runbooks

RB-18 (e-signature or KBA vendor outage: record mode and the wet-signature path).
