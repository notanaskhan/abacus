// SHL-12's reads and write over the generated client (P-04-T48; docs/contracts/review-grammar.md):
// the target's ladder, the viewer's eligibility at one level (checks, levels allowed, statement),
// and the person's sign-off. The write carries the content hash the person saw (409
// `content_changed` when the target changed since) and the statement version they read. Nothing
// here signs for anyone: the screen calls `sign` only from a HumanAction (INV-1).

import type {
  BulkSignOffOut,
  SignOffEligibilityOut,
  SignOffOut,
} from "@abacus/api-client";
import {
  signOffEligibilityOptions,
  signOffEligibilityQueryKey,
  signOffLadderOptions,
  signOffLadderQueryKey,
  signOffBulkMutation,
  signOffMutation,
} from "@abacus/api-client/query";
import { useMutation, useQueries, useQuery, useQueryClient } from "@tanstack/react-query";

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

/** SHL-12 f (P-04-T49): each picked target's eligibility at one level, in order. */
export function useBulkEligibility(targets: readonly SignOffTarget[], level: SignOffLevel) {
  return useQueries({
    queries: targets.map((t) =>
      signOffEligibilityOptions({ query: { target_type: t.type, target_id: t.id, level } }),
    ),
  });
}

/** SHL-12 f: sign the eligible targets at one level in one request (R-SO-7). Each item is decided
 * on its own by the server; the key makes a retried click return the same answer. Called only
 * from the sheet's HumanAction (INV-1). */
export function useBulkSignOffWrite(): (
  eligible: readonly SignOffEligibilityOut[],
  key: string,
) => Promise<BulkSignOffOut> {
  const queryClient = useQueryClient();
  const bulk = useMutation({
    ...signOffBulkMutation(),
    onSuccess: () => {
      // Every ladder and eligibility read may have moved (one per signed target).
      void queryClient.invalidateQueries({ queryKey: [{ _id: "signOffLadder" }] });
      void queryClient.invalidateQueries({ queryKey: [{ _id: "signOffEligibility" }] });
    },
  });
  return (eligible, key) => {
    const first = eligible[0];
    if (first === undefined) return Promise.reject(new Error("nothing_to_sign"));
    return bulk.mutateAsync({
      headers: { "Idempotency-Key": key },
      body: {
        level: first.level,
        statement_version: first.statement.version,
        targets: eligible.map((e) => ({
          target_type: e.target.target_type,
          target_id: e.target.target_id,
          seen_hash: e.target.content_hash,
        })),
      },
    });
  };
}
