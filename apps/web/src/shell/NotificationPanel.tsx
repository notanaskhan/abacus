import {
  listNotificationsOptions,
  listNotificationsQueryKey,
  readAllMutation,
  readNotificationMutation,
} from "@abacus/api-client/query";
import { Alert, Button, EmptyState, Spinner } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { JSX } from "react";
import { errorMessage } from "../api";
import { notificationHref, notificationText } from "./notifications";

const POLL_MS = 60_000;

/** The unread count for the rail's bell; polled, and refreshed when the window regains focus. */
export function useUnreadCount(): number {
  const page = useQuery({
    ...listNotificationsOptions({ query: { limit: 50 } }),
    refetchInterval: POLL_MS,
  });
  return page.data?.unread_count ?? 0;
}

export function NotificationPanel({ onClose }: { onClose: () => void }): JSX.Element {
  const queryClient = useQueryClient();
  const page = useQuery(listNotificationsOptions({ query: { limit: 50 } }));
  const refresh = (): void => {
    void queryClient.invalidateQueries({ queryKey: listNotificationsQueryKey() });
  };
  const readOne = useMutation({ ...readNotificationMutation(), onSuccess: refresh });
  const readAll = useMutation({ ...readAllMutation(), onSuccess: refresh });

  return (
    <aside
      aria-label="Notifications"
      className="flex w-full flex-col gap-3 border-line bg-surface p-4 sm:w-96 sm:border-l"
    >
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-lg">Notifications</h2>
        <div className="flex gap-1">
          <Button
            size="sm"
            variant="ghost"
            disabled={(page.data?.unread_count ?? 0) === 0 || readAll.isPending}
            onClick={() => {
              readAll.mutate({});
            }}
          >
            Mark all read
          </Button>
          <Button size="sm" variant="outline" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
      {page.isPending ? (
        <Spinner label="Loading notifications…" />
      ) : page.isError ? (
        <Alert title="Couldn't load notifications">{errorMessage(page.error)}</Alert>
      ) : page.data.items.length === 0 ? (
        <EmptyState title="You're all caught up" />
      ) : (
        <ul className="flex flex-col divide-y divide-line">
          {page.data.items.map((n) => {
            const href = notificationHref(n);
            const text = notificationText(n.kind);
            return (
              <li key={n.id} className="flex items-start gap-3 py-3">
                <span
                  aria-hidden="true"
                  className={`mt-1.5 size-2 shrink-0 rounded-full ${n.read ? "bg-line" : "bg-accent"}`}
                />
                <div className="flex flex-1 flex-col gap-1 text-sm">
                  {href === null ? (
                    <span className={n.read ? "text-muted" : "font-semibold"}>{text}</span>
                  ) : (
                    <Link
                      to={href}
                      onClick={onClose}
                      className={
                        n.read ? "text-muted hover:underline" : "font-semibold hover:underline"
                      }
                    >
                      {text}
                    </Link>
                  )}
                  <time dateTime={n.created_at} className="text-xs text-muted">
                    {new Date(n.created_at).toLocaleString()}
                  </time>
                </div>
                {!n.read && (
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Mark read: ${text}`}
                    onClick={() => {
                      readOne.mutate({ path: { notification_id: n.id } });
                    }}
                  >
                    Mark read
                  </Button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </aside>
  );
}
