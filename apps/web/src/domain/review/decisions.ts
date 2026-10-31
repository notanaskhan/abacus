// SHL-11's reads and writes over the generated client (P-04-T50; docs/contracts/review-grammar.md):
// one decision card's C3 projection, and the reserved person's Decide (option, factors, rationale,
// the version seen), Notify and Request more analysis. Nothing here decides for anyone: the
// screen calls `decide` only from the Decide HumanAction, and the server refuses everyone but the
// reserved person (INV-1).

import type { DecisionCardOut } from "@abacus/api-client";
import {
  decisionCardAnalysisRequestMutation,
  decisionCardDecideMutation,
  decisionCardNotifyMutation,
  decisionCardOptions,
  decisionCardQueryKey,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useDecisionCard(cardId: string) {
  return useQuery(decisionCardOptions({ path: { card_id: cardId } }));
}

export interface DecisionWrites {
  decide: (
    optionKey: string,
    factors: readonly string[],
    rationale: string,
  ) => Promise<DecisionCardOut>;
  notify: () => Promise<unknown>;
  requestAnalysis: (text: string) => Promise<unknown>;
}

export function useDecisionWrites(card: DecisionCardOut | undefined): DecisionWrites {
  const queryClient = useQueryClient();
  const cardId = card?.card.id ?? "";
  const path = { card_id: cardId };
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: decisionCardQueryKey({ path }) });
  };
  const decide = useMutation({ ...decisionCardDecideMutation(), onSuccess: refresh });
  const notify = useMutation({ ...decisionCardNotifyMutation(), onSuccess: refresh });
  const analysis = useMutation({ ...decisionCardAnalysisRequestMutation(), onSuccess: refresh });
  return {
    decide: (optionKey, factors, rationale) =>
      decide.mutateAsync({
        path,
        body: {
          option_key: optionKey,
          factors: [...factors],
          rationale,
          seen_version: card?.card.version_no ?? 0,
        },
      }),
    notify: () => notify.mutateAsync({ path }),
    requestAnalysis: (text) => analysis.mutateAsync({ path, body: { text } }),
  };
}
