import type { ReviewFlagOut } from "@abacus/api-client";
import {
  requestReviewMutation,
  uploadReviewOptions,
  uploadReviewQueryKey,
} from "@abacus/api-client/query";
import { AgentText, AiTag, Alert, Badge, Button, Skeleton } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { isForbidden } from "../shell/mfa";

// SPEC-030 AC-6 (TASK-059): the upload reviewer's flags, for the firm only. Agent text is shown
// through AgentText (ADR-065); only quotes code verified reach this screen (SPEC-030 Q3).

const CATEGORY: Record<string, string> = {
  irrelevant: "Not the document requested",
  draft: "Looks like a draft",
  altered: "Looks altered",
};

const FAILED: Record<string, string> = {
  data_boundary: "AI review isn't available for real client data yet.",
  budget_exceeded: "The review stopped at its cost limit.",
  budget_exhausted: "The firm's AI budget is used up for now.",
  capacity_timeout: "The review waited too long for the AI provider. Try again later.",
  provider_unavailable: "The AI provider was unavailable. Try again later.",
};

function where(quote: ReviewFlagOut["quotes"][number]): string {
  if (quote.page != null) return `Page ${String(quote.page)}`;
  return [quote.sheet, quote.cell].filter(Boolean).join(" ");
}

export function AIReviewPanel({
  engagementId,
  versionId,
  canRequest,
  onOpenPage,
}: {
  engagementId: string;
  versionId: string;
  canRequest: boolean;
  onOpenPage: (page: number) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = { path: { engagement_id: engagementId, version_id: versionId } };
  const review = useQuery({
    ...uploadReviewOptions(path),
    retry: false,
    refetchInterval: (query) => (query.state.data?.status === "running" ? 4000 : false),
  });
  const request = useMutation({
    ...requestReviewMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: uploadReviewQueryKey(path) });
    },
  });
  const refused =
    request.isError && errorMessage(request.error) === "ai_review_unavailable"
      ? "AI review isn't available in this environment."
      : request.isError
        ? "Couldn't start the review. Try again."
        : null;
  const reviewNow = canRequest ? (
    <span className="inline-flex flex-wrap items-center gap-2">
      <Button
        size="sm"
        variant="secondary"
        disabled={request.isPending}
        onClick={() => {
          request.mutate(path);
        }}
      >
        Review now
      </Button>
      {refused !== null && <span className="text-meta text-danger">{refused}</span>}
    </span>
  ) : null;

  if (review.isPending) return <Skeleton className="h-20" />;
  if (review.isError) {
    return isForbidden(review.error) ? (
      <p className="text-body text-ink-3">You can&apos;t see this file&apos;s AI review.</p>
    ) : (
      <Alert title="Couldn't load the AI review">Try again in a moment.</Alert>
    );
  }
  const data = review.data;
  if (data.status === "none") {
    return (
      <div className="flex flex-wrap items-center gap-3 text-body text-ink-3">
        Not reviewed yet.
        {reviewNow}
      </div>
    );
  }
  if (data.status === "running") return <p className="text-body text-ink-3">Reviewing…</p>;
  if (data.status !== "completed") {
    return (
      <div className="flex flex-wrap items-center gap-3 text-body text-ink-3">
        {FAILED[data.reason ?? ""] ?? "The AI review didn't finish."}
        {data.reason !== "data_boundary" && reviewNow}
      </div>
    );
  }
  if (data.flags.length === 0) {
    return (
      <div className="flex flex-wrap items-center gap-3 text-body">
        <AiTag />
        <span className="text-ok">No concerns</span>
        {reviewNow}
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <ul aria-label="AI flags" className="flex flex-col gap-3">
        {data.flags.map((flag, n) => (
          <li
            key={`${flag.category}-${String(n)}`}
            className="flex flex-col gap-1 rounded-[var(--radius-control)] border border-hair p-3 text-body"
          >
            <span className="flex flex-wrap items-center gap-2">
              <AiTag citations={flag.quotes.length} />
              <Badge tone="warning">{CATEGORY[flag.category] ?? flag.category}</Badge>
              <span className="text-meta text-ink-3 tabular-nums">
                {Math.round(Number(flag.confidence) * 100)}% confident
              </span>
            </span>
            <AgentText text={flag.rationale} />
            <ul className="flex flex-col gap-1">
              {flag.quotes.map((quote, q) => (
                <li key={q} className="text-meta text-ink-3">
                  {quote.page != null ? (
                    <button
                      type="button"
                      className="text-espresso hover:underline"
                      onClick={() => {
                        if (quote.page != null) onOpenPage(quote.page);
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
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ul>
      <div>{reviewNow}</div>
    </div>
  );
}
