// ENG-04's reads and writes over the generated client (N-02-T34; docs/contracts/c7-envelopes.md §2,
// N-02-T32 additions): the composed letter, a draft edit (PUT with If-Match: a new version, so an
// edit after approval returns the letter to Draft), the partner-approval request and Send, which
// answers the C7 draft SIG-02 opens. Send is a person's click only (INV-1).

import type { ComposerLetterOut, LetterDraftIn, LetterFeesIn } from "@abacus/api-client";
import {
  draftLetterMutation,
  getLetterOptions,
  getLetterQueryKey,
  approveLetterMutation,
  requestApprovalMutation,
  sendLetterMutation,
  withdrawLetterEnvelopeMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useComposedLetter(engagementId: string) {
  return useQuery(getLetterOptions({ path: { engagement_id: engagementId } }));
}

/** The fee terms the letter was composed with, as a draft edit sends them back. */
export function feesIn(letter: ComposerLetterOut): LetterFeesIn {
  const fees = letter.fees;
  if (fees == null) return { basis: "fixed", lines: [] };
  return {
    basis: fees.basis,
    lines: fees.lines,
    installments: fees.installments.map((i) => ({ label: i.label, share_bp: i.share_bp })),
    third_party: fees.third_party.map((t) => ({
      payee: t.payee,
      estimated_cents: t.estimated_cents,
    })),
  };
}

/** A draft edit that changes one clause's state and keeps everything else as composed. */
export function withClause(letter: ComposerLetterOut, key: string, on: boolean): LetterDraftIn {
  return {
    template_version_id: letter.template_version_id ?? "",
    clause_states: {
      ...Object.fromEntries(letter.clauses.map((c) => [c.key, c.state])),
      [key]: on ? "on" : "off",
    },
    variables: Object.fromEntries(
      letter.variables
        .filter((v) => v.source === "override" && v.value != null)
        .map((v) => [v.key, v.value ?? ""]),
    ),
    fees: feesIn(letter),
  };
}

export function useLetterWrites(letter: ComposerLetterOut | undefined) {
  const queryClient = useQueryClient();
  const at = { path: { engagement_id: letter?.engagement_id ?? "" } };
  const ifMatch = { "If-Match": `"${String(letter?.version ?? 0)}"` };
  const put = (next: ComposerLetterOut): void => {
    queryClient.setQueryData(getLetterQueryKey(at), next);
  };
  const draft = useMutation({ ...draftLetterMutation(), onSuccess: put });
  const request = useMutation({ ...requestApprovalMutation(), onSuccess: put });
  const send = useMutation(sendLetterMutation());
  // N-02-T35: the partner's approval (fresh second factor) and the withdrawal of an ended envelope.
  const approve = useMutation({ ...approveLetterMutation(), onSuccess: put });
  const withdraw = useMutation({ ...withdrawLetterEnvelopeMutation(), onSuccess: put });
  return {
    draft: (body: LetterDraftIn) => draft.mutateAsync({ ...at, body, headers: ifMatch }),
    // N-02-T33: the request names the version it asks about, like an edit.
    requestApproval: () => request.mutateAsync({ ...at, headers: ifMatch }),
    send: () => send.mutateAsync(at),
    approve: () => approve.mutateAsync({ ...at, headers: ifMatch }),
    withdraw: () => withdraw.mutateAsync({ ...at, headers: ifMatch }),
    pending:
      draft.isPending ||
      request.isPending ||
      send.isPending ||
      approve.isPending ||
      withdraw.isPending,
  };
}
