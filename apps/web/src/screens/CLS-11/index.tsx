// CLS-11 · Ledger sync console (C-02-T35, DEC-5924; handoff CLS-11 a, a2, c, d, d2; SPEC-700
// AC-23, AC-24; C20 v2.1 W1 reads). The T1 variant: subbar with the back chip, filter chips, status
// tiles that filter, the connection pane (420) and the log pane with Batches and Sync events, and
// the Failures band. Every figure, time and state is the server's (`ledger-console`,
// `posting-batches`, `ledger-activity`, `ledger-pull`); the browser formats and never sums.
// Reconnecting is always the client owner's step in their portal (POR-16): "Request reconnect…"
// shows the POR-20 email it will send (`…/reconnect-requests/preview`) before anything is sent,
// and the console never shows a credential field. A connection needing reauth pauses posting and
// Sync now. Client-system text (the provider's failure message) renders as plain text only.
import type {
  LedgerSyncStatusOut,
  W1ActivityOut,
  W1ConnectionPaneOut,
  W1LedgerConsoleOut,
  W1PostingFailureOut,
  W1PostingLogRowOut,
} from "@abacus/api-client";
import { postingLogCsv } from "@abacus/api-client";
import {
  closeSummaryOptions,
  ledgerActivityOptions,
  ledgerConsoleOptions,
  ledgerConsoleQueryKey,
  ledgerSyncNowMutation,
  ledgerSyncStatusOptions,
  ledgerSyncStatusQueryKey,
  postingLogOptions,
  reconnectPreviewOptions,
  reconnectRequestMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  Dialog,
  FilterChip,
  Icon,
  Pane,
  Pill,
  RegistryStatus,
  Segmented,
  Skeleton,
  StatusDisc,
  StatusTile,
  amount,
  cn,
  count,
  date,
  monthYear,
  sameDay,
  time,
  toast,
  weekdayDate,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { EmailPreview } from "../../domain/communications";
import { ov, to } from "../../routes/to";
import { COPY as C } from "./copy";

export type Cls11Log = "batches" | "events";
type StatusFilter = "posted" | "proposed" | "failed_post";

export interface CLS11Props {
  clientEntityId: string;
  /** The close the console was opened from (the back chip "‹ August 2026 Close"). */
  closeId?: string | undefined;
  /** The log pane's segment (`?log=events`: a2). */
  log?: Cls11Log;
  onLog?: (log: Cls11Log) => void;
  /** d2: the reconnect confirm opens with the page. */
  reconnectOpen?: boolean;
}

const TH = "h-[30px] px-[10px] text-left text-[12px] font-normal text-ink-2";
const TD = "px-[10px] text-[13px]";
const HOURLY_MS = 3_600_000;
/** WB-11's catalogue key for the ledger this console reads. */
const QBO_KEY = "quickbooks_online";

function idempotency(prefix: string): { "Idempotency-Key": string } {
  return { "Idempotency-Key": `${prefix}-${crypto.randomUUID()}` };
}

/** "Aug 11, 2:41 PM" (the year only outside the current one). */
function stamp(v: string, now: Date): string {
  return `${date(v, { now })}, ${time(v)}`;
}

function Kv({ k, children, tone }: { k: string; children: ReactNode; tone?: "amber" }) {
  return (
    <div className="flex min-h-[33px] gap-[12px] px-[14px] py-[7px] hairline-b text-[13px]">
      <dt className="w-[116px] flex-none text-ink-2">{k}</dt>
      <dd className={cn("flex-1", tone === "amber" && "text-amber-ink")}>{children}</dd>
    </div>
  );
}

function Warn({ children }: { children: ReactNode }): JSX.Element {
  return (
    <span className="inline-flex gap-[6px]">
      <Icon name="triangle-alert" size={13} className="mt-[3px] flex-none text-amber" />
      <span>{children}</span>
    </span>
  );
}

function lastSync(c: W1ConnectionPaneOut): { text: string; warn: boolean } {
  const failedAt = c.last_failed_at ?? null;
  if (c.health === "needs_attention" && failedAt !== null) {
    const retry = c.retry_at ? time(c.retry_at) : null;
    const text =
      c.status_reason === "rate_limited"
        ? C.connection.failedRateLimit(time(failedAt), retry)
        : C.connection.failed(time(failedAt));
    return { text, warn: true };
  }
  if (c.health === "needs_reauth" && failedAt !== null) {
    return { text: C.connection.failedExpired(time(failedAt)), warn: true };
  }
  if (c.last_sync_at === null || c.last_sync_at === undefined) return { text: DASH, warn: false };
  const read =
    c.last_sync_transactions === null || c.last_sync_transactions === undefined
      ? null
      : count(String(c.last_sync_transactions));
  return {
    text: C.connection.lastSyncValue(time(c.last_sync_at), read, c.last_sync_errors ?? null),
    warn: false,
  };
}

function nextSync(c: W1ConnectionPaneOut, owner: string): { text: string; amber: boolean } {
  if (c.health === "needs_reauth") return { text: C.connection.paused(owner), amber: true };
  if (c.health === "needs_attention" && c.retry_at) {
    return { text: C.connection.retry(time(c.retry_at)), amber: false };
  }
  if (!c.next_sync_at) return { text: DASH, amber: false };
  const hourly =
    c.last_sync_at !== null &&
    c.last_sync_at !== undefined &&
    Date.parse(c.next_sync_at) - Date.parse(c.last_sync_at) === HOURLY_MS;
  return {
    text: hourly ? C.connection.hourly(time(c.next_sync_at)) : time(c.next_sync_at),
    amber: false,
  };
}

function ConnectionPane({
  view,
  sync,
  onSync,
  syncing,
  onReconnect,
  onIntegration,
  now,
}: {
  view: W1LedgerConsoleOut;
  sync: LedgerSyncStatusOut | undefined;
  onSync: () => void;
  syncing: boolean;
  onReconnect: () => void;
  onIntegration?: (() => void) | undefined;
  now: Date;
}): JSX.Element {
  const c = view.connection;
  if (c === null || c === undefined) {
    return (
      <Pane width={420} title={C.connection.title}>
        <p className="px-[14px] py-[12px] text-[13px] text-ink-2">{C.connection.noConnection}</p>
      </Pane>
    );
  }
  const owner = c.authorized_by ?? DASH;
  const last = lastSync(c);
  const next = nextSync(c, owner);
  const reauth = c.health === "needs_reauth";
  const retrying = c.health === "needs_attention";
  const busy = syncing || sync?.state === "syncing";
  const footer = (
    <>
      <Button
        variant="secondary"
        size="sm"
        disabled={reauth || busy}
        onClick={onSync}
        data-cls11="sync-now"
      >
        {busy ? C.connection.syncing : retrying ? C.connection.retryNow : C.connection.syncNow}
      </Button>
      <Button variant="secondary" size="sm" onClick={onReconnect} data-cls11="reconnect">
        {C.connection.requestReconnect}
      </Button>
      <span className="flex-1" />
      {onIntegration ? (
        <Button variant="ghost" size="sm" onClick={onIntegration}>
          {C.connection.integration}
        </Button>
      ) : null}
    </>
  );
  return (
    <Pane width={420} title={C.connection.title} footer={footer}>
      <div className="flex items-center gap-[10px] px-[14px] py-[14px] hairline-b">
        <span
          aria-hidden="true"
          className="flex size-[34px] flex-none items-center justify-center rounded-tile bg-green text-on-dark"
        >
          <Icon name="book-open" size={17} />
        </span>
        <span className="flex-1 text-[14px] font-medium">{view.ledger_label}</span>
        <RegistryStatus object="integration" code={c.health} />
      </div>
      <dl data-cls11="kv">
        <Kv k={C.connection.company}>{c.company_name ?? view.client_entity_name}</Kv>
        <Kv k={C.connection.authorizedBy}>
          {c.authorized_by && c.authorized_at
            ? C.connection.authorizedByValue(c.authorized_by, longDateShort(c.authorized_at))
            : (c.authorized_by ?? DASH)}
          {reauth ? ` · ${C.connection.expired}` : null}
        </Kv>
        <Kv k={C.connection.mode}>
          {c.write_granted ? C.connection.modeWrite : C.connection.modeRead}
        </Kv>
        <Kv k={C.connection.lastSync} {...(last.warn ? { tone: "amber" as const } : {})}>
          <span data-cls11="last-sync" aria-busy={busy}>
            {busy ? (
              <Skeleton className="inline-block h-[12px] w-[120px]" />
            ) : last.warn ? (
              <Warn>{last.text}</Warn>
            ) : (
              last.text
            )}
          </span>
        </Kv>
        <Kv k={C.connection.nextSync} {...(next.amber ? { tone: "amber" as const } : {})}>
          {next.text}
        </Kv>
        <Kv k={C.connection.closingDate}>
          {c.closing_date
            ? C.connection.closingDateValue(
                longDateShort(c.closing_date),
                c.closing_date_set_by ?? null,
                c.closing_date_set_at ? stamp(c.closing_date_set_at, now) : null,
              )
            : DASH}
        </Kv>
        <Kv k={C.connection.writeScope}>
          {c.write_granted ? C.connection.writeScopeValue : C.connection.readOnly}
        </Kv>
        {(c.dependents ?? []).length > 0 ? (
          <Kv k={C.connection.agents}>{(c.dependents ?? []).join(" · ")}</Kv>
        ) : null}
      </dl>
    </Pane>
  );
}

/** "Mar 9, 2026": a date that always carries its year. */
function longDateShort(v: string): string {
  return date(v, { now: 0, withYear: true });
}

function LogRow({
  r,
  paused,
  now,
}: {
  r: W1PostingLogRowOut;
  paused: boolean;
  now: Date;
}): JSX.Element {
  const sub =
    r.status === "proposed"
      ? [C.log.approved(r.approved_count, r.entry_count), paused ? C.log.postingPaused : null]
          .filter((p) => p !== null)
          .join(" · ")
      : (r.resolved_failures ?? 0) > 0
        ? C.log.resolved(r.resolved_failures ?? 0)
        : null;
  const ids =
    r.first_external_ref && r.last_external_ref
      ? C.log.qbo(r.first_external_ref, r.last_external_ref)
      : DASH;
  return (
    <tr className="h-[40px] hairline-b" data-batch={r.batch_code}>
      <td className={cn(TD, "font-medium")}>{r.batch_code}</td>
      <td className={TD}>{monthYear(r.period)}</td>
      <td className={cn(TD, "text-right tabular-nums")}>{r.entry_count}</td>
      <td className={cn(TD, "text-right tabular-nums")}>
        {r.amount === null || r.amount === undefined ? DASH : amount(r.amount, "money").text}
      </td>
      <td className={cn(TD, "py-[6px]")}>
        <span className="flex flex-col items-start gap-[2px]">
          <RegistryStatus object="posting_batch" code={r.status} />
          {sub === null ? null : <span className="text-[11.5px] text-ink-3">{sub}</span>}
        </span>
      </td>
      <td className={TD}>{r.posted_at ? stamp(r.posted_at, now) : DASH}</td>
      <td className={TD}>{ids}</td>
      <td className={TD}>{r.posted_by ?? DASH}</td>
    </tr>
  );
}

function Failures({
  failures,
  now,
}: {
  failures: readonly W1PostingFailureOut[];
  now: Date;
}): JSX.Element | null {
  if (failures.length === 0) return null;
  const resolved = failures.filter((f) => f.resolved_at).length;
  return (
    <section aria-label={C.log.failures} data-cls11="failures">
      <div className="flex h-[31px] items-center justify-between bg-nested px-[14px] hairline-b">
        <h3 className="text-[13px] font-medium">{C.log.failures}</h3>
        {resolved > 0 ? (
          <span className="text-[12px] text-ink-3">{C.log.failuresResolved(resolved)}</span>
        ) : null}
      </div>
      <ul>
        {failures.map((f) => {
          const done = f.resolved_at !== null && f.resolved_at !== undefined;
          const head = [
            stamp(f.at, now),
            f.batch_code,
            `${f.entry_ref} ${f.entry_description ?? ""}`.trim(),
          ];
          const tail = [
            f.provider_message ?? null,
            done ? C.log.resolvedBy(f.resolved_by ?? null, time(f.resolved_at ?? "")) : null,
          ].filter((p) => p !== null);
          return (
            <li
              key={`${f.at}-${f.entry_ref}`}
              className="flex min-h-[48px] items-start gap-[10px] px-[14px] py-[8px] hairline-b"
              data-failure={f.entry_ref}
            >
              <span className={cn("mt-[2px]", done && "opacity-60")}>
                <StatusDisc state={done ? "done" : "fail"} size={15} />
              </span>
              <span className="flex flex-col gap-[2px]">
                <span className={cn("text-[13px]", done ? "text-ink-2" : "font-medium")}>
                  {head.join(" · ")}
                </span>
                <span className="text-[12px] text-ink-3">{tail.join(" · ")}</span>
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function eventLine(
  e: W1ActivityOut,
  log: readonly W1PostingLogRowOut[],
  failures: readonly W1PostingFailureOut[],
): { title: string; sub: string | null; failed: boolean } {
  switch (e.kind) {
    case "sync":
      return {
        title: C.events.sync,
        sub:
          e.count === null || e.count === undefined
            ? null
            : C.events.syncRead(count(String(e.count))),
        failed: false,
      };
    case "post": {
      const batch = log.find((b) => b.batch_code === e.batch_code);
      const ids =
        batch?.first_external_ref && batch.last_external_ref
          ? C.log.qbo(batch.first_external_ref, batch.last_external_ref)
          : null;
      const fixed = batch?.resolved_failures ?? 0;
      const resolved = fixed > 0 ? C.log.resolved(fixed) : null;
      return {
        title: C.events.posted(e.batch_code ?? "", e.count ?? 0),
        sub: [ids, resolved].filter((p) => p !== null).join(" · ") || null,
        failed: false,
      };
    }
    case "closing_date":
      // The title names the date; SyncEvents fills it from the console's closing date.
      return { title: C.events.closingDate(DASH), sub: e.actor_name ?? null, failed: false };
    case "sync_failed": {
      if (e.entry_ref) {
        const f = failures.find(
          (x) => x.entry_ref === e.entry_ref && x.batch_code === e.batch_code,
        );
        return {
          title: C.events.failedPost(e.entry_ref),
          sub: f?.provider_message ?? null,
          failed: true,
        };
      }
      return {
        title: C.events.syncFailed,
        sub: e.provider_code ? (C.events.reasons[e.provider_code] ?? null) : null,
        failed: true,
      };
    }
    default:
      return { title: e.kind, sub: null, failed: false };
  }
}

function dayLabel(v: string, now: Date): string {
  const day = weekdayDate(v, { now });
  return sameDay(v, now) ? C.events.today(day) : day;
}

function SyncEvents({
  items,
  log,
  failures,
  closingDate,
  now,
}: {
  items: readonly W1ActivityOut[];
  log: readonly W1PostingLogRowOut[];
  failures: readonly W1PostingFailureOut[];
  closingDate: string | null;
  now: Date;
}): JSX.Element {
  if (items.length === 0) {
    return <p className="px-[14px] py-[12px] text-[13px] text-ink-2">{C.events.empty}</p>;
  }
  const groups: { day: string; rows: W1ActivityOut[] }[] = [];
  for (const e of items) {
    const day = dayLabel(e.at, now);
    const last = groups.at(-1);
    if (last?.day === day) last.rows.push(e);
    else groups.push({ day, rows: [e] });
  }
  return (
    <div data-cls11="events">
      {groups.map((g) => (
        <section key={g.day} aria-label={g.day}>
          <h3 className="flex h-[31px] items-center bg-nested px-[14px] text-[11.5px] font-medium uppercase tracking-[0.04em] text-ink-2 hairline-b">
            {g.day}
          </h3>
          <ul>
            {g.rows.map((e) => {
              const line = eventLine(e, log, failures);
              const title =
                e.kind === "closing_date" && closingDate !== null
                  ? C.events.closingDate(longDateShort(closingDate))
                  : line.title;
              return (
                <li
                  key={`${e.at}-${e.kind}-${e.entry_ref ?? ""}`}
                  className="flex min-h-[48px] items-start gap-[12px] px-[14px] py-[8px] hairline-b"
                  data-event={e.kind}
                >
                  <span className="w-[64px] flex-none pt-[2px] text-[13px] text-ink-2">
                    {time(e.at)}
                  </span>
                  <span className="mt-[2px]">
                    <StatusDisc state={line.failed ? "fail" : "done"} size={15} />
                  </span>
                  <span className="flex flex-col gap-[2px]">
                    <span className="text-[13px] font-medium">{title}</span>
                    {line.sub === null ? null : (
                      <span className="text-[12px] text-ink-3">{line.sub}</span>
                    )}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ReconnectDialog({
  open,
  onOpenChange,
  connectionId,
  company,
  onSent,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connectionId: string;
  company: string;
  onSent: (at: string) => void;
}): JSX.Element {
  const preview = useQuery({
    ...reconnectPreviewOptions({ path: { connection_id: connectionId } }),
    enabled: open,
  });
  const send = useMutation({
    ...reconnectRequestMutation(),
    onSuccess: (out) => {
      onSent(out.requested_at);
      onOpenChange(false);
    },
    onError: () => {
      toast.show({ kind: "error", text: C.failedToLoad });
    },
  });
  const p = preview.data;
  const owner = p?.recipients[0] ?? DASH;
  const firm = p?.from_display ?? "";
  const ready = p !== undefined && p.recipients.length > 0;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} title={C.dialog.title} size="lg">
      <div className="flex flex-col gap-[12px]" data-cls11="reconnect-dialog">
        {preview.isPending ? (
          <Skeleton className="h-[120px] w-full" />
        ) : p === undefined ? (
          <p className="text-[13px] text-ink-2">{C.failedToLoad}</p>
        ) : (
          <>
            <dl className="rounded-pane bg-card shadow-e1">
              <Kv k={C.dialog.recipient}>
                {p.recipients.length > 0
                  ? C.dialog.toValue(p.recipients, company)
                  : C.dialog.noOwner}
              </Kv>
              <Kv k={C.dialog.sends}>{C.dialog.sendsValue}</Kv>
              <Kv k={C.dialog.reconnectsIn}>{C.dialog.reconnectsInValue}</Kv>
            </dl>
            <p className="text-[12px] text-ink-3">
              {C.dialog.note(owner.split(" ")[0] ?? owner, firm)}
            </p>
            {p.template_missing ? (
              <p className="text-[12.5px] text-amber-ink" data-cls11="template-missing">
                {C.dialog.missing}
              </p>
            ) : (
              <section aria-label={C.dialog.preview} data-cls11="email-preview">
                <h3 className="pb-[6px] text-[12px] text-ink-2">{p.subject}</h3>
                <EmailPreview
                  html={p.html ?? ""}
                  text={p.text ?? ""}
                  width="600"
                  title={C.dialog.preview}
                  showText={C.dialog.showText}
                  hideText={C.dialog.hideText}
                />
              </section>
            )}
          </>
        )}
        <div className="flex justify-end gap-[8px] pt-[4px]">
          <Button
            variant="secondary"
            onClick={() => {
              onOpenChange(false);
            }}
          >
            {C.dialog.cancel}
          </Button>
          <Button
            variant="primary"
            disabled={!ready || send.isPending}
            onClick={() => {
              send.mutate({
                path: { connection_id: connectionId },
                headers: idempotency("cls11-reconnect"),
              });
            }}
          >
            <Icon name="send" size={14} />
            {C.dialog.send}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

async function exportCsv(clientEntityId: string): Promise<void> {
  try {
    const { data } = await postingLogCsv({
      path: { client_entity_id: clientEntityId },
      parseAs: "blob",
      throwOnError: true,
    });
    const url = URL.createObjectURL(data);
    const link = document.createElement("a");
    link.href = url;
    link.download = "posting-log.csv";
    link.click();
    URL.revokeObjectURL(url);
  } catch {
    toast.show({ kind: "error", text: C.failedToLoad });
  }
}

export function CLS11({
  clientEntityId,
  closeId,
  log: logProp,
  onLog,
  reconnectOpen = false,
}: CLS11Props): JSX.Element {
  const openOverlay = useOpenOverlay();
  const now = useNow();
  const queries = useQueryClient();
  const path = { client_entity_id: clientEntityId };
  const [ownLog, setOwnLog] = useState<Cls11Log>(logProp ?? "batches");
  const log = logProp ?? ownLog;
  const [period, setPeriod] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<StatusFilter | null>(null);
  const [dialog, setDialog] = useState(reconnectOpen);
  const [sentAt, setSentAt] = useState<string | null>(null);
  const [kicked, setKicked] = useState(false);

  const consoleQ = useQuery(ledgerConsoleOptions({ path }));
  const allQ = useQuery(postingLogOptions({ path }));
  const filtered = period !== null || statusFilter !== null;
  const shownQ = useQuery({
    ...postingLogOptions({
      path,
      query: {
        ...(period === null ? {} : { period }),
        ...(statusFilter === null ? {} : { status: statusFilter }),
      },
    }),
    enabled: filtered,
  });
  const activityQ = useQuery({ ...ledgerActivityOptions({ path }), enabled: log === "events" });
  const syncQ = useQuery({
    ...ledgerSyncStatusOptions({ path }),
    refetchInterval: (q) => (q.state.data?.state === "syncing" ? 5_000 : false),
  });
  const close = useQuery({
    ...closeSummaryOptions({ path: { close_id: closeId ?? "" } }),
    enabled: closeId !== undefined,
  });
  const syncNow = useMutation({
    ...ledgerSyncNowMutation(),
    onSuccess: async () => {
      setKicked(false);
      await queries.invalidateQueries({ queryKey: ledgerSyncStatusQueryKey({ path }) });
      await queries.invalidateQueries({ queryKey: ledgerConsoleQueryKey({ path }) });
    },
    onError: () => {
      setKicked(false);
      toast.show({ kind: "error", text: C.failedToLoad });
    },
  });

  const chooseLog = (next: Cls11Log): void => {
    setOwnLog(next);
    onLog?.(next);
  };

  if (consoleQ.isPending) {
    return (
      <div data-screen="CLS-11" aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
        <Skeleton className="h-[42px] w-full" />
        <Skeleton className="h-[72px] w-[520px]" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  if (consoleQ.isError) {
    return (
      <div
        data-screen="CLS-11"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.failedToLoad}</p>
        <Button variant="secondary" size="sm" onClick={() => void consoleQ.refetch()}>
          {C.retryLoad}
        </Button>
      </div>
    );
  }
  const view = consoleQ.data;
  const conn = view.connection ?? null;
  const reauth = conn?.health === "needs_reauth";
  const owner = conn?.authorized_by ?? DASH;
  const requested = sentAt ?? conn?.reconnect_requested_at ?? null;
  const all = allQ.data?.items ?? [];
  const rows = filtered ? (shownQ.data?.items ?? []) : all;
  const periods = [...new Set(all.map((r) => r.period))];
  const tiles = view.tiles;
  const lastResolved = (view.failures ?? [])
    .map((f) => f.resolved_at)
    .filter((v): v is string => typeof v === "string")
    .sort()
    .at(-1);
  const company = conn?.company_name ?? view.client_entity_name;
  const shortCompany = company.split(" ")[0] ?? company;
  const toggleStatus = (s: StatusFilter): void => {
    setStatusFilter((cur) => (cur === s ? null : s));
    chooseLog("batches");
  };

  return (
    <div data-screen="CLS-11" className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[42px] items-center px-[12px]">
        {closeId !== undefined && close.data ? (
          <Link
            {...to.CLS02({ closeId })}
            className="z-10 flex h-[29px] items-center gap-[4px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
          >
            <Icon name="chevron-left" size={14} />
            {C.back(monthYear(close.data.period))}
          </Link>
        ) : null}
        <h1 className="absolute inset-x-0 flex items-center justify-center gap-[8px] text-[15px]">
          <span className="font-medium">{C.title}</span>
          <span className="text-ink-2">{view.client_entity_name}</span>
          {conn ? <RegistryStatus object="integration" code={conn.health} /> : null}
        </h1>
      </div>
      <div className="flex h-[50px] items-center gap-[8px] px-[12px]" data-cls11="filters">
        <FilterChip
          label={C.filters.period}
          icon="calendar"
          placeholder={C.filters.year}
          options={periods.map((p) => ({ value: p, label: monthYear(p) }))}
          value={period}
          onChange={setPeriod}
        />
        <span className={cn(log === "events" && "pointer-events-none opacity-50")}>
          <FilterChip
            label={C.filters.status}
            icon="circle-check"
            placeholder={C.filters.all}
            options={(Object.keys(C.filters.statuses) as StatusFilter[]).map((s) => ({
              value: s,
              label: C.filters.statuses[s],
            }))}
            value={statusFilter}
            onChange={(v) => {
              setStatusFilter(v as StatusFilter | null);
            }}
          />
        </span>
        <FilterChip
          label={C.filters.type}
          icon="layers"
          options={[
            { value: "batches", label: C.filters.types.batches },
            { value: "events", label: C.filters.types.events },
          ]}
          value={log}
          onChange={(v) => {
            chooseLog(v === "events" ? "events" : "batches");
          }}
        />
      </div>
      <div className="flex items-end gap-[8px] px-[12px] pb-[10px]" data-cls11="tiles">
        <StatusTile
          count={tiles.posted}
          label={C.tiles.posted}
          variant="green-tint"
          selected={statusFilter === "posted"}
          onSelect={() => {
            toggleStatus("posted");
          }}
        />
        <StatusTile
          count={tiles.proposed}
          label={C.tiles.proposed}
          variant="state"
          selected={statusFilter === "proposed"}
          onSelect={() => {
            toggleStatus("proposed");
          }}
        />
        <StatusTile
          count={tiles.failed_post}
          label={C.tiles.failed}
          variant="red-tint"
          selected={statusFilter === "failed_post"}
          onSelect={() => {
            toggleStatus("failed_post");
          }}
        />
        <div
          className="flex h-[72px] w-[120px] flex-col items-center justify-center gap-[7px] rounded-pane bg-card shadow-e1"
          data-cls11="closing-date"
        >
          <span className="text-[22px]">
            {tiles.closing_date ? date(tiles.closing_date, { now }) : DASH}
          </span>
          <Pill variant="neutral" size="state">
            {C.tiles.closingDate}
          </Pill>
        </div>
        <span className="flex-1" />
        {tiles.resolved_failures > 0 && lastResolved ? (
          <span className="pb-[2px] text-[11.5px] text-ink-3">
            {C.tiles.resolvedCaption(tiles.resolved_failures, date(lastResolved, { now }))}
          </span>
        ) : null}
      </div>
      {reauth ? (
        <div
          role="status"
          className="mx-[12px] mb-[10px] flex h-[40px] items-center gap-[8px] rounded-pane bg-amber-tint px-[12px] text-[13px] text-amber-ink"
          data-cls11="banner"
        >
          <Icon name="triangle-alert" size={14} />
          <span className="flex-1">
            {requested !== null
              ? C.banner.sent(owner, time(requested))
              : C.banner.expired(shortCompany, owner)}
          </span>
          {requested === null ? (
            <Button
              variant="primary"
              size="sm"
              onClick={() => {
                setDialog(true);
              }}
            >
              {C.connection.requestReconnect}
            </Button>
          ) : null}
        </div>
      ) : null}
      <div className="flex min-h-0 flex-1 gap-[10px] px-[12px] pb-[12px]">
        <ConnectionPane
          view={view}
          sync={syncQ.data}
          syncing={kicked || syncNow.isPending}
          onSync={() => {
            setKicked(true);
            syncNow.mutate({ path, headers: idempotency("cls11-sync") });
          }}
          onReconnect={() => {
            setDialog(true);
          }}
          onIntegration={() => {
            openOverlay(ov.WB11(QBO_KEY));
          }}
          now={now}
        />
        <Pane
          title={C.log.title}
          left={
            <Segmented
              size="small"
              label={C.filters.type}
              options={[{ label: C.filters.types.batches }, { label: C.filters.types.events }]}
              active={log === "events" ? C.filters.types.events : C.filters.types.batches}
              onChange={(label) => {
                chooseLog(label === C.filters.types.events ? "events" : "batches");
              }}
            />
          }
          right={
            <Button
              variant="ghost"
              size="sm"
              onClick={() => void exportCsv(clientEntityId)}
              data-cls11="export"
            >
              <Icon name="download" size={14} />
              {C.log.export}
            </Button>
          }
        >
          {log === "events" ? (
            activityQ.isPending ? (
              <Skeleton className="m-[14px] h-[200px]" />
            ) : (
              <SyncEvents
                items={activityQ.data?.items ?? []}
                log={all}
                failures={view.failures ?? []}
                closingDate={conn?.closing_date ?? tiles.closing_date ?? null}
                now={now}
              />
            )
          ) : (
            <>
              <table className="w-full border-collapse" data-cls11="log">
                <thead>
                  <tr className="hairline-b">
                    {C.log.columns.map((h, i) => (
                      <th
                        key={h}
                        scope="col"
                        className={cn(TH, (i === 2 || i === 3) && "text-right")}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <LogRow key={r.batch_id} r={r} paused={reauth} now={now} />
                  ))}
                </tbody>
              </table>
              {rows.length === 0 && !allQ.isPending ? (
                <p className="px-[14px] py-[12px] text-[13px] text-ink-2">{C.log.empty}</p>
              ) : null}
              <Failures failures={view.failures ?? []} now={now} />
            </>
          )}
        </Pane>
      </div>
      {conn ? (
        <ReconnectDialog
          open={dialog}
          onOpenChange={setDialog}
          connectionId={conn.connection_id}
          company={company}
          onSent={(at) => {
            setSentAt(at);
            void queries.invalidateQueries({ queryKey: ledgerConsoleQueryKey({ path }) });
          }}
        />
      ) : null}
    </div>
  );
}
