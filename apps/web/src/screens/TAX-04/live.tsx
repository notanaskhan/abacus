// T-04-T29 (TASK-6828): TAX-04 Review on a live build. The review tree at the viewer's level
// (`GET /v1/tax/returns/{id}/review-tree`, "Review n" from the server), Approve at the viewer's
// level (`POST …/document-approvals` with the version the person saw) and Unapprove of the live
// approval at that level (`POST /v1/tax/document-approvals/{id}/reverse`, a reversing row; the
// tree names the approval, so one made in another session or by a colleague at the same level is
// reachable too, TASK-7322; the approval's toast offers the same as Undo for 10 s, DEC-24). A
// mismatch disables Approve with the handoff's helper; every refusal shows its words
// (`blockerWords`). With nothing left to review, "Request final approval…" (TAX-05 e) confirms
// the request to BH-TAX-02's signer, named by the server (`final_approver_user_id`), at SHL-12's
// "Partner · final approval (BH-TAX-02)"; it is disabled while the K-1 is a draft, and a refusal
// names its blockers.
import {
  documentApprovalMutation,
  documentApprovalReverseMutation,
  finalApprovalRequestMutation,
  reviewTreeOptions,
  workspaceOptions,
} from "@abacus/api-client/query";
import type { DocumentApprovalOut, ReviewDocumentOut } from "@abacus/api-client";
import { Button, ConfirmDialog, EmptyState, Pill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useStaffNames } from "../../domain/requests";
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
  // TAX-05 e and SHL-12's level line; the toast is the activity's own words.
  requestFinal: "Request final approval…",
  requestTitle: "Request final approval",
  requestLevel: "Partner · final approval (BH-TAX-02)",
  assignee: (name: string) => `Assignee · ${name}`,
  requested: "Final approval requested",
  noSigner: "No partner is named for this client in BH-TAX-02.",
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
  const request = useMutation({ ...finalApprovalRequestMutation(), onSettled: refresh });
  const canApprove = summary.data?.allowed_actions.includes("document.approve") === true;
  const canRequest =
    summary.data?.allowed_actions.includes("tax_return.request_approval") === true;
  const signer = summary.data?.final_approver_user_id ?? null;
  const names = useStaffNames();
  const [confirming, setConfirming] = useState(false);
  const [requestWords, setRequestWords] = useState<string[]>([]);

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
  const onUnapprove = async (doc: ReviewDocumentOut, approvalId: string): Promise<void> => {
    setRefusal(null);
    try {
      await reverse.mutateAsync({ path: { approval_id: approvalId }, body: {} });
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
          void onUnapprove(doc, made.id);
        },
      });
    } catch (error) {
      setRefusal({ doc: doc.evidence_version_id, words: blockerWords(error) });
    }
  };
  const mismatches = items.filter((d) => d.approval === "mismatch").length;
  const reviewCount = tree.data?.review_count ?? 0;
  const draftK1 = summary.data?.k1_dependency === "draft_pre_release";
  const onRequest = async (): Promise<void> => {
    if (signer === null) return;
    setRequestWords([]);
    try {
      await request.mutateAsync({
        path: { return_id: returnId },
        body: { assignee_user_id: signer },
      });
      toast.show({ text: REVIEW_LIVE_COPY.requested });
    } catch (error) {
      setRequestWords(blockerWords(error));
    }
  };
  return (
    <div data-screen="TAX-04" data-live className="flex flex-col gap-[8px] p-[12px]">
      <div className="text-[13px] font-medium" data-review-count>
        {REVIEW_LIVE_COPY.review(reviewCount)}
      </div>
      <ul aria-label="Documents" className="flex flex-col">
        {items.map((doc) => {
          const made = mine[doc.evidence_version_id];
          // The approval to reverse: the one made here, else the tree's live one at this level.
          const live =
            made?.id ?? (doc.approval === "approved" ? (doc.approval_id ?? undefined) : undefined);
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
                {live !== undefined && canApprove ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={reverse.isPending}
                    onClick={() => void onUnapprove(doc, live)}
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
      {canRequest && reviewCount === 0 ? (
        <div className="flex flex-col gap-[6px]" data-final-request>
          <Button
            variant="primary"
            disabled={draftK1 || signer === null || request.isPending}
            title={
              draftK1
                ? BLOCKER_COPY.draft_k1
                : signer === null
                  ? REVIEW_LIVE_COPY.noSigner
                  : undefined
            }
            onClick={() => {
              setConfirming(true);
            }}
          >
            {REVIEW_LIVE_COPY.requestFinal}
          </Button>
          {draftK1 ? <p className="text-[11px] text-ink-3">{BLOCKER_COPY.draft_k1}</p> : null}
          {!draftK1 && signer === null ? (
            <p className="text-[11px] text-ink-3">{REVIEW_LIVE_COPY.noSigner}</p>
          ) : null}
          {requestWords.map((w) => (
            <p key={w} role="alert" className="text-[12.5px] text-red-ink">
              {w}
            </p>
          ))}
          <ConfirmDialog
            open={confirming}
            onOpenChange={setConfirming}
            title={REVIEW_LIVE_COPY.requestTitle}
            confirmLabel={REVIEW_LIVE_COPY.requestTitle}
            destructive={false}
            initialFocus="cancel"
            onConfirm={() => void onRequest()}
          >
            <span className="flex flex-col gap-[2px]">
              <span>{REVIEW_LIVE_COPY.requestLevel}</span>
              <span>
                {REVIEW_LIVE_COPY.assignee(signer === null ? "" : (names.get(signer) ?? ""))}
              </span>
            </span>
          </ConfirmDialog>
        </div>
      ) : null}
    </div>
  );
}
