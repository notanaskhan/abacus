# SHL-10 · Approve agent output

| Field | Value |
|---|---|
| Route and params | Overlay `?ov=approve:<proposalRef>` over any firm route, registered in `routes/firm/approve.tsx` (behind `review.grammar_api`). No route of its own. Artboards: `/components/screens/SHL-10?st=a,b,c,f` |
| Template and host frame | O3 sheet modal 500 · `Wave 0 - Shell.dc.html#shl10` |
| Surface | firm |
| Handoff | `$ACCRUED_HANDOFF_DIR/handoff/screens/SHL-10 Approve agent output/` (README.md, spec.md, revision.md R2; revision wins) |
| Epic and tasks | P-04 · kit P-04-T40 (TASK-2124); a, b, c, f P-04-T41 (TASK-2125); proposals service P-04-T24; adapters P-04-T25; fixtures P-04-T34; d, e, e′, g later P-04 rows; independent AC tests P-04-T44 |
| Manifest status | planned (`routes/manifest/shl.ts`) until the staging walk; built on fixtures |

Code: `src/domain/review/{proposals.ts, useGate.ts}`, `src/screens/SHL-10/{index.tsx, copy.ts, scenarios.ts, SHL-10.test.tsx}`, `src/fixtures/scenarios/SHL-10.ts`.

## States

| Artboard | Viewer (persona) | Clock | Data condition that produces it | Status |
|---|---|---|---|---|
| a | default persona (the handoff names Samuel Ito) | Thu Oct 1, 2026, 9:24 AM CT | `SHL10.a`: the Feld K-1 treatment, 4 rows, totals tie, 3 evidence rows, `pending` | built · fixture (T41) |
| b | same | same | a's proposal opened in edit mode: After cells editable, citation note per edited row, CTA "Approve with edits" | built · fixture (T41) |
| c | same | same | `SHL10.c`: a fifth row with no citation (`unsupported`), approve not in `allowed_actions` | built · fixture (T41) |
| d | raj-malhotra | same | AJE-05 over threshold, routed to Priya Raman | later P-04 row |
| e, e′ | raj-malhotra | same | the within-threshold batch and its approved line with Undo | later P-04 row |
| f | default persona | same | `SHL10.f`: `rejected` by Samuel Ito, reason `needs_client_input`; the reject dialog opens from a's Reject… | built · fixture (T41) |
| g | hannah-leclerc | same | `SHL10.g`: part of a set; the link row opens SHL-19 | later P-04 row |

Loading: "Loading the proposal". Error: "This proposal isn't available." Not-allowed: Approve is a `HumanAction`, so it never renders for the agent, a policy or the system, and only when `allowed_actions` holds `proposal.approve` and the proposal is `pending`.

## API
| Read or write | Endpoint | Shape | Matrix action |
|---|---|---|---|
| read | `GET /v1/proposals/{ref}` | `AgentProposalOut` | `proposal.read` |
| write | `POST /v1/proposals/{proposal_id}/approve` (Idempotency-Key) | `ApproveProposalIn {seen_version, edits?}`; 409 `proposal_changed`, 422 `uncited_change` | `proposal.approve` (agent deny) |
| write | `POST /v1/proposals/{proposal_id}/reject` (Idempotency-Key) | `RejectProposalIn {seen_version, reason_code, note}` | `proposal.reject` |
| write | `POST /v1/proposals/{proposal_id}/follow-up` (Idempotency-Key) | `FollowUpIn {text}` | `proposal.follow_up` |
| write | `POST /v1/proposals/{proposal_id}/undo` (Idempotency-Key) | `UndoProposalIn {decision_id}`: the Undo toast's compensating command | `proposal.undo` |

## Open
- Diff-row lighting (hover lights the target field in the underlay) needs a typed locator: `AgentProposalOut` carries no target record, so no `MatchId` can be minted (INV-2). Waits on the projection adding `target_type`/`target_id` (P-04-T24).
- The footer line reads "Approving creates a checkpoint and logs to Activity." (the handoff's "Checkpoint 6" is that frame's number; the projection does not yet carry the next checkpoint's sequence).
