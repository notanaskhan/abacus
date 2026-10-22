import type { NotificationFeedOut, NotificationItemOut } from "@abacus/api-client";
import {
  listNotificationsQueryKey,
  notificationFeedOptions,
  readAllMutation,
  readNotificationMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  DEFAULT_TZ,
  Drawer,
  EmptyState,
  Icon,
  Pill,
  Segmented,
  SkeletonRows,
  cn,
  useFormat,
} from "@abacus/ui";
import { type Query, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { registerOverlay } from "../../app-core/overlays";
import { useSession } from "../../app-core/session";
import { feedHref, firmDayGroup, kindGlyph, notificationText } from "../notifications";
import { NOTIFICATIONS } from "./copy";

// SHL-04 · the notifications drawer v2 (P-01-T10): an O2 peek (480, no scrim, the page stays live)
// opened by the bell and named in the URL as `?ov=notifications`. A white tab row with a
// Segmented control and the server's counts (All · Approvals 3 · Mentions 1 · Client activity),
// the rows grouped by day on the firm's calendar ("Today", "Friday, September 11"), unread rows
// in 500 with a 7 px brick dot, and the footer "Showing 30 days".
//
// It reads the C16 v2 feed (`GET /v1/notifications/feed`, P-01-T06): `pending` and the facts are
// resolved when read, so an upload decided elsewhere drops out of Approvals. Opening the drawer
// marks nothing read; opening a row does, and deep-links. Agent-originated rows only ever
// deep-link, and their context renders through AgentText (INV-1, AC 3.1.9).

export const FEED_DAYS = 30;
export const FEED_LIMIT = 30;

export type FeedTab = keyof typeof NOTIFICATIONS.tabs;
const TABS = Object.keys(NOTIFICATIONS.tabs) as FeedTab[];

/** A row's buttons never say these on a row an agent originated (AGENTS.md frontend rule 3). */
const HUMAN_WORDS = /\b(Approve|Sign off|Release|Send|Post|Decide)\b/;

/** A fact as text, when the facts carry it (title and context until the kind templates exist). */
function fact(item: NotificationItemOut, key: string): string | null {
  const value = item.facts[key];
  return typeof value === "string" && value !== "" ? value : null;
}

/** The button a row may carry: a deep link only ("Sign off…", "Open to-do", "Review update…"). */
export function rowButton(item: NotificationItemOut): string | null {
  const label = fact(item, "button");
  if (label === null) return null;
  if (item.actor.kind === "agent" && HUMAN_WORDS.test(label)) return null;
  return label;
}

/** The rows in their feed order, cut into consecutive day groups. */
export function groupByDay(
  items: readonly NotificationItemOut[],
  now: Date,
  tz: string,
): [string, NotificationItemOut[]][] {
  const groups: [string, NotificationItemOut[]][] = [];
  for (const item of items) {
    const label = firmDayGroup(item.created_at, now, tz);
    const last = groups[groups.length - 1];
    if (last?.[0] === label) last[1].push(item);
    else groups.push([label, [item]]);
  }
  return groups;
}

/** The tab track's options: a count only where the server counts more than none. */
export function tabOptions(
  counts: NotificationFeedOut["counts"] | undefined,
): { label: string; count?: number }[] {
  return TABS.map((tab) => {
    const count = tab === "all" ? 0 : (counts?.[tab] ?? 0);
    return count > 0
      ? { label: NOTIFICATIONS.tabs[tab], count }
      : { label: NOTIFICATIONS.tabs[tab] };
  });
}

const isFeed = (query: Query): boolean =>
  (query.queryKey[0] as { _id?: string } | undefined)?._id === "notificationFeed";

function Row({
  item,
  onOpen,
}: {
  item: NotificationItemOut;
  onOpen: (item: NotificationItemOut) => void;
}): JSX.Element {
  const f = useFormat();
  const unread = !item.read;
  const title = fact(item, "title") ?? notificationText(item.kind);
  const context = fact(item, "context");
  const pill = fact(item, "pill");
  const receipt = fact(item, "receipt");
  const button = rowButton(item);
  const agent = item.actor.kind === "agent";
  return (
    <li
      data-notification={item.id}
      data-kind={item.kind}
      className="border-b-[0.5px] border-hair last:border-b-0"
    >
      <div className="flex min-h-[64px] items-start gap-[10px] px-[12px] py-[10px]">
        <span
          aria-hidden="true"
          className="mt-[1px] flex size-[22px] flex-none items-center justify-center rounded-pill bg-nested"
        >
          <Icon name={kindGlyph(item.kind)} size={12} className="text-ink-2" />
        </span>
        <div className="flex min-w-0 flex-1 flex-col items-start gap-[3px]">
          <button
            type="button"
            onClick={() => {
              onOpen(item);
            }}
            className={cn(
              "line-clamp-2 text-left text-body hover:underline",
              unread ? "font-medium text-ink" : "text-ink-2",
            )}
          >
            {title}
            {unread && <span className="sr-only"> · {NOTIFICATIONS.unread}</span>}
          </button>
          {context !== null &&
            (agent ? (
              <AgentText inline text={context} className="text-meta text-ink-3" />
            ) : (
              <span className="text-meta text-ink-3">{context}</span>
            ))}
          {receipt !== null && (
            <span data-receipt="" className="text-meta font-medium text-green-ink">
              {receipt}
            </span>
          )}
          {button !== null && (
            <Button
              size="sm"
              variant="secondary"
              className="mt-[4px]"
              onClick={() => {
                onOpen(item);
              }}
            >
              {button}
            </Button>
          )}
        </div>
        <div className="flex flex-none items-center gap-[6px] pt-[1px]">
          {pill !== null && (
            <Pill variant="amber" size="micro">
              {pill}
            </Pill>
          )}
          {unread && (
            <span
              aria-hidden="true"
              data-dot="unread"
              className="size-[7px] rounded-pill bg-red"
            />
          )}
          <time dateTime={item.created_at} className="text-meta text-ink-3 tabular-nums">
            {f.time(item.created_at)}
          </time>
        </div>
      </div>
    </li>
  );
}

export interface NotificationsDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Go to a row's page (the router's navigate). */
  navigate: (to: string) => void;
  /** An artboard: the drawer drawn in place, on this tab. */
  held?: { tab?: FeedTab };
}

export function NotificationsDrawer({
  open,
  onOpenChange,
  navigate,
  held,
}: NotificationsDrawerProps): JSX.Element {
  const queryClient = useQueryClient();
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const [tab, setTab] = useState<FeedTab>(held?.tab ?? "all");
  const query = (t: FeedTab) =>
    notificationFeedOptions({ query: { tab: t, limit: FEED_LIMIT, days: FEED_DAYS } });
  // The All page carries the counts and the unread count whatever tab is showing.
  const all = useQuery({ ...query("all"), enabled: open, retry: false });
  const page = useQuery({ ...query(tab), enabled: open, retry: false });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ predicate: isFeed });
    void queryClient.invalidateQueries({ queryKey: listNotificationsQueryKey() });
  };
  const readOne = useMutation({ ...readNotificationMutation(), onSuccess: refresh });
  const readAll = useMutation({ ...readAllMutation(), onSuccess: refresh });
  const unread = all.data?.unread_count ?? 0;

  const openRow = (item: NotificationItemOut): void => {
    if (!item.read) readOne.mutate({ path: { notification_id: item.id } });
    const href = feedHref(item);
    if (href === null) return;
    onOpenChange(false);
    navigate(href.to);
  };

  const items = page.data?.items ?? [];
  const empty = tab === "approvals" ? NOTIFICATIONS.emptyApprovals : NOTIFICATIONS.emptyAll;
  const body = page.isPending ? (
    <div className="overflow-hidden rounded-pane bg-card shadow-e1">
      <SkeletonRows type="list" count={5} immediate label={NOTIFICATIONS.loading} />
    </div>
  ) : page.isError ? (
    <EmptyState
      tone="error"
      title={NOTIFICATIONS.error}
      action={
        <Button size="sm" variant="secondary" onClick={() => void page.refetch()}>
          {NOTIFICATIONS.retry}
        </Button>
      }
    />
  ) : items.length === 0 ? (
    <EmptyState icon="bell" title={empty.title}>
      {empty.body}
    </EmptyState>
  ) : (
    <>
      {groupByDay(items, now, tz).map(([label, rows]) => (
        <section key={label} aria-label={label} className="flex flex-col">
          <h3 className="flex h-[26px] items-center px-[2px] text-meta font-medium text-ink-3">
            {label}
          </h3>
          <ul className="flex flex-col overflow-hidden rounded-pane bg-card shadow-e1">
            {rows.map((item) => (
              <Row key={item.id} item={item} onOpen={openRow} />
            ))}
          </ul>
        </section>
      ))}
      {tab === "approvals" && (
        <Button
          size="sm"
          variant="ghost"
          className="self-start"
          onClick={() => {
            // HOME-02 is planned until I-01: the link closes the drawer.
            onOpenChange(false);
          }}
        >
          {NOTIFICATIONS.openApprovals}
        </Button>
      )}
    </>
  );

  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={NOTIFICATIONS.title}
      width={480}
      peek
      bare
      {...(held === undefined ? {} : { forceState: "open" as const })}
      meta={
        <Button
          size="sm"
          variant="ghost"
          disabled={unread === 0 || readAll.isPending}
          onClick={() => {
            readAll.mutate({});
          }}
        >
          {NOTIFICATIONS.markAllRead}
        </Button>
      }
      footer={<span className="mr-auto text-dense text-ink-3">{NOTIFICATIONS.showing}</span>}
    >
      <div className="sticky top-0 z-[1] flex h-[44px] flex-none items-center justify-center border-b-[0.5px] border-hair bg-card">
        <Segmented
          size="small"
          label={NOTIFICATIONS.tabsLabel}
          options={tabOptions(all.data?.counts)}
          active={NOTIFICATIONS.tabs[tab]}
          onChange={(label) => {
            setTab(TABS.find((t) => NOTIFICATIONS.tabs[t] === label) ?? "all");
          }}
        />
      </div>
      <div aria-busy={page.isPending} className="flex flex-col gap-[10px] p-[10px]">
        {body}
      </div>
    </Drawer>
  );
}

/** The `?ov=notifications` layer: the drawer, open, closed by removing it from the URL. */
function NotificationsOverlay({ close }: { close: () => void }): JSX.Element {
  const navigate = useNavigate();
  return (
    <NotificationsDrawer
      open
      onOpenChange={(next) => {
        if (!next) close();
      }}
      navigate={(to) => void navigate({ to })}
    />
  );
}

export const NOTIFICATIONS_OVERLAY = "notifications";

registerOverlay(NOTIFICATIONS_OVERLAY, {
  layer: "drawer",
  render: ({ close }) => <NotificationsOverlay close={close} />,
});
