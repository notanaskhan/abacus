// SHL-10's reads and writes over the generated client (P-04-T41; docs/contracts/review-grammar.md):
// one proposal's C3 projection, and the person's approve (with edits), reject with a reason,
// follow-up and Undo. Every write carries the version the person saw (409 `proposal_changed` when
// the agent revised it since) and an Idempotency-Key. Nothing here approves for anyone: the
// screen calls these only from a HumanAction or the reject dialog (INV-1).

import type { AgentProposalOut, ProposalEditIn, RejectProposalIn } from "@abacus/api-client";
import {
  agentProposalOptions,
  agentProposalQueryKey,
  proposalApproveMutation,
  proposalFollowUpMutation,
  proposalRejectMutation,
  proposalUndoMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type RejectReason = RejectProposalIn["reason_code"];

/** The reason picker's codes, in the handoff's order (SHL-10 f). */
export const REJECT_REASONS: readonly RejectReason[] = [
  "wrong_treatment",
  "unsupported_value",
  "needs_client_input",
  "other",
];

function idempotencyKey(): string {
  return globalThis.crypto.randomUUID();
}

export function useProposal(ref: string) {
  return useQuery(agentProposalOptions({ path: { ref } }));
}

export interface ProposalWrites {
  approve: (edits?: ProposalEditIn[]) => Promise<AgentProposalOut>;
  reject: (reason: RejectReason, note: string | null) => Promise<AgentProposalOut>;
  followUp: (text: string) => Promise<unknown>;
  undo: (decisionId: string) => Promise<unknown>;
}

export function useProposalWrites(proposal: AgentProposalOut | undefined): ProposalWrites {
  const queryClient = useQueryClient();
  const ref = proposal?.ref ?? "";
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: agentProposalQueryKey({ path: { ref } }) });
  };
  const approve = useMutation({ ...proposalApproveMutation(), onSuccess: refresh });
  const reject = useMutation({ ...proposalRejectMutation(), onSuccess: refresh });
  const followUp = useMutation({ ...proposalFollowUpMutation(), onSuccess: refresh });
  const undo = useMutation({ ...proposalUndoMutation(), onSuccess: refresh });
  const seen = proposal?.version ?? 0;
  const at = { path: { proposal_id: ref } };
  return {
    approve: (edits) =>
      approve.mutateAsync({
        ...at,
        body:
          edits === undefined || edits.length === 0
            ? { seen_version: seen }
            : { seen_version: seen, edits },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    reject: (reason, note) =>
      reject.mutateAsync({
        ...at,
        body: { seen_version: seen, reason_code: reason, note },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    followUp: (text) =>
      followUp.mutateAsync({
        ...at,
        body: { text },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
    undo: (decisionId) =>
      undo.mutateAsync({
        ...at,
        body: { decision_id: decisionId },
        headers: { "Idempotency-Key": idempotencyKey() },
      }),
  };
}
