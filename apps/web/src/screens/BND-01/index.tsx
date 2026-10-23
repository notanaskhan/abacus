import type { BinderRowOut } from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  DASH,
  Dialog,
  Fieldset,
  Icon,
  type IndexChip,
  type IndexColumn,
  IndexList,
  type IndexTile,
  type ListEnvelope,
  Menu,
  type MenuItem,
  ProgressBar,
  RegistryStatus,
  SheetModal,
  SubLine,
  ValueRow,
  type ViewState,
  cn,
  count,
  date,
  sameDay,
  time,
  toast,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { todayIso, useNow, useToday } from "../../app-core/clock";
import { useCan } from "../../app-core/can";
import { useSession } from "../../app-core/session";
import {
  type BinderFilters,
  defaultBinderFilters,
  initialsOf,
  isBinderStatus,
  kindForWorkItem,
  rowAllows,
  useBinderActions,
  useBinders,
  useNewBinder,
  useStaffNames,
} from "../../domain/requests";
import { COPY } from "./copy";

// BND-01 · Binders index (P-06-T09; docs/screens/BND-01.md). T1 over `GET /v1/binders`: the five
// filter chips, the five binder-status tiles that filter (the server counts them over the filters
// minus the tile, after `visible()`), the ledger rows with progress, a row ··· menu, and the
// "+ New binder" sheet. Each artboard is its data:
//
//   a  Service │ Tax returns, Season │ TY2025: 1 · 48 · 0 · 40 · 152 = 241, 15 rows (Grace Holloway)
//   c  Osterberg Unpublished Sep 2 by Remy Vidal — fixing 2 requests (Remy Vidal)
//   d  Season │ TY2026: no binders; "Open season setup" (ENG-07, planned)
//   e  the list never answers: 8 skeleton rows
//
// b (Client activity │ None in 30 days with the bulk bar) and "Send reminders…" come with the
// follow-up sheet in P-06-T16.

const TILES: readonly IndexTile[] = [
  { code: "draft", label: "Draft", variant: "neutral" },
  { code: "published", label: "Published", variant: "state" },
  { code: "unpublished", label: "Unpublished", variant: "neutral" },
  { code: "complete", label: "Complete", variant: "green-tint" },
  { code: "closed", label: "Closed", variant: "neutral" },
];

const DAY_MS = 86_400_000;
const SILENT_DAYS = 30;

export interface BND01Props {
  filters: BinderFilters;
  onFilters: (next: BinderFilters) => void;
  /** A row's › opens its binder (BND-02, P-06-T12). */
  onOpen?: (row: BinderRowOut) => void;
}

/** "9:12 AM" today, "Yesterday", else "Sep 9" (the Inbox and HOME-01 feed agree). */
export function activityText(at: string | null, now: Date, tz: string): string {
  if (at === null) return DASH;
  if (sameDay(at, now, { tz })) return time(at, { tz });
  if (sameDay(at, now.getTime() - DAY_MS, { tz })) return COPY.yesterday;
  return date(at, { now, tz });
}

/** A published binder the client has not touched in 30 days on the business clock (BND-01b). */
export function isSilent(row: BinderRowOut, now: Date): boolean {
  if (row.status !== "published" || row.last_client_activity_at === null) return false;
  return now.getTime() - Date.parse(row.last_client_activity_at) > SILENT_DAYS * DAY_MS;
}

function priorSeason(season: string): string {
  const year = Number(season.replace(/^TY/, ""));
  return Number.isFinite(year) ? `TY${String(year - 1)}` : season;
}

/** The screen with its own filters: the route's page and the gallery's artboard. The filters live
 * in the page's state until the fixture-to-live swap (P-06-T16) mirrors them into the search
 * params; `initial` is what an artboard opens on (d: Season │ TY2026). */
export function BindersIndex({
  initial = {},
  onOpen,
}: {
  initial?: Partial<BinderFilters>;
  /** A row's › opens its binder (BND-02); the route navigates. */
  onOpen?: (row: BinderRowOut) => void;
}): JSX.Element {
  const today = useToday();
  const [filters, setFilters] = useState<BinderFilters>(() => ({
    ...defaultBinderFilters(today),
    ...initial,
  }));
  return (
    <BND01
      filters={filters}
      onFilters={setFilters}
      {...(onOpen === undefined ? {} : { onOpen })}
    />
  );
}

export function BND01({ filters, onFilters, onOpen }: BND01Props): JSX.Element {
  const now = useNow();
  const tz = useSession().tz ?? DEFAULT_TZ;
  const names = useStaffNames();
  const list = useBinders(filters);
  const actions = useBinderActions();
  const canCreate = useCan("binder.create");
  const [unpublishing, setUnpublishing] = useState<BinderRowOut | null>(null);
  const [creating, setCreating] = useState(false);

  const page = list.data;
  const facets = page?.facets ?? {};
  const set = (patch: Partial<BinderFilters>): void => {
    onFilters({ ...filters, ...patch });
  };

  const narrowed =
    filters.office !== null ||
    filters.preparer !== null ||
    filters.activity !== "any" ||
    filters.status !== null ||
    filters.q.trim() !== "";
  let state: ViewState;
  if (list.isError) state = { kind: "error", retry: () => void list.refetch() };
  else if (page === undefined) state = { kind: "loading" };
  else if (page.total === 0 && !narrowed) state = { kind: "empty" };
  else if (page.items.length === 0) {
    state = {
      kind: "filtered-empty",
      ...(filters.q.trim() === "" ? {} : { query: filters.q.trim() }),
      clear: () => {
        set({ office: null, preparer: null, activity: "any", status: null, q: "" });
      },
    };
  } else state = { kind: "ready" };

  const envelope: ListEnvelope<BinderRowOut> | undefined =
    page === undefined
      ? undefined
      : {
          items: page.items,
          next_cursor: page.next_cursor ?? null,
          total: page.total,
          counts: page.counts ?? {},
          facets,
        };

  const season = filters.season ?? "";
  const options = (key: string) =>
    (facets[key] ?? []).map((f) => ({ value: f.value, label: f.label }));
  const withValue = (key: string, value: string | null, label: string) => {
    const known = options(key);
    return value === null || known.some((o) => o.value === value)
      ? known
      : [...known, { value, label }];
  };
  const chips: IndexChip[] = [
    {
      key: "service",
      label: COPY.chips.service,
      icon: "briefcase",
      options: withValue("service", filters.service, filters.service ?? ""),
      value: filters.service,
    },
    {
      key: "season",
      label: COPY.chips.season,
      icon: "calendar",
      options: withValue("season", filters.season, season),
      value: filters.season,
    },
    {
      key: "office",
      label: COPY.chips.office,
      icon: "map-pin",
      options: options("office"),
      value: filters.office,
      placeholder: COPY.chips.officeAll,
    },
    {
      key: "preparer",
      label: COPY.chips.preparer,
      icon: "circle-user-round",
      options: options("preparer"),
      value: filters.preparer,
      placeholder: COPY.chips.preparerAll,
    },
    {
      key: "activity",
      label: COPY.chips.activity,
      icon: "activity",
      options: [{ value: "none_30_days", label: COPY.activity.none_30_days }],
      value: filters.activity === "any" ? null : filters.activity,
      placeholder: COPY.activity.any,
    },
  ];

  const onChip = (key: string, value: string | null): void => {
    if (key === "activity") set({ activity: value === "none_30_days" ? value : "any" });
    else if (key === "service" || key === "season" || key === "office" || key === "preparer") {
      set({ [key]: value });
    }
  };

  // "224 returns · 17 second-part binders" from the `part` facet; drawn only when the read model
  // gives it (docs/screens/BND-01.md, Open gaps).
  const parts = facets.part;
  const returns = parts?.find((f) => f.value === "1")?.n;
  const second = parts?.find((f) => f.value === "2+")?.n;
  const summary =
    page === undefined || returns === undefined || second === undefined || state.kind === "empty"
      ? undefined
      : COPY.summary(count(page.total), season, count(returns), count(second));

  const run = async (work: () => Promise<unknown>, done: string): Promise<void> => {
    try {
      await work();
      toast.show({ kind: "success", text: done });
    } catch {
      toast.show({ kind: "error", text: COPY.toasts.failed });
    }
  };

  const publish = async (row: BinderRowOut): Promise<void> => {
    try {
      await actions.publish(row.id);
      toast.undoable({
        text: COPY.toasts.published(row.name, row.client_name),
        undo: () => {
          void actions.undoPublish(row.id);
        },
      });
    } catch (error) {
      const detail = (error as { detail?: unknown } | null)?.detail;
      toast.show({
        kind: "error",
        text: detail === "binder_gate_unmet" ? COPY.toasts.gate : COPY.toasts.failed,
      });
    }
  };

  const menuFor = (row: BinderRowOut): MenuItem[][] => {
    const canPublish = rowAllows(row, "binder.publish");
    const lifecycle: MenuItem[] = [];
    if (row.status === "draft" || row.status === "unpublished") {
      lifecycle.push({
        label: COPY.menu.publish,
        disabled: !canPublish,
        onSelect: () => void publish(row),
      });
    }
    if (row.status === "published") {
      lifecycle.push({
        label: COPY.menu.unpublish,
        opensDialog: true,
        disabled: !canPublish,
        onSelect: () => {
          setUnpublishing(row);
        },
      });
    }
    const other: MenuItem[] = [
      {
        label: COPY.menu.duplicate(row.part + 1),
        disabled: !rowAllows(row, "binder.create"),
        onSelect: () =>
          void run(
            () => actions.duplicate(row.id),
            COPY.toasts.duplicated(
              `${row.name.replace(/ pt \d+$/, "")} pt ${String(row.part + 1)}`,
            ),
          ),
      },
      // FIL-01 is planned (docs/screens/BND-01.md, Links).
      { label: COPY.menu.files, disabled: true, onSelect: () => undefined },
    ];
    return lifecycle.length === 0 ? [other] : [lifecycle, other];
  };

  const columns: IndexColumn<BinderRowOut>[] = [
    { key: "binder", header: COPY.columns.binder, width: 170, cell: (r) => r.name },
    { key: "client", header: COPY.columns.client, cell: (r) => r.client_name },
    {
      key: "work_item",
      header: COPY.columns.workItem,
      width: 160,
      cell: (r) => (
        <span className="block truncate whitespace-normal text-ink-3 line-clamp-2">
          {r.work_item_label ?? DASH}
        </span>
      ),
    },
    {
      key: "requests",
      header: COPY.columns.requests,
      width: 170,
      cell: (r) => (
        <ProgressBar
          done={r.done_count}
          total={r.total_count}
          tone={r.done_count === r.total_count ? "ink" : "amber"}
          left={COPY.progress(count(r.done_count), count(r.total_count))}
          className="w-[140px]"
        />
      ),
    },
    {
      key: "status",
      header: COPY.columns.status,
      width: 200,
      cell: (r) => <StatusCell row={r} names={names} now={now} tz={tz} />,
    },
    {
      key: "activity",
      header: COPY.columns.activity,
      width: 230,
      cell: (r) => (
        <span
          data-silent={isSilent(r, now) ? "" : undefined}
          className={cn("text-meta", isSilent(r, now) ? "text-red-ink" : "text-ink-3")}
        >
          {activityText(r.last_client_activity_at, now, tz)}
        </span>
      ),
    },
    {
      key: "prep",
      header: COPY.columns.prep,
      width: 56,
      cell: (r) => {
        const name = r.preparer_user_id === null ? undefined : names.get(r.preparer_user_id);
        return name === undefined ? (
          DASH
        ) : (
          <abbr title={name} className="text-ink-3 no-underline">
            {initialsOf(name)}
          </abbr>
        );
      },
    },
    {
      key: "menu",
      header: "",
      width: 36,
      cell: (r) => (
        <Menu
          label={COPY.menu.label(r.name, r.client_name)}
          align="end"
          sections={menuFor(r)}
          trigger={
            <button
              type="button"
              aria-label={COPY.menu.label(r.name, r.client_name)}
              onClick={(e) => {
                e.stopPropagation();
              }}
              className="flex size-[24px] items-center justify-center rounded-pill text-ink-3 hover:bg-nested"
            >
              <Icon name="ellipsis" size={14} />
            </button>
          }
        />
      ),
    },
  ];

  const emptyAction = (
    <Button variant="secondary" size="md" disabled title={COPY.empty.actionHint}>
      {COPY.empty.action}
    </Button>
  );

  return (
    <div data-screen="BND-01" className="flex min-h-0 flex-1 flex-col">
      <IndexList<BinderRowOut>
        title={COPY.title}
        noun={COPY.noun}
        state={state}
        envelope={envelope}
        columns={columns}
        {...(onOpen === undefined ? {} : { onOpen })}
        rowKey={(r) => r.id}
        twoLine={() => true}
        chips={chips}
        onChip={onChip}
        // The tiles wait for the counts: a loading tile never reads 0 (docs/screens/BND-01.md, DV-13).
        {...(page === undefined ? {} : { tiles: TILES })}
        tile={filters.status}
        onTile={(code) => {
          set({ status: isBinderStatus(code) ? code : null });
        }}
        {...(summary === undefined ? {} : { summary })}
        onClear={() => {
          onFilters(defaultBinderFilters(todayIso(now.getTime())));
        }}
        query={filters.q}
        onQuery={(q) => {
          set({ q });
        }}
        {...(canCreate
          ? {
              newLabel: COPY.newBinder,
              onNew: () => {
                setCreating(true);
              },
            }
          : {})}
        empty={{
          icon: "folder",
          title: COPY.empty.title(season),
          body: COPY.empty.body(priorSeason(season)),
          action: emptyAction,
        }}
      />
      <UnpublishDialog
        row={unpublishing}
        onClose={() => {
          setUnpublishing(null);
        }}
        onUnpublish={(row, reason) =>
          run(
            () => actions.unpublish(row.id, reason),
            COPY.toasts.unpublished(row.name, row.client_name),
          )
        }
      />
      <NewBinderSheet
        open={creating}
        onOpenChange={setCreating}
        onCreated={() => {
          toast.show({ kind: "success", text: COPY.toasts.created });
        }}
      />
    </div>
  );
}

function StatusCell({
  row,
  names,
  now,
  tz,
}: {
  row: BinderRowOut;
  names: ReadonlyMap<string, string>;
  now: Date;
  tz: string;
}): JSX.Element {
  const by = row.unpublished_by === null ? undefined : names.get(row.unpublished_by ?? "");
  const line =
    row.status === "unpublished" &&
    row.unpublished_at != null &&
    by !== undefined &&
    row.unpublish_reason != null
      ? COPY.unpublished(date(row.unpublished_at, { now, tz }), by, row.unpublish_reason)
      : null;
  return (
    <span className="flex flex-col items-start gap-[2px]">
      <RegistryStatus object="binder" code={row.status} />
      {line !== null && <SubLine>{line}</SubLine>}
    </span>
  );
}

function UnpublishDialog({
  row,
  onClose,
  onUnpublish,
}: {
  row: BinderRowOut | null;
  onClose: () => void;
  onUnpublish: (row: BinderRowOut, reason: string) => Promise<void>;
}): JSX.Element {
  const [reason, setReason] = useState("");
  const close = (): void => {
    setReason("");
    onClose();
  };
  return (
    <Dialog
      open={row !== null}
      onOpenChange={(open) => {
        if (!open) close();
      }}
      title={COPY.unpublishDialog.title}
      {...(row === null ? {} : { description: `${row.name} · ${row.client_name}` })}
      dirty={reason.trim() !== ""}
      action={
        <Button
          variant="primary"
          disabled={reason.trim() === ""}
          onClick={() => {
            if (row === null) return;
            void onUnpublish(row, reason.trim()).then(close);
          }}
        >
          {COPY.unpublishDialog.confirm}
        </Button>
      }
    >
      <Fieldset flush>
        <ValueRow
          kind="paragraph"
          label={COPY.unpublishDialog.reason}
          value={reason}
          onChange={setReason}
          placeholder={COPY.unpublishDialog.placeholder}
        />
      </Fieldset>
    </Dialog>
  );
}

function NewBinderSheet({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}): JSX.Element {
  const [engagementId, setEngagementId] = useState<string | null>(null);
  const [workItemId, setWorkItemId] = useState<string | null>(null);
  const { engagements, items, create } = useNewBinder(open ? engagementId : null);
  const engagementOptions = (engagements.data ?? []).map((e) => ({
    value: e.id,
    label: `${e.client_name} · ${e.name}`,
  }));
  const workItems = items.data ?? [];
  const workItem = workItems.find((w) => w.id === workItemId);
  const reset = (next: boolean): void => {
    if (!next) {
      setEngagementId(null);
      setWorkItemId(null);
    }
    onOpenChange(next);
  };
  return (
    <SheetModal
      open={open}
      onOpenChange={reset}
      title={COPY.sheet.title}
      dirty={engagementId !== null}
      action={
        <Button
          variant="primary"
          disabled={workItem === undefined || create.isPending}
          onClick={() => {
            if (workItem === undefined) return;
            void create
              .mutateAsync({
                body: { work_item_id: workItem.id, kind: kindForWorkItem(workItem.kind) },
              })
              .then(() => {
                onCreated();
                reset(false);
              })
              .catch(() => {
                toast.show({ kind: "error", text: COPY.toasts.failed });
              });
          }}
        >
          {COPY.sheet.create}
        </Button>
      }
    >
      <div className="p-[16px]">
        <Fieldset flush>
          <ValueRow
            kind="select"
            label={COPY.sheet.engagement}
            options={engagementOptions}
            {...(engagementId === null ? {} : { value: engagementId })}
            placeholder={COPY.sheet.choose}
            onChange={(v) => {
              setEngagementId(v);
              setWorkItemId(null);
            }}
            menuWidth={320}
          />
          <ValueRow
            kind="select"
            label={COPY.sheet.workItem}
            options={workItems.map((w) => ({ value: w.id, label: w.name }))}
            {...(workItemId === null ? {} : { value: workItemId })}
            placeholder={COPY.sheet.choose}
            onChange={setWorkItemId}
          />
          <ValueRow
            kind="select"
            label={COPY.sheet.template}
            options={[{ value: "blank", label: COPY.sheet.blank }]}
            value="blank"
          />
        </Fieldset>
      </div>
    </SheetModal>
  );
}
