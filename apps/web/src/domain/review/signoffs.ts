// SHL-12's reads and write over the generated client (P-04-T48; docs/contracts/review-grammar.md):
// the target's ladder, the viewer's eligibility at one level (checks, levels allowed, statement),
// and the person's sign-off. The write carries the content hash the person saw (409
// `content_changed` when the target changed since) and the statement version they read. Nothing
// here signs for anyone: the screen calls `sign` only from a HumanAction (INV-1).

import type { SignOffEligibilityOut, SignOffOut } from "@abacus/api-client";
import {
  signOffEligibilityOptions,
  signOffEligibilityQueryKey,
  signOffLadderOptions,
  signOffLadderQueryKey,
  signOffMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type SignOffLevel = SignOffEligibilityOut["level"];

/** The ladder's levels, L1 to L5. */
export const SIGN_OFF_LEVELS: readonly SignOffLevel[] = [
  "L1_preparer",
  "L2_reviewer",
  "L3_manager",
  "L4_partner",
  "L5_eqr",
];

/** `?ov=signoff:<type>:<id>:L2` names a level by its short code; the long code passes as is. */
export function levelOf(arg: string | undefined): SignOffLevel | undefined {
  if (arg === undefined) return undefined;
  return SIGN_OFF_LEVELS.find((l) => l === arg || l.startsWith(`${arg}_`));
}

export interface SignOffTarget {
  type: string;
  id: string;
}

export function useSignOffLadder(target: SignOffTarget) {
  return useQuery(
    signOffLadderOptions({ query: { target_type: target.type, target_id: target.id } }),
  );
}

export function useSignOffEligibility(target: SignOffTarget, level: SignOffLevel) {
  return useQuery(
    signOffEligibilityOptions({
      query: { target_type: target.type, target_id: target.id, level },
    }),
  );
}

/** Sign at the eligibility's level with the hash and statement the person saw. */
export function useSignOffWrite(
  eligibility: SignOffEligibilityOut | undefined,
): (kind: "ladder" | "final_approval") => Promise<SignOffOut> {
  const queryClient = useQueryClient();
  const sign = useMutation({
    ...signOffMutation(),
    onSuccess: () => {
      if (eligibility === undefined) return;
      const query = {
        target_type: eligibility.target.target_type,
        target_id: eligibility.target.target_id,
      };
      void queryClient.invalidateQueries({ queryKey: signOffLadderQueryKey({ query }) });
      void queryClient.invalidateQueries({
        queryKey: signOffEligibilityQueryKey({ query: { ...query, level: eligibility.level } }),
      });
    },
  });
  return (kind) => {
    if (eligibility === undefined) return Promise.reject(new Error("not_loaded"));
    return sign.mutateAsync({
      body: {
        target_type: eligibility.target.target_type,
        target_id: eligibility.target.target_id,
        level: eligibility.level,
        kind,
        seen_hash: eligibility.target.content_hash,
        statement_version: eligibility.statement.version,
      },
    });
  };
}
