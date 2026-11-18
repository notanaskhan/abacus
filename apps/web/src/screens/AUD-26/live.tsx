// AUD-26 live (A-08-T32; TASK-8547; DEC-5531): the SSARS workspace on
// `GET /v1/work-items/{id}/ssars`: the rail as the server orders and states it, the engagement's
// mode (review, compilation or preparation; never switched here), the inquiry counts, and in review
// mode the analytics set's statement (AUD-13's grammar, its own read). Every word of a step and
// every count is the server's; the canvases the server does not answer yet stay on the fixture
// screen (DEC-5531).
import type { RailRowOut } from "@abacus/api-client";
import { getAnalyticsSetOptions, ssarsWorkspaceOptions } from "@abacus/api-client/query";
import { ErrorState, Segmented, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { BlockCard, SsarsRail, type SsarsStep } from "../../domain/fieldwork";
import { Statement } from "../AUD-13/live";
import { AUD26_COPY as C } from "./copy";

const STATES: readonly SsarsStep["state"][] = ["done", "in_progress", "not_started"];
const MODE_LABEL = {
  review: C.modes[0],
  compilation: C.modes[1],
  preparation: C.modes[2],
} as const;

export function stepOf(row: RailRowOut): SsarsStep {
  const state = (STATES as readonly string[]).includes(row.state)
    ? (row.state as SsarsStep["state"])
    : "not_started";
  return { key: row.key, label: row.label, state };
}

function Analytics({ setId }: { setId: string }): JSX.Element {
  const read = useQuery(getAnalyticsSetOptions({ path: { analytics_set_id: setId } }));
  if (read.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void read.refetch();
        }}
      />
    );
  }
  if (read.data === undefined) return <Skeleton className="h-[320px]" />;
  return (
    <BlockCard title={C.analyticsTitle}>
      <Statement set={read.data} />
    </BlockCard>
  );
}

export function AUD26Live({ workItemId }: { workItemId: string }): JSX.Element {
  const read = useQuery(ssarsWorkspaceOptions({ path: { work_item_id: workItemId } }));
  if (read.isError) {
    return (
      <ErrorState
        onRetry={() => {
          void read.refetch();
        }}
      />
    );
  }
  const ws = read.data;
  if (ws === undefined) return <Skeleton className="h-[480px]" />;
  const title =
    ws.mode === "compilation"
      ? C.readTitle
      : ws.mode === "preparation"
        ? C.previewTitle
        : C.analyticsTitle;
  return (
    <div
      data-screen="AUD-26"
      data-live="true"
      data-mode={ws.mode}
      className="flex gap-[12px] bg-shell p-[12px]"
    >
      <SsarsRail mode={ws.mode} steps={ws.rail.map(stepOf)} />
      <section aria-label={title} className="flex w-[696px] flex-col gap-[10px]">
        <header className="flex h-[46px] items-center justify-between">
          <h1 className="text-[14.5px] font-medium">{title}</h1>
          <Segmented
            size="small"
            label={C.modeLabel}
            options={C.modes}
            active={MODE_LABEL[ws.mode]}
          />
        </header>
        <p data-aud26="standard" className="text-[12px] text-ink-3">
          {ws.standard}
          {ws.legend === null ? "" : ` · ${ws.legend}`}
        </p>
        {ws.mode === "review" && ws.analytics_set_id !== null && (
          <Analytics setId={ws.analytics_set_id} />
        )}
      </section>
    </div>
  );
}
