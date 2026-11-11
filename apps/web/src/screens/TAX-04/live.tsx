// T-04-T29 (TASK-6828): TAX-04 Review on a live build. The review tree at the viewer's level
// (`GET /v1/tax/returns/{id}/review-tree`, "Review n" from the server), Approve at the viewer's
// level (`POST …/document-approvals` with the version the person saw) and Unapprove of an
// approval made here (`POST /v1/tax/document-approvals/{id}/reverse`, a reversing row; the
// approval's toast offers the same as Undo for 10 s, DEC-24). A
// mismatch disables Approve with the handoff's helper; every refusal shows its words
// (`blockerWords`). "Request final approval…" is SHL-12 h's; a refusal names its blockers.
import {
  documentApprovalMutation,
  documentApprovalReverseMutation,
  reviewTreeOptions,
  workspaceOptions,
} from "@abacus/api-client/query";
import type { DocumentApprovalOut, ReviewDocumentOut } from "@abacus/api-client";
import { Button, EmptyState, Pill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { BLOCKER_COPY, blockerWords, RETURN_LIVE_KEYS, useReturnLive } from "./live-core";

export const REVIEW_LIVE_COPY = {
  loading: "Loading documents…",
  empty: "No documents to review at your level.",
  approve: "Approve",
  unapprove: "Unapprove",
  approved: (n: number) => `✓ ${String(n)}`,
  approvedToast: "Document approved",
  mismatch: "Mismatch",
  unapproved: "Unapproved",
  review: (n: number) => `Review ${String(n)}`,
} as const;

export interface ReviewLiveProps {
  returnId: string;
  engagementId: string | undefined;
}

export function ReviewLive({ returnId, engagementId }: ReviewLiveProps): JSX.Element {
  const interval = useReturnLive(engagementId);
  const queryClient = useQueryClient();
  const summary = useQuery({
    ...workspaceOptions({ path: { return_id: returnId } }),
    refetchInterval: interval,
  });
  const level = summary.data?.viewer_level ?? undefined;
  const tree = useQuery({
    ...reviewTreeOptions({
      path: { return_id: returnId },
      ...(level === undefined ? {} : { query: { level } }),
    }),
    refetchInterval: interval,
  });
  const [mine, setMine] = useState<Record<string, DocumentApprovalOut>>({});
  const [refusal, setRefusal] = useState<{ doc: string; words: string[] } | null>(null);
  const refresh = (): void => {
    for (const queryKey of RETURN_LIVE_KEYS) void queryClient.invalidateQueries({ queryKey });
  };
  const approve = useMutation({ ...documentApprovalMutation(), onSettled: refresh });
  const reverse = useMutation({ ...documentApprovalReverseMutation(), onSettled: refresh });
  const canApprove = summary.data?.allowed_actions.includes("document.approve") === true;

  if (tree.isPending) {
    return (
      <div data-screen="TAX-04" data-live aria-busy="true" className="p-[16px] text-ink-3">
        {REVIEW_LIVE_COPY.loading}
      </div>
    );
  }
  const items = tree.data?.items ?? [];
  if (items.length === 0) {
    return (
      <div data-screen="TAX-04" data-live>
        <EmptyState title={REVIEW_LIVE_COPY.empty} />
      </div>
    );
  }
  const onUnapprove = async (doc: ReviewDocumentOut, made: DocumentApprovalOut): Promise<void> => {
    setRefusal(null);
    try {
      await reverse.mutateAsync({ path: { approval_id: made.id }, body: {} });
      setMine((m) =>
        Object.fromEntries(Object.entries(m).filter(([key]) => key !== doc.evidence_version_id)),
      );
    } catch (error) {
      setRefusal({ doc: doc.evidence_version_id, words: blockerWords(error) });
    }
  };
  const onApprove = async (doc: ReviewDocumentOut): Promise<void> => {
    if (level === undefined) return;
    setRefusal(null);
    try {
      const made = await approve.mutateAsync({
        path: { return_id: returnId },
        body: {
          evidence_version_id: doc.evidence_version_id,
          level,
          seen_version: doc.version,
        },
      });
      setMine((m) => ({ ...m, [doc.evidence_version_id]: made }));
      // DEC-24, DEC-4318: the approval is undoable for 10 s; Undo is the reversal route.
      toast.undoable({
        text: REVIEW_LIVE_COPY.approvedToast,
        undo: () => {
          void onUnapprove(doc, made);
        },
      });
    } catch (error) {
      setRefusal({ doc: doc.evidence_version_id, words: blockerWords(error) });
    }
  };
  const mismatches = items.filter((d) => d.approval === "mismatch").length;
  return (
    <div data-screen="TAX-04" data-live className="flex flex-col gap-[8px] p-[12px]">
      <div className="text-[13px] font-medium" data-review-count>
        {REVIEW_LIVE_COPY.review(tree.data?.review_count ?? 0)}
      </div>
      <ul aria-label="Documents" className="flex flex-col">
        {items.map((doc) => {
          const made = mine[doc.evidence_version_id];
          const words = refusal?.doc === doc.evidence_version_id ? refusal.words : [];
          return (
            <li
              key={doc.evidence_version_id}
              data-document={doc.evidence_version_id}
              data-approval={doc.approval}
              className="flex min-h-[42px] flex-col gap-[4px] border-b border-hairline py-[6px]"
            >
              <div className="flex items-center gap-[8px]">
                <span className="flex min-w-0 flex-1 flex-col">
                  <span className="truncate text-[13px]">{doc.title}</span>
                  <span className="text-[11.5px] text-ink-3">{doc.category}</span>
                </span>
                {doc.approval === "approved" ? (
                  <Pill variant="green-tint" size="state">
                    {REVIEW_LIVE_COPY.approved(doc.approvals_count ?? 1)}
                  </Pill>
                ) : doc.approval === "mismatch" ? (
                  <Pill variant="red-tint" size="state">
                    {REVIEW_LIVE_COPY.mismatch}
                  </Pill>
                ) : (
                  <Pill variant="neutral" size="state">
                    {REVIEW_LIVE_COPY.unapproved}
                  </Pill>
                )}
                {made !== undefined ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={reverse.isPending}
                    onClick={() => void onUnapprove(doc, made)}
                  >
                    {REVIEW_LIVE_COPY.unapprove}
                  </Button>
                ) : doc.approval !== "approved" && canApprove && level !== undefined ? (
                  <Button
                    variant="primary"
                    size="sm"
                    disabled={doc.approval === "mismatch" || approve.isPending}
                    title={doc.approval === "mismatch" ? BLOCKER_COPY.mismatch(1) : undefined}
                    onClick={() => void onApprove(doc)}
                  >
                    {REVIEW_LIVE_COPY.approve}
                  </Button>
                ) : null}
              </div>
              {words.map((w) => (
                <p key={w} role="alert" className="text-[12.5px] text-red-ink">
                  {w}
                </p>
              ))}
            </li>
          );
        })}
      </ul>
      {mismatches > 0 ? (
        <p className="text-[11.5px] text-ink-3" data-mismatch-helper>
          {BLOCKER_COPY.mismatch(mismatches)}
        </p>
      ) : null}
    </div>
  );
}
