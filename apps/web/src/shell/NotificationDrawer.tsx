import type { NotificationOut } from "@abacus/api-client";
import { listNotifications } from "@abacus/api-client";
import {
  listEngagementsOptions,
  listNotificationsQueryKey,
  readAllMutation,
  readNotificationMutation,
} from "@abacus/api-client/query";
import { Alert, Button, Drawer, EmptyState, Skeleton, useFormat, useNow } from "@abacus/ui";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "@tanstack/react-router";
import { type JSX, useState } from "react";
import { errorMessage } from "../api";
import {
  type Category,
  categoryOf,
  dayGroup,
  notificationHref,
  notificationText,
} from "./notifications";

// SPEC-305 (TASK-306): the notifications drawer (SHL-04, overlay O2, 480 wide). Tabs by kind,
// day groups, the engagement each concerns, unread only, and pages back. Opening one marks it
// read and goes to its page. Nothing is approved from here.

const PAGE = 50;

const TABS: [Category | "all", string][] = [
  ["all", "All"],
  ["needs_you", "Needs you"],
  ["mentions", "Mentions"],
  ["client", "Client activity"],
];

export function NotificationDrawer({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}): JSX.Element {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const f = useFormat();
  const now = useNow();
  const [tab, setTab] = useState<Category | "all">("all");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const pages = useInfiniteQuery({
    queryKey: ["notificationsDrawer", unreadOnly],
    initialPageParam: undefined as string | undefined,
    queryFn: async ({ pageParam }) => {
      const { data } = await listNotifications({
        query: {
          limit: PAGE,
          unread: unreadOnly,
          ...(pageParam === undefined ? {} : { before: pageParam }),
        },
        throwOnError: true,
      });
      return data;
    },
    getNextPageParam: (last) =>
      last.items.length < PAGE ? undefined : last.items[last.items.length - 1]?.created_at,
    enabled: open,
    retry: false,
  });
  const engagements = useQuery({ ...listEngagementsOptions(), enabled: open, retry: false });
  const names = new Map(
    (engagements.data ?? []).map((e) => [e.id, `${e.client_name} · ${e.name}`]),
  );
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: listNotificationsQueryKey() });
    void queryClient.invalidateQueries({ queryKey: ["notificationsDrawer"] });
  };
  const readOne = useMutation({ ...readNotificationMutation(), onSuccess: refresh });
  const readAll = useMutation({ ...readAllMutation(), onSuccess: refresh });
  const all = pages.data?.pages.flatMap((p) => p.items) ?? [];
  const unread = pages.data?.pages[0]?.unread_count ?? 0;
  const counts = new Map<string, number>();
  for (const n of all)
    if (!n.read) counts.set(categoryOf(n.kind), (counts.get(categoryOf(n.kind)) ?? 0) + 1);
  const shown = all.filter((n) => tab === "all" || categoryOf(n.kind) === tab);
  const groups: [string, NotificationOut[]][] = [];
  for (const n of shown) {
    const label = dayGroup(n.created_at, now);
    const last = groups[groups.length - 1];
    if (last?.[0] === label) last[1].push(n);
    else groups.push([label, [n]]);
  }
  const openOne = (n: NotificationOut): void => {
    if (!n.read) readOne.mutate({ path: { notification_id: n.id } });
    const href = notificationHref(n, "firm");
    if (href === null) return;
    onOpenChange(false);
    void navigate({ to: href.to, ...(href.hash !== undefined ? { hash: href.hash } : {}) });
  };
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title="Notifications"
      meta={
        <Button
          size="sm"
          variant="ghost"
          disabled={unread === 0 || readAll.isPending}
          onClick={() => {
            readAll.mutate({});
          }}
        >
          Mark all read
        </Button>
      }
    >
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <div
          role="tablist"
          aria-label="Kinds"
          className="flex gap-0.5 rounded-tile bg-nested p-0.5"
        >
          {TABS.map(([key, label]) => {
            const n = key === "all" ? unread : (counts.get(key) ?? 0);
            return (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={tab === key}
                onClick={() => {
                  setTab(key);
                }}
                className={`flex items-center gap-1.5 rounded-[var(--radius-control)] px-2.5 py-1 text-[12.5px] ${tab === key ? "bg-card font-medium shadow-e1" : "text-ink-2"}`}
              >
                {label}
                {n > 0 && (
                  <span className="rounded-[var(--radius-badge)] bg-espresso px-1 text-[10.5px] text-on-dark tabular-nums">
                    {n}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <span className="flex-1" />
        <label className="flex items-center gap-1.5 text-[12.5px] text-ink-2">
          <input
            type="checkbox"
            checked={unreadOnly}
            onChange={(e) => {
              setUnreadOnly(e.target.checked);
            }}
          />
          Unread only
        </label>
      </div>
      {pages.isPending ? (
        <Skeleton className="h-40" />
      ) : pages.isError ? (
        <Alert title="Couldn't load notifications">{errorMessage(pages.error)}</Alert>
      ) : shown.length === 0 ? (
        <EmptyState title={tab === "all" && !unreadOnly ? "You're all caught up" : "Nothing here"}>
          {tab === "needs_you" ? "Nothing is waiting for you." : undefined}
        </EmptyState>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map(([label, items]) => (
            <section key={label} aria-label={label}>
              <h3 className="mb-1 px-1 text-[11px] font-medium tracking-[0.02em] text-ink-3 uppercase">
                {label}
              </h3>
              <ul className="flex flex-col overflow-hidden rounded-nested bg-card shadow-e1">
                {items.map((n) => {
                  const text = notificationText(n.kind);
                  const where = n.engagement_id === null ? null : names.get(n.engagement_id);
                  return (
                    <li key={n.id} className="border-b-[0.5px] border-hair last:border-b-0">
                      <button
                        type="button"
                        onClick={() => {
                          openOne(n);
                        }}
                        className="flex w-full items-start gap-2.5 px-3 py-2.5 text-left hover:bg-sel-bg"
                      >
                        <span
                          aria-hidden="true"
                          className={`mt-1.5 size-2 shrink-0 rounded-full ${n.read ? "bg-transparent" : "bg-espresso"}`}
                        />
                        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
                          <span className={`text-[13px] ${n.read ? "text-ink-2" : "font-medium"}`}>
                            {text}
                          </span>
                          <span className="truncate text-[11.5px] text-ink-3">
                            {[where, f.time(n.created_at)].filter(Boolean).join(" · ")}
                          </span>
                        </span>
                        {!n.read && <span className="sr-only">Unread</span>}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
          {pages.hasNextPage && (
            <Button
              size="sm"
              variant="secondary"
              className="self-center"
              disabled={pages.isFetchingNextPage}
              onClick={() => void pages.fetchNextPage()}
            >
              Load older
            </Button>
          )}
        </div>
      )}
    </Drawer>
  );
}
