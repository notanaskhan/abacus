// The Activity tab of a record (CLI-02, ENG-02; P-07-T61, DEC-822): P-07-T57's audit-trail lines
// for the client or the engagement, newest first, in ADM-07's actor grammar and words. Read only;
// a line never opens the audit drawer here (ADM-07 owns it). Rows are data from the generated
// client; the copy is ADM-07's (`titleOf`, `detailOf`).
import type { AuditEventRow, ListPageAuditEventRow } from "@abacus/api-client";
import { clientActivityOptions, engagementActivityOptions } from "@abacus/api-client/query";
import { EmptyState, ErrorState, Skeleton, Tag, date, time } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import type { JSX } from "react";
import { COPY as AUDIT, detailOf, titleOf } from "../ADM-07/copy";

export const ACTIVITY_COPY = {
  label: "Activity",
  empty: "No activity yet",
  error: "Activity didn't load",
} as const;

export type RecordActivityOf = { client: string } | { engagement: string };

function Line({ row, now, tz }: { row: AuditEventRow; now: Date; tz: string }): JSX.Element {
  const title = titleOf(row);
  const detail = detailOf(row, (iso) => date(iso, { now, tz }));
  const object = row.target.label ?? "";
  return (
    <li
      data-seq={row.seq}
      className="grid grid-cols-[76px_minmax(0,1fr)_auto] items-start gap-[14px] px-[18px] py-[9px] hairline-b"
    >
      <span className="flex flex-col items-end text-right">
        <span className="text-dense text-ink-2">{date(row.effective_at, { now, tz })}</span>
        <span className="text-meta text-ink-3">{time(row.effective_at, { tz })}</span>
      </span>
      <span className="flex min-w-0 flex-col gap-[2px]">
        <span className="text-chat leading-[1.3] font-medium">{title}</span>
        {detail !== "" && <span className="text-dense leading-[1.4] text-ink-2">{detail}</span>}
      </span>
      <span className="flex items-center gap-[8px] pt-[3px]">
        {object !== "" && <Tag className="max-w-[220px] truncate">{object}</Tag>}
        <span className="text-meta text-ink-2">{AUDIT.tags[row.actor.kind]}</span>
      </span>
    </li>
  );
}

function Lines({
  query,
  now,
  tz,
}: {
  query: { isPending: boolean; isError: boolean; data: ListPageAuditEventRow | undefined };
  now: Date;
  tz: string;
}): JSX.Element {
  if (query.isPending) {
    return (
      <div aria-busy="true" className="flex flex-col gap-[10px] p-[18px]">
        <Skeleton className="h-[18px] w-3/5" />
        <Skeleton className="h-[18px] w-2/5" />
        <Skeleton className="h-[18px] w-1/2" />
      </div>
    );
  }
  if (query.isError || query.data === undefined) return <ErrorState title={ACTIVITY_COPY.error} />;
  const rows = query.data.items;
  if (rows.length === 0) return <EmptyState title={ACTIVITY_COPY.empty} />;
  return (
    <ul aria-label={ACTIVITY_COPY.label} className="flex flex-col">
      {rows.map((row) => (
        <Line key={row.seq} row={row} now={now} tz={tz} />
      ))}
    </ul>
  );
}

function ClientLines({
  clientId,
  now,
  tz,
}: {
  clientId: string;
  now: Date;
  tz: string;
}): JSX.Element {
  const query = useQuery(
    clientActivityOptions({ path: { client_id: clientId }, query: { limit: 50 } }),
  );
  return <Lines query={query} now={now} tz={tz} />;
}

function EngagementLines({
  engagementId,
  now,
  tz,
}: {
  engagementId: string;
  now: Date;
  tz: string;
}): JSX.Element {
  const query = useQuery(
    engagementActivityOptions({ path: { engagement_id: engagementId }, query: { limit: 50 } }),
  );
  return <Lines query={query} now={now} tz={tz} />;
}

export function RecordActivity({
  of,
  now,
  tz,
}: {
  of: RecordActivityOf;
  now: Date;
  tz: string;
}): JSX.Element {
  return "client" in of ? (
    <ClientLines clientId={of.client} now={now} tz={tz} />
  ) : (
    <EngagementLines engagementId={of.engagement} now={now} tz={tz} />
  );
}
