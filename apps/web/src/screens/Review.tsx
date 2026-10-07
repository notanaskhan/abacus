import type { QueueEntryOut } from "@abacus/api-client";
import {
  acceptMutation,
  reasonCodesOptions,
  rejectMutation,
  releaseMutation,
  reviewQueueOptions,
  reviewQueueQueryKey,
  sendBackMutation,
  takeMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Alert,
  Badge,
  Button,
  Card,
  EmptyState,
  Input,
  Label,
  Skeleton,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { confidencePercent } from "../board/join";

type Kind = "accept" | "reject" | "send_back";

/** The review queue for one engagement (SPEC-004 AC-1 to AC-8, Q6): take an item and decide.
 * Minimal by design; full item detail comes with increment 6. */
export function Review({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const queue = useQuery(reviewQueueOptions(path));
  if (queue.isPending) return <Skeleton className="h-24 w-full" />;
  if (queue.isError)
    return <Alert title="Couldn't load the review queue">{errorMessage(queue.error)}</Alert>;
  if (queue.data.length === 0) {
    return <EmptyState title="Nothing to review">New evidence appears here.</EmptyState>;
  }
  return (
    <section aria-label="Review queue" className="space-y-3">
      {queue.data.map((entry) => (
        <ReviewEntry key={entry.evidence_version.id} engagementId={engagementId} entry={entry} />
      ))}
    </section>
  );
}

function ReviewEntry({
  engagementId,
  entry,
}: {
  engagementId: string;
  entry: QueueEntryOut;
}): JSX.Element {
  const queryClient = useQueryClient();
  const versionPath = {
    engagement_id: engagementId,
    version_id: entry.evidence_version.id,
  };
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: reviewQueueQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  const take = useMutation({ ...takeMutation(), onSuccess: refresh });
  const release = useMutation({ ...releaseMutation(), onSuccess: refresh });
  const [kind, setKind] = useState<Kind>("accept");
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const codes = useQuery({
    ...reasonCodesOptions({
      path: {
        engagement_id: engagementId,
        applies_to: kind === "send_back" ? "send_back" : "reject",
      },
    }),
    enabled: kind !== "accept",
  });
  const accept = useMutation({ ...acceptMutation(), onSuccess: refresh });
  const reject = useMutation({ ...rejectMutation(), onSuccess: refresh });
  const sendBack = useMutation({ ...sendBackMutation(), onSuccess: refresh });
  const deciding = accept.isPending || reject.isPending || sendBack.isPending;
  const failed = accept.error ?? reject.error ?? sendBack.error ?? take.error ?? release.error;
  const decide = (): void => {
    const body = {
      decision: kind,
      reason_code: kind === "accept" ? null : reason || null,
      note: note.trim() === "" ? null : note,
    };
    const options = { path: versionPath, body };
    if (kind === "accept") accept.mutate(options);
    else if (kind === "reject") reject.mutate(options);
    else sendBack.mutate(options);
  };
  const proposal = entry.proposal;
  return (
    <Card className="space-y-2 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="font-medium">{entry.item_description}</p>
          <p className="text-sm text-slate-600">{entry.item_audit_area}</p>
        </div>
        {entry.assignee_user_id === null ? (
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              take.mutate({ path: versionPath });
            }}
          >
            Take
          </Button>
        ) : (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              release.mutate({ path: versionPath });
            }}
          >
            Release
          </Button>
        )}
      </div>
      {proposal !== null && (
        <div className="space-y-1">
          <Badge tone={proposal.action === "ready_for_review" ? "success" : "warning"}>
            {proposal.action === "ready_for_review" ? "Agent: ready" : "Agent: needs revision"} ·{" "}
            {confidencePercent(proposal.confidence)}
          </Badge>
          <AgentText text={proposal.rationale} />
        </div>
      )}
      <fieldset className="flex flex-wrap items-end gap-3" disabled={deciding}>
        <Label className="flex flex-col gap-1">
          Decision
          <select
            className="rounded border px-2 py-1"
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as Kind);
              setReason("");
            }}
          >
            <option value="accept">Accept</option>
            <option value="reject">Reject</option>
            <option value="send_back">Send back</option>
          </select>
        </Label>
        {kind !== "accept" && (
          <Label className="flex flex-col gap-1">
            Reason
            <select
              className="rounded border px-2 py-1"
              value={reason}
              onChange={(e) => {
                setReason(e.target.value);
              }}
            >
              <option value="">Choose a reason</option>
              {(codes.data ?? []).map((c) => (
                <option key={c.code} value={c.code}>
                  {c.label}
                </option>
              ))}
            </select>
          </Label>
        )}
        <Label className="flex flex-col gap-1">
          Note
          <Input
            value={note}
            maxLength={2000}
            onChange={(e) => {
              setNote(e.target.value);
            }}
          />
        </Label>
        <Button size="sm" onClick={decide} disabled={kind !== "accept" && reason === ""}>
          Record decision
        </Button>
      </fieldset>
      {failed !== null && <Alert title="That didn't work">{errorMessage(failed)}</Alert>}
    </Card>
  );
}
