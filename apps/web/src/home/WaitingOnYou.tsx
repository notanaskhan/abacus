import {
  fieldworkWaitingOptions,
  listEngagementsOptions,
  overdueWaitingOptions,
  reviewWaitingOptions,
} from "@abacus/api-client/query";
import { Button, type Column, DataTable, EmptyState, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import type { JSX } from "react";
import { type QueueRow, queueRows } from "./queue";

const PATHS = {
  fieldwork: "/engagements/$engagementId/fieldwork",
  review: "/engagements/$engagementId/review",
  requests: "/engagements/$engagementId/requests",
} as const;

/** TASK-102 (the plan's HOME-01/02): what's waiting on this person across their engagements,
 * approvals first. A row opens the tab where it's done. */
export function WaitingOnYou(): JSX.Element | null {
  const navigate = useNavigate();
  const fieldwork = useQuery({ ...fieldworkWaitingOptions(), retry: false });
  const review = useQuery({ ...reviewWaitingOptions(), retry: false });
  const overdue = useQuery({ ...overdueWaitingOptions(), retry: false });
  const engagements = useQuery(listEngagementsOptions());
  // Show what's arrived; say when some lists are still being checked.
  const loading = fieldwork.isPending && review.isPending && overdue.isPending;
  const checking = fieldwork.isPending || review.isPending || overdue.isPending;
  const rows = queueRows(
    fieldwork.data ?? [],
    review.data ?? [],
    overdue.data ?? [],
    engagements.data ?? [],
  );
  const open = (row: QueueRow): void => {
    void navigate({ to: PATHS[row.to], params: { engagementId: row.engagementId } });
  };
  const columns: Column<QueueRow>[] = [
    {
      key: "what",
      header: "To do",
      cell: (r) => <span className="font-medium">{r.what}</span>,
    },
    {
      key: "engagement",
      header: "Engagement",
      cell: (r) => (
        <span className="text-ink-2">
          {r.engagement}
          {r.client !== "" && r.client !== r.engagement && (
            <span className="text-ink-3">{` · ${r.client}`}</span>
          )}
        </span>
      ),
      sortValue: (r) => r.engagement,
    },
    {
      key: "action",
      header: <span className="sr-only">Action</span>,
      align: "right",
      width: "w-[120px]",
      cell: (r) => (
        <Button
          size="sm"
          variant={r.rank === 0 ? "primary" : "secondary"}
          onClick={(e) => {
            e.stopPropagation();
            open(r);
          }}
        >
          {r.action}
        </Button>
      ),
    },
  ];
  return (
    <section
      aria-labelledby="waiting-heading"
      className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e2"
    >
      <div className="flex min-h-[50px] items-center gap-2 border-b-[0.5px] border-hair px-4">
        <h2 id="waiting-heading" className="text-[15px] font-medium tracking-[-0.012em]">
          Waiting on you
        </h2>
        {!loading && <span className="text-[12.5px] text-ink-3 tabular-nums">{rows.length}</span>}
        {checking && !loading && <span className="text-[12px] text-ink-3">Still checking…</span>}
      </div>
      {loading ? (
        <div className="flex flex-col gap-3 p-4" aria-busy="true">
          <Skeleton className="w-[62%]" />
          <Skeleton className="w-[38%]" />
        </div>
      ) : rows.length === 0 && !checking ? (
        <EmptyState title="Nothing is waiting on you">
          Approvals, reviews, decisions and overdue client items show here.
        </EmptyState>
      ) : (
        <DataTable
          label="Waiting on you"
          rows={rows}
          columns={columns}
          rowKey={(r) => r.key}
          onRowClick={open}
        />
      )}
    </section>
  );
}
