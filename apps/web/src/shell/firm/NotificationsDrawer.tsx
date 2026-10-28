import type {
  DecisionOut,
  NotificationFeedOut,
  NotificationItemOut,
  NotificationPreferenceOut,
} from "@abacus/api-client";
import {
  acceptMutation,
  humanGateCountsOptions,
  listNotificationsQueryKey,
  notificationFeedOptions,
  notificationPreferencesOptions,
  notificationPreferencesQueryKey,
  readAllMutation,
  readNotificationMutation,
  reasonCodesOptions,
  sendBackMutation,
  setNotificationPreferencesMutation,
  undoDecisionMutation,
} from "@abacus/api-client/query";
import {
  AgentText,
  Button,
  DEFAULT_TZ,
  Dialog,
  Drawer,
  EmptyState,
  Fieldset,
  Icon,
  Pill,
  Popover,
  PopoverSection,
  Segmented,
  SkeletonRows,
  Toggle,
  ValueRow,
  cn,
  toast,
  useFormat,
} from "@abacus/ui";
import { type Query, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useSession } from "../../app-core/session";
import { feedHref, firmDayGroup, kindGlyph, notificationText } from "../notifications";
import { NOTIFICATIONS } from "./copy";
// The overlay registration lives beside the bell, so this module can be its own chunk; importing
// the drawer still registers it (TASK-1368).
export { NOTIFICATIONS_OVERLAY } from "./notifications-overlay";

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

/** The inline document decision's Undo window (SHL-04 frame 3; ADR-161 clause 6). */
export const UNDO_MS = 10_000;

/** A decision made from the drawer: its receipt, and its Undo while the window is open. */
export interface Decided {
  decision: DecisionOut;
  engagementId: string;
  receipt: string;
  undoable: boolean;
}

/** The inline pair a row may carry: a person's client upload, still pending, never an agent's. */
export function inlinePair(item: NotificationItemOut): boolean {
  return (
    item.actor.kind !== "agent" &&
    item.pending &&
    item.engagement_id !== null &&
    item.subject.type === "evidence_version" &&
    item.inline_actions.includes("accept_document") &&
    item.inline_actions.includes("return_document")
  );
}

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

/** The tab track's options: a count only where the server counts more than none. Approvals is
 * the C13 counts endpoint's total when it answers (I-01-T13; P-01 risk R4), the number HOME-01's
 * header and segmented badge show; the feed's own count only while that endpoint is off. */
export function tabOptions(
  counts: NotificationFeedOut["counts"] | undefined,
  gateTotal?: number,
): { label: string; count?: number }[] {
  return TABS.map((tab) => {
    const count =
      tab === "all"
        ? 0
        : tab === "approvals" && gateTotal !== undefined
          ? gateTotal
          : (counts?.[tab] ?? 0);
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
  decided,
  busy,
  onAccept,
  onReturn,
  onUndo,
}: {
  item: NotificationItemOut;
  onOpen: (item: NotificationItemOut) => void;
  decided?: Decided | undefined;
  busy?: boolean;
  onAccept?: (item: NotificationItemOut) => void;
  onReturn?: (item: NotificationItemOut) => void;
  onUndo?: (item: NotificationItemOut) => void;
}): JSX.Element {
  const f = useFormat();
  const unread = !item.read;
  const title = fact(item, "title") ?? notificationText(item.kind);
  const context = fact(item, "context");
  const pill = fact(item, "pill");
  const receipt = decided?.receipt ?? fact(item, "receipt");
  const button = rowButton(item);
  const agent = item.actor.kind === "agent";
  const pair = decided === undefined && inlinePair(item) && onAccept !== undefined;
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
            <span className="flex items-center gap-[6px]">
              <span data-receipt="" className="text-meta font-medium text-green-ink">
                {receipt}
              </span>
              {decided?.undoable === true && onUndo !== undefined && (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={busy}
                  onClick={() => {
                    onUndo(item);
                  }}
                >
                  {NOTIFICATIONS.undo}
                </Button>
              )}
            </span>
          )}
          {pair && (
            <span className="mt-[4px] flex gap-[6px]">
              <Button
                size="sm"
                variant="primary"
                disabled={busy}
                onClick={() => {
                  onAccept(item);
                }}
              >
                {NOTIFICATIONS.accept}
              </Button>
              <Button
                size="sm"
                variant="secondary"
                disabled={busy}
                onClick={() => {
                  onReturn?.(item);
                }}
              >
                {NOTIFICATIONS.returnAction}
              </Button>
            </span>
          )}
          {!pair && decided === undefined && button !== null && (
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
  // I-01-T13: the Approvals count is C13's, the same call HOME-01 makes (404 while it is off).
  const gates = useQuery({ ...humanGateCountsOptions(), enabled: open, retry: false });
  const page = useQuery({ ...query(tab), enabled: open, retry: false });
  const refresh = (): void => {
    void queryClient.invalidateQueries({ predicate: isFeed });
    void queryClient.invalidateQueries({ queryKey: listNotificationsQueryKey() });
  };
  const readOne = useMutation({ ...readNotificationMutation(), onSuccess: refresh });
  const readAll = useMutation({ ...readAllMutation(), onSuccess: refresh });
  const unread = all.data?.unread_count ?? 0;
  const f = useFormat();
  const viewer = useSession().user?.displayName ?? "";
  // The inline document decision (row d): Accept, or Return with a reason; 10 s to Undo.
  const [decided, setDecided] = useState<Record<string, Decided>>({});
  const [returning, setReturning] = useState<NotificationItemOut | null>(null);
  const accept = useMutation(acceptMutation());
  const sendBack = useMutation(sendBackMutation());
  const undo = useMutation(undoDecisionMutation());
  const busy = accept.isPending || sendBack.isPending || undo.isPending;
  const settle = (item: NotificationItemOut, decision: DecisionOut, accepted: boolean): void => {
    const at = f.time(now.toISOString());
    const receipt = accepted
      ? NOTIFICATIONS.accepted(viewer, at)
      : NOTIFICATIONS.returned(viewer, at);
    setDecided((d) => ({
      ...d,
      [item.id]: { decision, engagementId: item.engagement_id ?? "", receipt, undoable: true },
    }));
    if (!item.read) readOne.mutate({ path: { notification_id: item.id } });
    window.setTimeout(() => {
      setDecided((d) => {
        const held = d[item.id];
        return held === undefined ? d : { ...d, [item.id]: { ...held, undoable: false } };
      });
      refresh();
    }, UNDO_MS);
  };
  const failed = (): void => {
    toast.show({ kind: "error", text: NOTIFICATIONS.failed });
  };
  const path = (item: NotificationItemOut) => ({
    engagement_id: item.engagement_id ?? "",
    version_id: item.subject.id,
  });
  const acceptRow = (item: NotificationItemOut): void => {
    accept.mutate(
      { path: path(item), body: { note: null, seen_proposal: null } },
      {
        onSuccess: (decision) => {
          settle(item, decision, true);
        },
        onError: failed,
      },
    );
  };
  const returnRow = async (item: NotificationItemOut, reason: string, note: string) => {
    try {
      const decision = await sendBack.mutateAsync({
        path: path(item),
        body: { reason_code: reason, note: note === "" ? null : note, seen_proposal: null },
      });
      settle(item, decision, false);
    } catch {
      failed();
    }
  };
  const undoRow = (item: NotificationItemOut): void => {
    const held = decided[item.id];
    if (held === undefined) return;
    undo.mutate(
      { path: { engagement_id: held.engagementId, decision_id: held.decision.id } },
      {
        onSuccess: () => {
          setDecided((d) =>
            Object.fromEntries(Object.entries(d).filter(([id]) => id !== item.id)),
          );
          refresh();
        },
        onError: failed,
      },
    );
  };

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
              <Row
                key={item.id}
                item={item}
                onOpen={openRow}
                decided={decided[item.id]}
                busy={busy}
                onAccept={acceptRow}
                onReturn={setReturning}
                onUndo={undoRow}
              />
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
      footer={
        <>
          <span className="mr-auto text-dense text-ink-3">{NOTIFICATIONS.showing}</span>
          <NotificationSettings enabled={open} />
        </>
      }
    >
      <div className="sticky top-0 z-[1] flex h-[44px] flex-none items-center justify-center border-b-[0.5px] border-hair bg-card">
        <Segmented
          size="small"
          label={NOTIFICATIONS.tabsLabel}
          options={tabOptions(all.data?.counts, gates.data?.total)}
          active={NOTIFICATIONS.tabs[tab]}
          onChange={(label) => {
            setTab(TABS.find((t) => NOTIFICATIONS.tabs[t] === label) ?? "all");
          }}
        />
      </div>
      <div aria-busy={page.isPending} className="flex flex-col gap-[10px] p-[10px]">
        {body}
      </div>
      <ReturnDialog
        item={returning}
        onClose={() => {
          setReturning(null);
        }}
        onReturn={returnRow}
      />
    </Drawer>
  );
}

/** "Return…": a reason from the engagement's send-back codes, and a note the client sees. */
function ReturnDialog({
  item,
  onClose,
  onReturn,
}: {
  item: NotificationItemOut | null;
  onClose: () => void;
  onReturn: (item: NotificationItemOut, reason: string, note: string) => Promise<void>;
}): JSX.Element {
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const codes = useQuery({
    ...reasonCodesOptions({
      path: { engagement_id: item?.engagement_id ?? "", applies_to: "send_back" },
    }),
    enabled: item?.engagement_id != null,
  });
  const chosen = codes.data?.find((c) => c.code === reason);
  const noteNeeded = chosen?.requires_note === true && note.trim() === "";
  const described = item === null ? null : fact(item, "title");
  const close = (): void => {
    setReason("");
    setNote("");
    onClose();
  };
  return (
    <Dialog
      open={item !== null}
      onOpenChange={(next) => {
        if (!next) close();
      }}
      title={NOTIFICATIONS.returnTitle}
      {...(described === null ? {} : { description: described })}
      dirty={note.trim() !== "" || reason !== ""}
      action={
        <Button
          variant="primary"
          disabled={reason === "" || noteNeeded}
          onClick={() => {
            if (item === null) return;
            void onReturn(item, reason, note.trim()).then(close);
          }}
        >
          {NOTIFICATIONS.returnConfirm}
        </Button>
      }
    >
      <Fieldset flush>
        <ValueRow
          kind="select"
          label={NOTIFICATIONS.reason}
          options={[
            { value: "", label: NOTIFICATIONS.chooseReason },
            ...(codes.data ?? []).map((c) => ({ value: c.code, label: c.label })),
          ]}
          value={reason}
          onChange={setReason}
        />
        <ValueRow
          kind="paragraph"
          label={chosen?.requires_note === true ? NOTIFICATIONS.noteRequired : NOTIFICATIONS.note}
          value={note}
          onChange={setNote}
        />
      </Fieldset>
      <span className="text-meta text-ink-3">{NOTIFICATIONS.noteToClient}</span>
    </Dialog>
  );
}

/** The footer's "Notification settings" menu (R2): each kind with In Accrued and Email toggles. */
export function NotificationSettings({ enabled }: { enabled: boolean }): JSX.Element {
  const queryClient = useQueryClient();
  const prefs = useQuery({ ...notificationPreferencesOptions(), enabled, retry: false });
  const [items, setItems] = useState<NotificationPreferenceOut[]>([]);
  useEffect(() => {
    if (prefs.data !== undefined) setItems(prefs.data.items);
  }, [prefs.data]);
  const save = useMutation({
    ...setNotificationPreferencesMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: notificationPreferencesQueryKey() });
    },
    onError: () => {
      toast.show({ kind: "error", text: NOTIFICATIONS.failed });
    },
  });
  const change = (kind: string, channel: "in_app" | "email", on: boolean): void => {
    const next = items.map((p) => (p.kind === kind ? { ...p, [channel]: on } : p));
    setItems(next);
    save.mutate({ body: { items: next } });
  };
  return (
    <Popover
      label={NOTIFICATIONS.settings}
      align="end"
      width={300}
      trigger={
        <Button size="sm" variant="ghost">
          {NOTIFICATIONS.settings}
        </Button>
      }
    >
      <PopoverSection>
        {items.map((p) => {
          const label = NOTIFICATIONS.kinds[p.kind] ?? p.kind;
          return (
            <div key={p.kind} className="flex items-center gap-[8px] px-[8px] py-[6px]">
              <span className="flex min-w-0 flex-1 flex-col">
                <span className="text-body text-ink">{label}</span>
                <span className="text-meta text-ink-3">{NOTIFICATIONS.settingsChannels}</span>
              </span>
              <Toggle
                size="small"
                label={`${label} · ${NOTIFICATIONS.inApp}`}
                checked={p.in_app}
                disabled={save.isPending}
                onChange={(on) => {
                  change(p.kind, "in_app", on);
                }}
              />
              <Toggle
                size="small"
                label={`${label} · ${NOTIFICATIONS.email}`}
                checked={p.email}
                disabled={save.isPending}
                onChange={(on) => {
                  change(p.kind, "email", on);
                }}
              />
            </div>
          );
        })}
      </PopoverSection>
    </Popover>
  );
}
