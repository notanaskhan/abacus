import type {
  ActivityEventOut,
  BinderOut,
  BinderRequestRowOut,
  ClientPreviewItemOut,
  WaiveIn,
} from "@abacus/api-client";
import {
  Button,
  type CockpitDock,
  DASH,
  DEFAULT_TZ,
  Dialog,
  Fieldset,
  Icon,
  KvRowView,
  type MenuItem,
  OverviewCard,
  Pill,
  type PillVariant,
  ProgressBar,
  RecordCockpit,
  RecordHeader,
  RequestSection,
  SheetModal,
  Tabsbar,
  Toggle,
  type ToolbarProps,
  type ViewState,
  ValueRow,
  count,
  date,
  dateTime,
  isoDate,
  registryWord,
  toast,
} from "@abacus/ui";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOverlays } from "../../app-core/overlay-host";
import { useSession } from "../../app-core/session";
import {
  BinderRequestRow,
  CategoryList,
  type FollowUpSelection,
  FollowUpSheet,
  allows,
  categoryIcon,
  isSatisfied,
  useBinder,
  useBinderActivity,
  useBinderContext,
  useBinderLive,
  useBinderRequests,
  useBinderWrites,
  useClientPreview,
  useRequestDetail,
  useStaffNames,
} from "../../domain/requests";
import { COPY } from "./copy";

// BND-02 · Binder builder & tracker (P-06-T12; docs/screens/BND-02.md). T2 with the Request dock
// over `GET /v1/binders/{id}` and its rows: the rail (overview card, key values, the nine
// categories with olive ticks), the publish bar, request rows with the Eye toggle and the ··· menu
// (Edit, Waive, Return to client, Delete), the dock for the selected request, "Preview as client",
// the Requests and Activity tabs, and the live poll for "Uploading n files…" and "Waiting n" while
// the page is visible. Each artboard is its data (fixtures/scenarios/BND-02.ts):
//
//   a  Feld, published, 5 of 7    b  the TY2026 Draft    c  Complete, marked done by Claire Feld
//   d  Thornbury, 3 overdue       e  Paul Thornbury's Ignore    f  the K-1 hidden from the client
//
// g and the R2 rows (Linked (n), the screening glyph, the dock ScreeningCard) are P-06-T22's.

const DAY_MS = 86_400_000;

export type BinderTab = "requests" | "activity";

export interface BND02Props {
  binderId: string;
  /** The request the dock shows (`?request=`); null opens the first. */
  request: string | null;
  onRequest: (id: string | null) => void;
  tab: BinderTab;
  onTab: (tab: BinderTab) => void;
  /** The gallery's toolbar and window; the routed screen draws inside the workspace's shell. */
  toolbar?: ToolbarProps;
  frame?: boolean;
  /** "‹ All Binders": the route opens BND-01. */
  onBack?: () => void;
}

/** "From 2024 return" names the year of the source return the binder was carried from. */
function sourceYear(binder: BinderOut): string | null {
  const ref = binder.prior_year_source_ref ?? "";
  const year = /^(\d{4}) return/.exec(ref)?.[1];
  return year ?? null;
}

/** "2025 return" from "2025 return (CCH Axcess)". */
function sourceName(binder: BinderOut): string | null {
  const ref = binder.prior_year_source_ref ?? "";
  return /^(\d{4} return)/.exec(ref)?.[1] ?? null;
}

const STATUS_TONE: Readonly<Record<BinderOut["status"], PillVariant>> = {
  draft: "neutral",
  published: "amber",
  unpublished: "muted",
  complete: "green-tint",
  closed: "soon",
};

export function BND02({
  binderId,
  request,
  onRequest,
  tab,
  onTab,
  toolbar,
  frame = false,
  onBack,
}: BND02Props): JSX.Element {
  const now = useNow();
  const overlays = useOverlays();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const names = useStaffNames();
  const binderQ = useBinder(binderId);
  const rowsQ = useBinderRequests(binderId);
  const binder = binderQ.data;
  const rows = rowsQ.data?.items ?? [];
  const live = useBinderLive(binderId, binder?.status === "published");
  const preview = useClientPreview(binderId);
  const activity = useBinderActivity(binderId, tab === "activity");
  const context = useBinderContext(binder?.engagement_id);
  const writes = useBinderWrites(binderId, binder?.engagement_id);
  const [category, setCategory] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [followUp, setFollowUp] = useState<FollowUpSelection | null>(null);
  const canFollowUp = binder !== undefined && allows(binder, "follow_up.draft");
  const person = useSession().user?.displayName ?? "";
  const [publishing, setPublishing] = useState(false);
  const [unpublishing, setUnpublishing] = useState(false);
  const [waiving, setWaiving] = useState<BinderRequestRowOut | null>(null);
  const [returning, setReturning] = useState<BinderRequestRowOut | null>(null);

  const selected = rows.find((r) => r.id === request) ?? rows[0] ?? null;
  const day = (iso: string | null | undefined): string =>
    iso == null ? DASH : date(iso, { now, tz });
  const year = binder === undefined ? null : sourceYear(binder);
  const today = isoDate(now, tz);

  let state: ViewState;
  if (binderQ.isError || rowsQ.isError) {
    state = {
      kind: "error",
      retry: () => {
        void binderQ.refetch();
        void rowsQ.refetch();
      },
    };
  } else if (binder === undefined || rowsQ.data === undefined) state = { kind: "loading" };
  else if (rows.length === 0) state = { kind: "empty" };
  else state = { kind: "ready" };

  const run = async (work: () => Promise<unknown>, done: string): Promise<void> => {
    try {
      await work();
      toast.show({ kind: "success", text: done });
    } catch {
      toast.show({ kind: "error", text: COPY.toasts.failed });
    }
  };

  const workItem = context.workItems.find((w) => w.id === binder?.work_item_id);
  const clientName = context.engagement?.client_name;
  const contextLine =
    clientName === undefined || workItem === undefined
      ? clientName
      : `${clientName} · ${workItem.name}`;
  const statusLabel = binder === undefined ? "" : registryWord("binder", binder.status).label;

  const header = (
    <RecordHeader
      variant="settings"
      title={binder?.name ?? ""}
      {...(contextLine === undefined ? {} : { context: contextLine })}
      state={statusLabel}
      {...(binder === undefined ? {} : { stateTone: STATUS_TONE[binder.status] })}
      backLabel={COPY.back}
      {...(onBack === undefined ? {} : { onBack })}
      right={
        // TAX-03 is planned (T-02): the tooltip names it.
        <Button variant="secondary" size="sm" disabled title={COPY.openReturnHint}>
          {COPY.openReturn}
          <Icon name="chevron-right" size={12} className="text-ink-3" />
        </Button>
      }
    />
  );

  const tabs = (
    <Tabsbar
      label={COPY.tabs.label}
      options={[{ label: COPY.tabs.requests, count: rows.length }, { label: COPY.tabs.activity }]}
      active={tab === "activity" ? COPY.tabs.activity : COPY.tabs.requests}
      onChange={(label) => {
        onTab(label === COPY.tabs.activity ? "activity" : "requests");
      }}
    />
  );

  // ---- rail --------------------------------------------------------------------------------
  const recipients = (binder?.recipients ?? []).map((r) => r.name);
  const open = binder === undefined ? 0 : (binder.total_count ?? 0) - (binder.done_count ?? 0);
  const markedBy = binder?.recipients?.find((r) => r.contact_id === binder.marked_done_by)?.name;
  const publishedBy = binder?.published_by == null ? undefined : names.get(binder.published_by);
  const kv =
    binder === undefined
      ? []
      : [
          {
            id: "published",
            label: COPY.rail.published,
            value:
              binder.published_at == null
                ? COPY.rail.notYet
                : [date(binder.published_at, { now, tz, withYear: true }), publishedBy]
                    .filter((v) => v !== undefined)
                    .join(" · "),
          },
          ...(binder.prior_year_source_ref == null
            ? []
            : [
                {
                  id: "created_from",
                  label: COPY.rail.createdFrom,
                  value: binder.prior_year_source_ref,
                  kind: "link" as const,
                },
              ]),
          { id: "visible_to", label: COPY.rail.visibleTo, value: recipients.join(" · ") || DASH },
          {
            id: "marked_done",
            label: COPY.rail.markedDone,
            value:
              binder.marked_done_at == null
                ? binder.status === "draft"
                  ? DASH
                  : COPY.rail.notYetOpen(count(open))
                : [dateTime(binder.marked_done_at, { tz }), markedBy]
                    .filter((v) => v !== undefined)
                    .join(" · "),
          },
          ...(binder.follow_up_override == null
            ? []
            : [
                {
                  id: "reminders",
                  label: COPY.rail.reminders,
                  value: COPY.rail.every(count(binder.follow_up_override.every_days)),
                },
              ]),
          ...(binder.template_ref == null
            ? []
            : [
                {
                  id: "template",
                  label: COPY.rail.template,
                  value: binder.template_ref,
                  kind: "link" as const,
                },
              ]),
        ];
  const activeCategory = category ?? selected?.category_id ?? null;
  const rail = (
    <section
      aria-label={COPY.rail.title}
      className="pane flex min-h-0 flex-1 flex-col overflow-hidden"
    >
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="text-pane font-medium tracking-[-0.012em]">{COPY.rail.title}</h2>
      </div>
      <div className="min-h-0 flex-1 overflow-auto">
        {binder !== undefined && (
          <>
            <OverviewCard
              icon="folder-open"
              title={binder.name}
              sub={contextLine ?? ""}
              state={statusLabel}
            />
            <div className="flex flex-col">
              {kv.map((row) => (
                <KvRowView key={row.id} row={row} />
              ))}
            </div>
            <CategoryList
              title={COPY.rail.categories}
              categories={binder.categories ?? []}
              openLabel={(n) => COPY.rail.open(count(n))}
              nothingLabel={COPY.rail.nothing}
              selected={activeCategory}
              onSelect={(id) => {
                setCategory(id);
                document
                  .querySelector(`[data-section="${id}"]`)
                  ?.scrollIntoView({ block: "start", behavior: "smooth" });
              }}
            />
          </>
        )}
      </div>
    </section>
  );

  // ---- canvas ------------------------------------------------------------------------------
  const overdue = rows.filter((r) => r.overdue && r.client_ignored_at == null).length;
  const ignored = rows.filter((r) => r.client_ignored_at != null).length;
  const canPublish = allows(binder, "binder.publish");
  const reminderPrimary = overdue > 0;
  // BND-02 d: "Send reminder…" drafts for the open items only (Requested or Returned, visible to
  // the client); the follow-up sheet lists each once (P-06-T16).
  const openIds = rows
    .filter((r) => (r.status === "requested" || r.status === "returned") && r.client_visible)
    .map((r) => r.id);
  const actions = (
    <span className="flex items-center gap-[8px]">
      <Button
        variant="secondary"
        size="sm"
        title={COPY.canvas.previewHint}
        onClick={() => {
          setPreviewing(true);
        }}
      >
        <Icon name="eye" size={14} />
        {COPY.canvas.preview}
      </Button>
      <Button
        variant={reminderPrimary ? "primary" : "secondary"}
        size="sm"
        disabled={!canFollowUp || openIds.length === 0}
        onClick={() => {
          setFollowUp({ kind: "requests", requestItemIds: openIds });
        }}
      >
        {COPY.canvas.sendReminder}
      </Button>
      <Button
        variant={reminderPrimary ? "secondary" : "primary"}
        size="sm"
        disabled={binder === undefined || !allows(binder, "binder.update")}
        title={COPY.canvas.newRequestHint}
        onClick={() => {
          overlays.open("request", "new", binderId);
        }}
      >
        <Icon name="plus" size={14} />
        {COPY.canvas.newRequest}
      </Button>
    </span>
  );

  const bar =
    binder === undefined ? null : (
      <PublishBar
        binder={binder}
        ignored={ignored}
        overdue={overdue}
        markedBy={markedBy}
        day={day}
        from={sourceName(binder)}
        canPublish={canPublish}
        onPublish={() => {
          setPublishing(true);
        }}
        onUnpublish={() => {
          setUnpublishing(true);
        }}
        tz={tz}
      />
    );

  const menuFor = (row: BinderRequestRowOut): MenuItem[][] => {
    const items: MenuItem[] = [
      // SHL-14 (P-06-T13): the composer drawer, `?ov=request:<id>:<binderId>`.
      {
        label: COPY.row.edit,
        hint: COPY.row.editHint,
        disabled: !allows(row, "request_item.update"),
        onSelect: () => {
          overlays.open("request", row.id, binderId);
        },
      },
    ];
    if (row.status !== "received" && row.status !== "not_applicable" && row.status !== "draft") {
      items.push({
        label: COPY.row.waive,
        opensDialog: true,
        disabled: !allows(row, "request_item.waive"),
        onSelect: () => {
          setWaiving(row);
        },
      });
    }
    if (row.client_ignored_at != null || row.status === "received") {
      items.push({
        label: COPY.row.returnToClient,
        opensDialog: true,
        disabled: !allows(row, "request_item.return"),
        onSelect: () => {
          setReturning(row);
        },
      });
    }
    const remove: MenuItem = {
      label: COPY.row.delete,
      danger: true,
      // Only a never-sent Draft can go (C5: 409 request_already_sent).
      disabled: row.status !== "draft" || !allows(row, "request_item.update"),
      onSelect: () => {
        void run(() => writes.remove(row.id), COPY.toasts.deleted);
      },
    };
    return [items, [remove]];
  };

  const sections = (binder?.categories ?? [])
    .slice()
    .sort((a, b) => a.position - b.position)
    .map((c) => ({ category: c, rows: rows.filter((r) => r.category_id === c.id) }))
    .filter((s) => s.rows.length > 0);

  const body = (
    <div className="flex flex-col gap-[8px] p-[8px]">
      {sections.map(({ category: c, rows: mine }) => (
        <div key={c.id} data-section={c.id}>
          <RequestSection title={c.name} icon={categoryIcon(c.name)}>
            <span className="sr-only">
              {COPY.canvas.sectionCount(count(c.done_count), count(c.total_count))}
            </span>
            {mine.map((row) => {
              const due = row.due_on ?? null;
              const lateDays =
                row.overdue && due !== null
                  ? Math.round((Date.parse(today) - Date.parse(due)) / DAY_MS)
                  : 0;
              return (
                <BinderRequestRow
                  key={row.id}
                  row={row}
                  live={live.byItem.get(row.id)}
                  due={due === null ? DASH : date(due, { now, tz })}
                  selected={selected?.id === row.id}
                  onSelect={() => {
                    onRequest(row.id);
                  }}
                  canChangeVisibility={allows(row, "request_item.update")}
                  onVisible={(visible) => {
                    void run(
                      () => writes.setVisible(row.id, visible),
                      visible ? COPY.toasts.shown : COPY.toasts.hidden,
                    );
                  }}
                  menu={menuFor(row)}
                  words={{
                    requested: COPY.row.requested,
                    notPublished: COPY.row.notPublished,
                    firmDraft: COPY.row.k1Draft,
                    ignored: COPY.row.ignored,
                    internalOnly: COPY.row.internalOnly,
                    waiting: COPY.row.waiting,
                    waitingHint: COPY.row.waitingHint,
                    uploading: COPY.row.uploading,
                    late:
                      lateDays > 0 && due !== null
                        ? COPY.row.late(date(due, { now, tz }), lateDays)
                        : null,
                    requestedOn:
                      row.requested_at == null
                        ? null
                        : COPY.row.requestedOn(date(row.requested_at, { now, tz })),
                    tag:
                      row.source_tag === "prior_year" && year !== null
                        ? COPY.row.fromPriorYear(year)
                        : null,
                    ignoreReason:
                      row.client_ignore_reason == null
                        ? null
                        : COPY.ignoreReasons[row.client_ignore_reason],
                    visibleLabel: row.client_visible
                      ? COPY.row.visibleOn(row.title)
                      : COPY.row.visibleOff(row.title),
                    menuLabel: COPY.row.menu(row.title),
                  }}
                />
              );
            })}
          </RequestSection>
        </div>
      ))}
    </div>
  );

  const canvas =
    tab === "activity"
      ? {
          title: COPY.tabs.activity,
          state:
            activity.data === undefined
              ? ({ kind: "loading" } as ViewState)
              : activity.data.items.length === 0
                ? ({ kind: "empty" } as ViewState)
                : ({ kind: "ready" } as ViewState),
          empty: { title: COPY.activity.empty },
          children: <ActivityList events={activity.data?.items ?? []} names={names} tz={tz} />,
        }
      : {
          title: COPY.canvas.title,
          actions,
          well: true,
          state,
          ...(bar === null || state.kind !== "ready" ? {} : { controls: bar }),
          children: body,
        };

  const dock: CockpitDock = {
    view: "Viewer",
    views: ["Viewer"],
    title: COPY.dock.title,
    children:
      selected === null || binder === undefined ? (
        <p className="p-[14px] text-dense text-ink-3">{COPY.dock.empty}</p>
      ) : (
        <RequestDock
          key={selected.id}
          row={selected}
          binder={binder}
          categoryName={binder.categories?.find((c) => c.id === selected.category_id)?.name}
          preview={preview.data?.items.find((i) => i.id === selected.id)}
          year={year}
          tz={tz}
          names={names}
          onVisible={(visible) => {
            void run(
              () => writes.setVisible(selected.id, visible),
              visible ? COPY.toasts.shown : COPY.toasts.hidden,
            );
          }}
          onWaive={() => {
            setWaiving(selected);
          }}
          onReturn={() => {
            setReturning(selected);
          }}
          {...(canFollowUp
            ? {
                onRemind: () => {
                  setFollowUp({ kind: "requests", requestItemIds: [selected.id] });
                },
              }
            : {})}
        />
      ),
  };

  return (
    <div data-screen="BND-02" className="flex min-h-0 flex-1 flex-col">
      <RecordCockpit
        {...(toolbar === undefined ? {} : { toolbar })}
        frame={frame}
        {...(frame ? { height: 860 } : {})}
        header={header}
        tabs={tabs}
        rail={rail}
        canvas={canvas}
        dock={dock}
      />
      <FollowUpSheet
        selection={followUp}
        person={person}
        onClose={() => {
          setFollowUp(null);
        }}
      />
      <ClientPreviewSheet
        open={previewing}
        onOpenChange={setPreviewing}
        items={preview.data?.items ?? []}
      />
      <PublishDialog
        open={publishing}
        people={recipients.join(" · ")}
        onClose={() => {
          setPublishing(false);
        }}
        onPublish={async () => {
          try {
            await writes.publish();
            toast.undoable({
              text: COPY.toasts.published(binder?.name ?? ""),
              undo: () => {
                void writes.undoPublish();
              },
            });
          } catch (error) {
            const detail = (error as { detail?: unknown } | null)?.detail;
            toast.show({
              kind: "error",
              text: detail === "binder_gate_unmet" ? COPY.toasts.gate : COPY.toasts.failed,
            });
          }
        }}
      />
      <ReasonDialog
        open={unpublishing}
        title={COPY.dialogs.unpublishTitle}
        label={COPY.dialogs.reason}
        confirm={COPY.dialogs.unpublish}
        onClose={() => {
          setUnpublishing(false);
        }}
        onConfirm={(reason) =>
          run(() => writes.unpublish(reason), COPY.toasts.unpublished(binder?.name ?? ""))
        }
      />
      <WaiveDialog
        row={waiving}
        onClose={() => {
          setWaiving(null);
        }}
        onWaive={(row, body) => run(() => writes.waive(row.id, body), COPY.toasts.waived)}
      />
      <ReasonDialog
        open={returning !== null}
        title={COPY.dialogs.returnTitle}
        {...(returning === null ? {} : { description: returning.title })}
        label={COPY.dialogs.returnNote}
        confirm={COPY.dialogs.returnIt}
        onClose={() => {
          setReturning(null);
        }}
        onConfirm={(note) => {
          const row = returning;
          if (row === null) return Promise.resolve();
          return run(() => writes.returnToClient(row.id, note), COPY.toasts.returned);
        }}
      />
    </div>
  );
}

/** The 40 publish bar: the sentence, the overdue count, the 64 × 3 bar and the lifecycle action. */
function PublishBar({
  binder,
  ignored,
  overdue,
  markedBy,
  day,
  from,
  canPublish,
  onPublish,
  onUnpublish,
  tz,
}: {
  binder: BinderOut;
  ignored: number;
  overdue: number;
  markedBy: string | undefined;
  day: (iso: string | null | undefined) => string;
  from: string | null;
  canPublish: boolean;
  onPublish: () => void;
  onUnpublish: () => void;
  tz: string;
}): JSX.Element {
  const done = binder.done_count ?? 0;
  const total = binder.total_count ?? 0;
  let sentence: string;
  if (binder.status === "draft") sentence = COPY.bar.draft(count(total), from);
  else if (binder.status === "complete" && binder.marked_done_at != null) {
    sentence = COPY.bar.complete(
      markedBy ?? DASH,
      dateTime(binder.marked_done_at, { tz }).replace(/^(\w+ \d+), \d{4}/, "$1,"),
      count(done),
      count(total),
    );
  } else if (binder.status === "unpublished") {
    sentence = COPY.bar.unpublished(day(binder.unpublished_at), binder.unpublish_reason ?? "");
  } else if (binder.status === "closed") sentence = COPY.bar.closed(day(binder.closed_at));
  else {
    sentence = COPY.bar.published(
      day(binder.published_at),
      count(done),
      count(total),
      count(total - done),
      ignored > 0 ? count(ignored) : null,
    );
  }
  return (
    <div data-part="publish-bar" className="flex min-w-0 flex-1 items-center gap-[10px]">
      <span className="min-w-0 truncate text-dense text-ink-2">{sentence}</span>
      {overdue > 0 && (
        <Pill variant="red-tint" size="sm">
          {COPY.bar.overdue(count(overdue))}
        </Pill>
      )}
      {binder.status !== "draft" && (
        <span title={COPY.bar.progress(count(done), count(total))}>
          <ProgressBar
            done={done}
            total={total}
            tone={done === total ? "ink" : "amber"}
            left=""
            className="w-[64px]"
          />
        </span>
      )}
      <span className="ml-auto flex items-center">
        {binder.status === "draft" || binder.status === "unpublished" ? (
          <Button variant="primary" size="sm" disabled={!canPublish} onClick={onPublish}>
            {COPY.bar.publish}
          </Button>
        ) : binder.status === "published" ? (
          <Button variant="ghost" size="sm" disabled={!canPublish} onClick={onUnpublish}>
            {COPY.bar.unpublish}
          </Button>
        ) : null}
      </span>
    </div>
  );
}

/** The dock for the selected request: "Document Request" and "Uploaded Document". */
function RequestDock({
  row,
  binder,
  categoryName,
  preview,
  year,
  tz,
  names,
  onVisible,
  onWaive,
  onReturn,
  onRemind,
}: {
  row: BinderRequestRowOut;
  binder: BinderOut;
  categoryName: string | undefined;
  preview: ClientPreviewItemOut | undefined;
  year: string | null;
  tz: string;
  names: ReadonlyMap<string, string>;
  onVisible: (visible: boolean) => void;
  onWaive: () => void;
  onReturn: () => void;
  /** "Send reminder…" for this one request (P-06-T16); absent when the person may not draft. */
  onRemind?: () => void;
}): JSX.Element {
  const now = useNow();
  const detail = useRequestDetail(binder.engagement_id, row.id);
  const sent = detail.activity.find((e) => e.event_type === "request_item.sent");
  const sender = sent?.actor_user_id == null ? undefined : names.get(sent.actor_user_id);
  const first = detail.uploads[0];
  const ignored = row.client_ignored_at != null;
  const kv = (label: string, value: ReactNode, sub?: string): JSX.Element => (
    <div className="flex min-h-[35px] items-start gap-[12px] px-[14px] py-[8px] hairline-t text-body">
      <span className="flex-none text-ink-2">{label}</span>
      <span className="ml-auto flex min-w-0 flex-col items-end text-right text-ink">
        <span className="min-w-0">{value}</span>
        {sub !== undefined && <span className="text-meta text-ink-3">{sub}</span>}
      </span>
    </div>
  );
  const band = (title: string): JSX.Element => (
    <div className="flex h-[36px] items-center gap-[8px] bg-row-hover px-[14px] hairline-t text-section font-medium">
      <Icon name="file-text" size={14} className="text-ink-3" />
      {title}
    </div>
  );
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        {band(COPY.dock.requestCard)}
        {kv(COPY.dock.request, row.title)}
        {kv(COPY.dock.category, categoryName ?? DASH)}
        <div className="flex min-h-[35px] items-center px-[14px] hairline-t text-body">
          <span className="text-ink-2">{COPY.dock.visible}</span>
          <Toggle
            className="ml-auto"
            size="small"
            label={COPY.dock.visible}
            checked={row.client_visible}
            disabled={!allows(row, "request_item.update")}
            onChange={onVisible}
          />
        </div>
        {kv(
          COPY.dock.requestedBy,
          sender ?? DASH,
          row.requested_at == null
            ? undefined
            : date(row.requested_at, { now, tz, withYear: true }),
        )}
        {kv(
          COPY.dock.source,
          row.source_tag === "prior_year" && year !== null ? COPY.row.fromPriorYear(year) : DASH,
        )}
        <div className="flex flex-col gap-[4px] px-[14px] py-[10px] hairline-t">
          <span className="text-body text-ink-2">{COPY.dock.wording}</span>
          <span className="text-dense leading-[1.5] text-ink-2">
            {preview?.description ?? DASH}
          </span>
        </div>
        {!row.client_visible && (
          <p className="px-[14px] py-[10px] hairline-t text-dense text-ink-3">
            {COPY.row.internalOnly}
          </p>
        )}
        {(first !== undefined || ignored) && band(COPY.dock.uploadCard)}
        {ignored && (
          <>
            {kv(
              COPY.dock.status,
              <Pill variant="muted" size="sm">
                {COPY.row.ignored}
              </Pill>,
            )}
            {row.client_ignore_reason != null &&
              kv(COPY.dock.clientReason, COPY.ignoreReasons[row.client_ignore_reason])}
          </>
        )}
        {first !== undefined && (
          <>
            {kv(
              COPY.dock.status,
              row.kind === "firm_provided" && row.status === "received" ? (
                <Pill variant="amber" size="sm">
                  {COPY.row.k1Draft}
                </Pill>
              ) : (
                registryWord("request", row.status).label
              ),
            )}
            {kv(
              COPY.dock.file,
              detail.uploads.length > 1
                ? `${first.file_name} · ${COPY.dock.ofFiles(count(detail.uploads.length))}`
                : first.file_name,
            )}
            {kv(
              COPY.dock.uploadedBy,
              first.uploaded_by_name,
              date(first.uploaded_at, { now, tz, withYear: true }),
            )}
          </>
        )}
      </div>
      <div className="flex flex-none flex-col gap-[8px] p-[10px] hairline-t">
        {ignored ? (
          <>
            <Button
              variant="primary"
              disabled={!allows(row, "request_item.waive")}
              onClick={onWaive}
            >
              {COPY.dock.waive}
            </Button>
            <Button
              variant="secondary"
              disabled={!allows(row, "request_item.return")}
              onClick={onReturn}
            >
              {COPY.dock.returnToClient}
            </Button>
          </>
        ) : row.overdue ? (
          <Button variant="secondary" disabled={onRemind === undefined} onClick={onRemind}>
            {COPY.dock.remind}
          </Button>
        ) : first !== undefined ? (
          <>
            <Button variant="secondary" disabled title={COPY.dock.openViewerHint}>
              {COPY.dock.openViewer}
            </Button>
            {row.kind === "firm_provided" && (
              <Button variant="secondary" disabled title={COPY.dock.replaceK1Hint}>
                {COPY.dock.replaceK1}
              </Button>
            )}
          </>
        ) : null}
      </div>
    </div>
  );
}

/** "Preview as client": the client's projection, grouped by category, in their words. */
function ClientPreviewSheet({
  open,
  onOpenChange,
  items,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  items: readonly ClientPreviewItemOut[];
}): JSX.Element {
  const groups = new Map<string, ClientPreviewItemOut[]>();
  for (const item of items) {
    const key = item.category_name ?? "";
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const word = (item: ClientPreviewItemOut): string =>
    item.client_ignored
      ? COPY.preview.ignored
      : isSatisfied(item)
        ? COPY.preview.done
        : COPY.preview.todo;
  return (
    <SheetModal open={open} onOpenChange={onOpenChange} title={COPY.preview.title}>
      <div className="flex flex-col gap-[8px] bg-shell p-[8px]">
        {[...groups.entries()].map(([name, mine]) => (
          <RequestSection key={name} title={name} icon={categoryIcon(name)}>
            {mine.map((item) => (
              <div
                key={item.id}
                className="flex flex-col gap-[2px] px-[14px] py-[10px] hairline-t"
              >
                <span className="flex items-center gap-[8px] text-section font-medium">
                  <span className="min-w-0 flex-1">{item.title}</span>
                  <span className="text-dense font-normal text-ink-3">{word(item)}</span>
                </span>
                <span className="text-dense text-ink-2">{item.description}</span>
              </div>
            ))}
          </RequestSection>
        ))}
      </div>
    </SheetModal>
  );
}

function ActivityList({
  events,
  names,
  tz,
}: {
  events: readonly ActivityEventOut[];
  names: ReadonlyMap<string, string>;
  tz: string;
}): JSX.Element {
  return (
    <ul className="flex flex-col">
      {events.map((e) => (
        <li key={e.id} className="flex items-center gap-[10px] px-[14px] py-[10px] hairline-t">
          <span className="min-w-0 flex-1 text-body">
            {COPY.activity.events[e.event_type] ?? e.event_type}
          </span>
          <span className="text-dense text-ink-2">
            {e.actor_user_id == null ? DASH : (names.get(e.actor_user_id) ?? DASH)}
          </span>
          <time dateTime={e.at} className="text-meta text-ink-3">
            {dateTime(e.at, { tz })}
          </time>
        </li>
      ))}
    </ul>
  );
}

function PublishDialog({
  open,
  people,
  onClose,
  onPublish,
}: {
  open: boolean;
  people: string;
  onClose: () => void;
  onPublish: () => Promise<void>;
}): JSX.Element {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.dialogs.publishTitle}
      description={COPY.dialogs.publishTo(people)}
      action={
        <Button
          variant="primary"
          onClick={() => {
            onClose();
            void onPublish();
          }}
        >
          {COPY.dialogs.publish}
        </Button>
      }
    >
      <span className="sr-only">{COPY.dialogs.publishTo(people)}</span>
    </Dialog>
  );
}

function ReasonDialog({
  open,
  title,
  description,
  label,
  confirm,
  onClose,
  onConfirm,
}: {
  open: boolean;
  title: string;
  description?: string;
  label: string;
  confirm: string;
  onClose: () => void;
  onConfirm: (text: string) => Promise<void>;
}): JSX.Element {
  const [text, setText] = useState("");
  const close = (): void => {
    setText("");
    onClose();
  };
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close();
      }}
      title={title}
      {...(description === undefined ? {} : { description })}
      dirty={text.trim() !== ""}
      action={
        <Button
          variant="primary"
          disabled={text.trim() === ""}
          onClick={() => {
            void onConfirm(text.trim()).then(close);
          }}
        >
          {confirm}
        </Button>
      }
    >
      <Fieldset flush>
        <ValueRow kind="paragraph" label={label} value={text} onChange={setText} />
      </Fieldset>
    </Dialog>
  );
}

const WAIVE_REASONS = Object.keys(COPY.waiveReasons) as WaiveIn["na_reason"][];

function WaiveDialog({
  row,
  onClose,
  onWaive,
}: {
  row: BinderRequestRowOut | null;
  onClose: () => void;
  onWaive: (row: BinderRequestRowOut, body: WaiveIn) => Promise<void>;
}): JSX.Element {
  const [reason, setReason] = useState<WaiveIn["na_reason"]>("not_applicable_this_year");
  const [note, setNote] = useState("");
  const close = (): void => {
    setNote("");
    onClose();
  };
  return (
    <Dialog
      open={row !== null}
      onOpenChange={(next) => {
        if (!next) close();
      }}
      title={COPY.dialogs.waiveTitle}
      {...(row === null ? {} : { description: row.title })}
      dirty={note.trim() !== ""}
      action={
        <Button
          variant="primary"
          disabled={note.trim() === ""}
          onClick={() => {
            if (row === null) return;
            void onWaive(row, { na_reason: reason, note: note.trim() }).then(close);
          }}
        >
          {COPY.dialogs.waive}
        </Button>
      }
    >
      <Fieldset flush>
        <ValueRow
          kind="select"
          label={COPY.dialogs.waiveReason}
          options={WAIVE_REASONS.map((value) => ({ value, label: COPY.waiveReasons[value] }))}
          value={reason}
          onChange={(v) => {
            if ((WAIVE_REASONS as string[]).includes(v)) setReason(v as WaiveIn["na_reason"]);
          }}
        />
        <ValueRow
          kind="paragraph"
          label={COPY.dialogs.waiveNote}
          value={note}
          onChange={setNote}
        />
      </Fieldset>
    </Dialog>
  );
}

/** The screen with its own selection and tab: the gallery's artboard. The route keeps both in the
 * search params (`?request=`, `?tab=`). */
export function BinderPage({
  binderId,
  initialRequest = null,
  toolbar,
  frame = false,
}: {
  binderId: string;
  initialRequest?: string | null;
  toolbar?: ToolbarProps;
  frame?: boolean;
}): JSX.Element {
  const [request, setRequest] = useState<string | null>(initialRequest);
  const [tab, setTab] = useState<BinderTab>("requests");
  return (
    <BND02
      binderId={binderId}
      request={request}
      onRequest={setRequest}
      tab={tab}
      onTab={setTab}
      {...(toolbar === undefined ? {} : { toolbar })}
      frame={frame}
    />
  );
}
