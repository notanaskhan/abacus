// The engagement record (P-07 §5, L3; docs/contracts/engagements-v2.md): ENG-02's reads and the
// interim recorded letter over the generated client only. A walled or unknown engagement answers
// 404 (INV-3). The recorded letter is a person's act; its 409s (`gate_unmet`,
// `letter_before_acceptance`, `engagement_archived`) are the server's, and the screen says them.

import type {
  EngagementGateOut,
  EngagementRecordOut,
  EngagementRailRowOut,
} from "@abacus/api-client";
import {
  engagementRecordOptions,
  engagementRecordQueryKey,
  recordEngagementLetterMutation,
  teamOptions,
  workItemsOptions,
  workItemsQueryKey,
} from "@abacus/api-client/query";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export function useEngagementRecord(engagementId: string) {
  return useQuery({
    ...engagementRecordOptions({ path: { engagement_id: engagementId } }),
    retry: false,
  });
}

export function useEngagementWorkItems(engagementId: string, enabled = true) {
  return useQuery({
    ...workItemsOptions({ path: { engagement_id: engagementId } }),
    retry: false,
    enabled,
  });
}

/** `GET /v1/engagements/{id}/team`: the Team tab host's roster (ENG-05 manages it later). */
export function useEngagementTeam(engagementId: string, enabled = true) {
  return useQuery({
    ...teamOptions({ path: { engagement_id: engagementId } }),
    retry: false,
    enabled,
  });
}

/** Record a signed letter; on success the record and its work items are read again. */
export function useRecordLetter(engagementId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    ...recordEngagementLetterMutation(),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: engagementRecordQueryKey({ path: { engagement_id: engagementId } }),
      });
      await queryClient.invalidateQueries({
        queryKey: workItemsQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
}

export function bandRows(
  record: EngagementRecordOut,
  band: "details" | "review_delivery" | "client_portal",
): readonly EngagementRailRowOut[] {
  return record.bands.find((b) => b.band === band)?.rows ?? [];
}

export function allows(record: EngagementRecordOut | undefined, action: string): boolean {
  return (record?.allowed_actions ?? []).includes(action);
}

export function gateOf(
  record: EngagementRecordOut | undefined,
  gate: EngagementGateOut["gate"],
): EngagementGateOut | undefined {
  return record?.gates.find((g) => g.gate === gate);
}

/** Work items open only once the letter is signed (G3): an accepted engagement waits on it. */
export function waitsOnLetter(record: EngagementRecordOut): boolean {
  return record.status === "accepted" && record.letter.status === "not_signed";
}

/** The server's 409 code, when the error is one. */
export function conflictOf(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : null;
}
