import type { FileMatchOut, RequestItemOut } from "@abacus/api-client";
import { inboxMatchesQueryKey, requestMatchMutation } from "@abacus/api-client/query";
import { AgentText, AiTag, Button, Dialog } from "@abacus/ui";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import { EvidencePreview } from "./EvidencePreview";

// SPEC-033 (TASK-066): the matcher's proposals for one inbox file, for the firm only. Agent text
// is shown through AgentText with the AI tag (ADR-065); only verified quotes reach this screen.

const FAILED: Record<string, string> = {
  data_boundary: "AI suggestions aren't available for real client data yet.",
  budget_exceeded: "The suggestion stopped at its cost limit.",
  budget_exhausted: "The firm's AI budget is used up for now.",
  capacity_timeout: "The suggestion waited too long for the AI provider. Try again later.",
  provider_unavailable: "The AI provider was unavailable. Try again later.",
};

function where(quote: FileMatchOut["proposals"][number]["quotes"][number]): string {
  if (quote.page != null) return `Page ${String(quote.page)}`;
  return [quote.sheet, quote.cell].filter(Boolean).join(" ");
}

export function InboxAIMatch({
  engagementId,
  fileId,
  match,
  items,
  canRequest,
}: {
  engagementId: string;
  fileId: string;
  match: FileMatchOut | undefined;
  items: RequestItemOut[];
  canRequest: boolean;
}): JSX.Element | null {
  const queryClient = useQueryClient();
  const [page, setPage] = useState<number | null>(null);
  const request = useMutation({
    ...requestMatchMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: inboxMatchesQueryKey({ path: { engagement_id: engagementId } }),
      });
    },
  });
  const describe = new Map(items.map((i) => [i.id, i.description]));
  const refused =
    request.isError && errorMessage(request.error) === "ai_match_unavailable"
      ? "AI suggestions aren't available in this environment."
      : request.isError
        ? "Couldn't start the suggestion. Try again."
        : null;
  const suggest = canRequest ? (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        size="sm"
        variant="ghost"
        disabled={request.isPending}
        onClick={() => {
          request.mutate({ path: { engagement_id: engagementId, file_id: fileId } });
        }}
      >
        Suggest with agent
      </Button>
      {refused !== null && <span className="text-meta text-danger">{refused}</span>}
    </span>
  ) : null;

  let body: JSX.Element | null;
  if (match === undefined) {
    body = suggest;
  } else if (match.status === "running") {
    body = <span className="text-meta text-muted">Looking at the file…</span>;
  } else if (match.status !== "completed") {
    body = (
      <span className="flex flex-wrap items-center gap-2 text-meta text-muted">
        {FAILED[match.reason ?? ""] ?? "The AI suggestion didn't finish."}
        {match.reason !== "data_boundary" && suggest}
      </span>
    );
  } else if (match.none_fit) {
    body = (
      <div className="flex flex-col gap-1 text-meta">
        <span className="flex items-center gap-2">
          <AiTag />
          <span>None of the requests fit</span>
        </span>
        {match.none_fit_rationale != null && <AgentText text={match.none_fit_rationale} />}
      </div>
    );
  } else if (match.proposals.length === 0) {
    body = (
      <span className="flex flex-wrap items-center gap-2 text-meta text-muted">
        <AiTag /> No confident suggestion. {suggest}
      </span>
    );
  } else {
    body = (
      <ul aria-label="AI suggestions" className="flex flex-col gap-2">
        {match.proposals.map((p) => (
          <li key={p.request_item_id} className="flex flex-col gap-1 text-meta">
            <span className="flex flex-wrap items-center gap-2">
              <AiTag citations={p.quotes.length} />
              <span className="font-medium text-ink">
                {describe.get(p.request_item_id) ?? "Request"}
              </span>
              <span className="text-muted tabular-nums">
                {Math.round(Number(p.confidence) * 100)}% confident
              </span>
            </span>
            <AgentText text={p.rationale} />
            {p.quotes.map((quote, n) => (
              <span key={n} className="text-muted">
                {quote.page != null ? (
                  <button
                    type="button"
                    className="text-accent hover:underline"
                    onClick={() => {
                      if (quote.page != null) setPage(quote.page);
                    }}
                  >
                    {where(quote)}
                  </button>
                ) : (
                  <span>{where(quote)}</span>
                )}
                : &ldquo;
                <AgentText inline text={quote.quote} />
                &rdquo;
              </span>
            ))}
          </li>
        ))}
      </ul>
    );
  }
  if (body === null) return null;
  return (
    <div className="flex flex-col gap-1 rounded-[var(--radius-control)] border border-ai-line p-2">
      {body}
      <Dialog
        open={page !== null}
        onOpenChange={(next) => {
          if (!next) setPage(null);
        }}
        title="Preview"
      >
        {page !== null && (
          <EvidencePreview source={{ kind: "inbox", engagementId, fileId }} openAtPage={page} />
        )}
      </Dialog>
    </div>
  );
}
