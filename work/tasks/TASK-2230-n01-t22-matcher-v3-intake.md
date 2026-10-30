---
id: TASK-2230
title: N-01-T22 evidence.matcher v3 intake mode
spec: SPEC-033  # the matcher; N-01 §6 (the agent card) for mode intake
acceptance_criteria: [AC-7]  # the backlog row's acceptance, quoted under Objective
risk_zone: red
status: in-review
epic: N-01
plan_key: N-01-T22
branch: s17-n01-t22
created: 2026-10-30
updated: 2026-10-30
---

## Objective
`evidence.matcher` v3 adds mode `intake` (N-01 §6): for one intake attachment of a matched client,
propose a classification (`form_family`, `tax_year`, `issuer`, `kind`) and up to three
destinations from that client's own destinations, each backed by quotes code verifies. Mode
`engagement` keeps v2's prompt and output, unchanged. The matcher proposes; filing, ignoring,
holding and superseding stay human (I-AGENT-NEVER).

Acceptance (backlog row): "The direct-route suite passes at the protected thresholds and no code
path lets the agent file, ignore, hold or supersede."

## Plan (red)
- **Flag** `matching.firm_intake` (agents registry, boolean, default off, ≤ 90 days, ADR-089);
  `_flags.py` regenerated.
- **Migration 0431 `inbox_match_intake`** (agents, expand-only, down 0430):
  `inbox_match_runs.engagement_id` and `inbox_file_id` nullable, `inbox_attachment_id` and
  `client_id` added, exactly one source per run (CHECK), an engagement for every inbox-file run;
  `inbox_match_proposals.request_item_id` nullable, `inbox_attachment_id`, `destination_kind`,
  `destination_id` added, a proposal names a request or a destination (CHECK); the app role's
  column grants for the new columns; an index on `(tenant_id, inbox_attachment_id)`. The v2 rows
  and paths are untouched.
- **Spec** `evidence.matcher` v3: prompt `evidence.inbox_match@v3` (protected), input
  `IntakeMatchInput`, output `IntakeMatchOutput`, `max_cost_usd` 0.015, routing below 0.5 hidden
  (kept). `spec.py` gains the two schema names; `_specs.py` regenerated. Mode `engagement` pins
  `evidence.inbox_match@v2` and `MatchOutput` (DEC-1276), so v2's measured behaviour and its
  replay history stay as they are.
- **Output** (`handoff.py`): `IntakeMatchOutput` with `none_fit`, `classification` (form family,
  tax year, issuer, kind; each optional) and up to three proposals over references D1..Dn, each
  with confidence, a one-sentence rationale and page citations with exact quotes.
- **Input builder** (`agents/intake_match.py`): code assembles the attachment's masked pages
  (evidence; never unmasked, no TIN), its file name and channel, and the matched client's
  destinations only (communications' `destinations`, for the relationship partner: open requests
  across non-archived work items, the permanent file and work-item folders), as D1..Dn with
  labels. Destinations in AI-excluded engagements are dropped. When the client holds a
  `tax_return` work item, the context declares its TRI subjects (entity, tax year) so C19's
  `consent_7216` refuses the call without both consents (fail closed, audited, never retried).
- **Gates before a run**: flag on, the attachment matched to a client, the client's relationship
  partner an active member (the run acts on their behalf, walls apply), a real model route,
  masked pages present, at least one destination, the daily cap; the gateway's data boundary
  (opt-in, clearance, stage) as for every agent.
- **Persistence**: an `inbox_match_runs` row for the attachment, proposals with
  `destination_kind`/`destination_id` (and `request_item_id` for a request), the classification
  through evidence (`document_classifications`, `proposed_by_kind = agent`), quotes as v2 document
  citations verified against the masked pages. Unknown references are discarded.
- **Never decides**: the module imports nothing that files, ignores, holds or supersedes; its task
  scope stays `evidence.read`, `inbox_match.run`; a test walks the module's imports and calls.
- **Workflow**: `InboxMatch` patched (`n01-t22-intake`) to run intake mode for an attachment input;
  AttachmentTriage starts it after classification when the attachment's client is known; the v2
  history still replays.
- **Bundle**: INB-02's cards read the latest shown intake proposals as `DestinationCandidate`s.
- **Evals**: the intake section's direct route runs the v3 intake path; the fake route keeps the
  recorded answers (`make evals-match-fast`).
- **Tests**: the matcher never files, ignores, holds or supersedes; TRI refused without consent;
  cross-client containment (only the matched client's destinations reach the context); flag off
  and unmatched attachments start nothing; unknown references discarded; citations verified;
  persistence; spec and prompt registered; workflow replay.
- **Rollback**: flag off stops new runs; the migration is expand-only (its downgrade drops the
  added columns and restores NOT NULL only when no intake rows exist).

## Progress log
- 2026-10-30: plan written. The direct-route run needs a model key and runs in the eval
  environment (`make evals`); not runnable from this machine.
- 2026-10-30: built (DEC-1276). Deviations from the plan: `InboxMatch` is not patched; intake
  runs on its own workflow type (v2 histories untouched). The spec gained `modes` and the gateway
  keys eligibility on (agent, prompt), since one prompt per agent would have refused engagement
  mode. `agent_runs` gained `inbox_attachment_id` and a third engagement-less run kind (0431).
  v2 readers now filter to engagement-mode rows (the gate projector would otherwise have seen
  intake runs). Deferred: v2 citation rows on attachments, INB-02 bundle candidates,
  `ProposalRecorded` for intake runs. Tests: 8 integration (fake model), 4 unit; fast eval green.
