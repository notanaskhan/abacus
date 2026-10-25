// The new-engagement wizard (P-07 §5, L3; ENG-03; docs/contracts/engagements-v2.md): the type
// catalogue, the draft (autosave with `seen_version`), discard, start acceptance and create, over
// the generated client only. The catalogue never holds `single_audit` (D10); the server checks
// the type code. Create is a person's act with an Idempotency-Key; the agent never creates.

import type { EngagementDraftOut, EngagementDraftPatchIn } from "@abacus/api-client";
import {
  createEngagementFromDraftMutation,
  discardEngagementDraftMutation,
  engagementTypesOptions,
  getEngagementDraftOptions,
  getEngagementDraftQueryKey,
  startAcceptanceFromDraftMutation,
  updateEngagementDraftMutation,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useEngagementTypes() {
  return useQuery({ ...engagementTypesOptions(), retry: false });
}

export function useDraft(draftId: string) {
  return useQuery({ ...getEngagementDraftOptions({ path: { draft_id: draftId } }), retry: false });
}

export function useDraftWrites(draftId: string) {
  const queryClient = useQueryClient();
  const key = getEngagementDraftQueryKey({ path: { draft_id: draftId } });
  const store = (draft: EngagementDraftOut): void => {
    queryClient.setQueryData(key, draft);
  };
  const patch = useMutation({ ...updateEngagementDraftMutation(), onSuccess: store });
  const discard = useMutation({ ...discardEngagementDraftMutation() });
  const accept = useMutation({ ...startAcceptanceFromDraftMutation() });
  const create = useMutation({ ...createEngagementFromDraftMutation() });
  return {
    save: (draft: EngagementDraftOut, change: Omit<EngagementDraftPatchIn, "seen_version">) =>
      patch.mutateAsync({
        path: { draft_id: draftId },
        body: { ...change, seen_version: draft.version },
      }),
    discard: () => discard.mutateAsync({ path: { draft_id: draftId } }),
    startAcceptance: () => accept.mutateAsync({ path: { draft_id: draftId } }),
    /** `confirmDuplicate`: "Create anyway" after a 409 `possible_duplicate`. */
    create: (confirmDuplicate = false) =>
      create.mutateAsync({
        path: { draft_id: draftId },
        body: confirmDuplicate ? { confirm_duplicate: true } : {},
        headers: { "Idempotency-Key": globalThis.crypto.randomUUID() },
      }),
    saving: patch.isPending,
    creating: create.isPending,
  };
}

/** ENG-03 e's §7216 consents card, fixture-only until C19 (T-01) serves consents (DEC-345): the
 * route never passes one, so production draws no card; the gallery passes the artboard's. */
export interface ConsentPreview {
  /** "Use · AI disclosure (2 consents) · 1 of 2 signed (Morgan ✓ · Kai ○)": seed data. */
  summary: string;
  /** The household's family name, for the helper ("Agents cannot read Ferris return …"). */
  family: string;
}
