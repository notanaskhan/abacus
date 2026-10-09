import type { ProposalOut, QueueEntryOut } from "@abacus/api-client";
import {
  meOptions,
  releaseMutation,
  reviewQueueOptions,
  reviewQueueQueryKey,
  takeMutation,
} from "@abacus/api-client/query";
import { AgentText, Alert, Badge, Button, Card, EmptyState, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { confidencePercent, sourceLabel } from "../board/join";
import { DecisionActions } from "./DecisionActions";

/** The review queue for one engagement (SPEC-004 AC-1 to AC-8, Q6): take an item and decide.
 * Minimal by design; full item detail comes with increment 6. */
export function Review({ engagementId }: { engagementId: string }): JSX.Element {
  const path = { path: { engagement_id: engagementId } };
  const queue = useQuery(reviewQueueOptions(path));
  const me = useQuery(meOptions());
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-xl font-semibold">Review queue</h1>
      {queue.isPending ? (
        <Skeleton className="h-24 w-full" />
      ) : queue.isError ? (
        <Alert title="Couldn't load the review queue">{errorMessage(queue.error)}</Alert>
      ) : queue.data.length === 0 ? (
        <EmptyState title="Nothing to review">New evidence appears here.</EmptyState>
      ) : (
        <section aria-label="Items awaiting a decision" className="flex flex-col gap-3">
          {queue.data.map((entry) => (
            <ReviewEntry
              key={entry.evidence_version.id}
              engagementId={engagementId}
              entry={entry}
              meId={me.data?.user_id ?? null}
            />
          ))}
        </section>
      )}
    </div>
  );
}

function Proposal({ proposal }: { proposal: ProposalOut }): JSX.Element {
  return (
    <div className="flex flex-col gap-1" aria-label="Agent proposal">
      <p>
        <Badge tone={proposal.action === "ready_for_review" ? "success" : "warning"}>
          {proposal.action === "ready_for_review" ? "Agent: ready" : "Agent: needs revision"}
        </Badge>{" "}
        <span className="text-muted">confidence {confidencePercent(proposal.confidence)}</span>
      </p>
      <AgentText text={proposal.rationale} />
      {proposal.citations.length > 0 && (
        <ul className="flex flex-col gap-1" aria-label="Citations">
          {proposal.citations.map((c) => (
            <li key={c.cell} className="flex items-center gap-2">
              <Badge tone={c.verified ? "success" : "danger"}>
                {c.verified ? "Verified" : "Unverified"}
              </Badge>
              <span>
                Cell <AgentText inline text={c.cell} />
              </span>
              {c.quote !== null && <AgentText inline text={`“${c.quote}”`} />}
            </li>
          ))}
        </ul>
      )}
      {proposal.unverified.length > 0 && (
        <div>
          <p className="text-muted">Couldn't be verified:</p>
          <ul className="list-disc pl-5">
            {proposal.unverified.map((note, i) => (
              <li key={`${String(i)}-${note}`}>
                <AgentText inline text={note} />
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

function ReviewEntry({
  engagementId,
  entry,
  meId,
}: {
  engagementId: string;
  entry: QueueEntryOut;
  meId: string | null;
}): JSX.Element {
  const queryClient = useQueryClient();
  const versionPath = { engagement_id: engagementId, version_id: entry.evidence_version.id };
  // Refresh on success and on error: a 409 (taken, decided, superseded, proposal changed) means
  // the card is stale.
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      queryKey: reviewQueueQueryKey({ path: { engagement_id: engagementId } }),
    });
  };
  const after = { onSuccess: refresh, onError: refresh };
  const take = useMutation({ ...takeMutation(), ...after });
  const release = useMutation({ ...releaseMutation(), ...after });
  const failed = take.error ?? release.error;
  const item = entry.item_description;
  const assignee = entry.assignee_user_id;
  const version = entry.evidence_version;
  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <Link
            to="/engagements/$engagementId/items/$itemId"
            params={{ engagementId, itemId: entry.request_item_id }}
            className="font-medium hover:underline"
          >
            {item}
          </Link>
          <p className="text-sm text-muted">
            {entry.item_audit_area} · {sourceLabel(version)} from {version.source}
            {version.period_start !== null &&
              ` · ${version.period_start} to ${version.period_end ?? ""}`}{" "}
            · version {String(version.version_no)}
          </p>
          <p className="text-sm text-muted">
            {assignee === null
              ? "Not taken"
              : assignee === meId
                ? "Taken by you"
                : "Taken by someone else"}
          </p>
        </div>
        {assignee === null && (
          <Button
            size="sm"
            variant="outline"
            aria-label={`Take ${item}`}
            onClick={() => {
              take.mutate({ path: versionPath });
            }}
          >
            Take
          </Button>
        )}
        {assignee !== null && assignee === meId && (
          <Button
            size="sm"
            variant="ghost"
            aria-label={`Release ${item}`}
            onClick={() => {
              release.mutate({ path: versionPath });
            }}
          >
            Release
          </Button>
        )}
      </div>
      {entry.proposal !== null && <Proposal proposal={entry.proposal} />}
      <DecisionActions
        engagementId={engagementId}
        versionId={version.id}
        itemLabel={item}
        seenProposal={entry.proposal?.screening_result_id ?? null}
        onSettled={refresh}
      />
      {failed !== null && <Alert title="That didn't work">{errorMessage(failed)}</Alert>}
    </Card>
  );
}
