import { type DragEvent, type JSX, useMemo, useRef, useState } from "react";
import { cn } from "../cn";
import { PRESS } from "../components/control-classes";
import { StatusDisc } from "../components/status";
import { Icon } from "../icons";
import { Pane } from "../layout/pane";
import {
  CategoryRail,
  DoneBanner,
  DragStack,
  DropRing,
  DropZone,
  MarkAsDone,
  ReceiptLine,
  RequestEmpty,
  type RequestEmptyKind,
  RequestRow,
  RequestSection,
  SimpleMenu,
  UploadList,
} from "./parts";
import {
  CATEGORIES,
  type CategoryKey,
  type CategoryState,
  FILTERS,
  type RequestFilter,
  type RequestItem,
  type RequestSectionData,
  type UploadInFlight,
  averageProgress,
  categoryState,
  doneButton,
  keep,
  satisfied,
  withoutKeys,
} from "./types";

// C-16 Request kit, portal variant (F-05-T36): the client's binder. `useRequestBinder` holds the
// view state (filter, category, the drop target, Mark as Done, the client's own edits) over the
// requests a screen passes in; `RequestRail`, `RequestDocuments` and `RequestMobile` draw it into
// the T7 PortalLayout's rail, pane and 390 column. Every intent goes out through a callback
// (upload, ignore, remove, reply, mark done, files dropped); the kit calls no API.

export interface RequestBinderProps {
  /** The firm's name for the client's lines ("Accepted by Brightwater Hale"). */
  firm: string;
  /** Today, from the server's clock: "Sep 14". */
  today: string;
  /** The binder's name: "2025 Binder". */
  binder: string;
  requests: readonly RequestItem[];
  sections: readonly RequestSectionData[];
  uploads?: readonly UploadInFlight[];
  /** Categories the firm marks complete whatever the requests say. */
  doneCats?: readonly CategoryKey[];
  filter?: RequestFilter;
  /** Starts marked as done. */
  marked?: boolean;
  /** Files that matched no request: "Brightwater Hale will sort this". */
  unsorted?: readonly string[];
  /** Hold the drop target on (T7c, TPL-07b), with this many files and their names. */
  drag?: { count: number; names?: readonly string[] };
  /** Hold one row's Ignore menu open (TPL-07f). */
  openIgnore?: string;
  /** Files chosen or dropped, with the request they were chosen for (null: sort them). */
  onFiles?: (files: readonly File[], requestId: string | null) => void;
  onIgnore?: (id: string, reason: string, note: string) => void;
  onUndoIgnore?: (id: string) => void;
  onRemove?: (id: string) => void;
  onReply?: (id: string, text: string) => void;
  onMarkDone?: () => void;
  onUndoDone?: () => void;
  /** Mark as Done clicked while requests are open: the screen toasts the count. */
  onBlocked?: (open: number) => void;
  /** "Upload something else": files for the firm's Inbox, not the list. */
  onUploadOther?: (files: readonly File[]) => void;
}

export interface RequestBinder {
  props: RequestBinderProps;
  items: readonly RequestItem[];
  filter: RequestFilter;
  setFilter: (f: RequestFilter) => void;
  category: CategoryKey | null;
  setCategory: (c: CategoryKey | null) => void;
  states: Readonly<Record<CategoryKey, CategoryState>>;
  done: boolean;
  over: boolean;
  open: number;
  /** Opens the file picker for one request, or for the drop zone (null). */
  choose: (requestId: string | null) => void;
  /** Opens the file picker for "Upload something else" (the firm's Inbox). */
  chooseOther: () => void;
  /** The hidden file input every picker shares. */
  input: JSX.Element;
  update: (id: string, patch: (r: RequestItem) => RequestItem) => void;
  markDone: () => void;
  undoDone: () => void;
  /** Files are over the well (the live drop target). */
  setOver: (over: boolean) => void;
}

/** The binder's view state. The client's own edits (ignore, undo, remove, reply) show at once and
 * go out through the callbacks; the screen's next read replaces them. */
export function useRequestBinder(props: RequestBinderProps): RequestBinder {
  const [items, setItems] = useState<readonly RequestItem[]>(props.requests);
  const [filter, setFilter] = useState<RequestFilter>(props.filter ?? "requested");
  const [category, setCategory] = useState<CategoryKey | null>(null);
  const [done, setDone] = useState(props.marked ?? false);
  const [live, setLive] = useState(false);
  const target = useRef<{ other: boolean; id: string | null }>({ other: false, id: null });
  const fileInput = useRef<HTMLInputElement>(null);

  const states = useMemo(() => {
    const out = {} as Record<CategoryKey, CategoryState>;
    for (const c of CATEGORIES) {
      out[c.key] = categoryState(c.key, items, props.sections, props.doneCats);
    }
    return out;
  }, [items, props.sections, props.doneCats]);
  const open = doneButton(items, done).open;

  const update = (id: string, patch: (r: RequestItem) => RequestItem): void => {
    setItems((all) => all.map((r) => (r.id === id ? patch(r) : r)));
  };
  const pick = (to: { other: boolean; id: string | null }): void => {
    target.current = to;
    fileInput.current?.click();
  };
  const input = (
    <input
      ref={fileInput}
      type="file"
      multiple
      hidden
      aria-hidden="true"
      tabIndex={-1}
      onChange={(event) => {
        const files = Array.from(event.target.files ?? []);
        event.target.value = "";
        if (files.length === 0) return;
        if (target.current.other) props.onUploadOther?.(files);
        else props.onFiles?.(files, target.current.id);
      }}
    />
  );
  return {
    props,
    items,
    filter,
    setFilter,
    category,
    setCategory,
    states,
    done,
    over: props.drag !== undefined || live,
    open,
    choose: (id) => {
      pick({ other: false, id });
    },
    chooseOther: () => {
      pick({ other: true, id: null });
    },
    input,
    update,
    markDone: () => {
      setDone(true);
      props.onMarkDone?.();
    },
    undoDone: () => {
      setDone(false);
      props.onUndoDone?.();
    },
    setOver: setLive,
  };
}

// ---- Rail ---------------------------------------------------------------------------------------

function BinderPicker({
  name,
  size = "pane",
}: {
  name: string;
  size?: "pane" | "mobile";
}): JSX.Element {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  return (
    <span className="relative inline-flex">
      <button
        ref={ref}
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className={cn(
          "inline-flex items-center gap-[6px] rounded-pill font-medium tracking-[-0.012em] whitespace-nowrap hover:bg-nav-fill aria-expanded:bg-nav-fill",
          size === "pane"
            ? "h-[30px] pr-[10px] pl-[12px] text-pane"
            : "h-[36px] pr-[6px] pl-[2px] text-title",
          PRESS,
        )}
      >
        {name}
        <Icon name="chevron-down" size={13} className="text-ink-3" />
      </button>
      <SimpleMenu
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        trigger={ref}
        label="Binder"
        width={220}
        align={size === "pane" ? "end" : "start"}
        items={[{ label: name, checked: true, onSelect: () => undefined }]}
      />
    </span>
  );
}

/** The 336 rail: the binder picker, the DropZone, the Uploading band and the CategoryRail. */
export function RequestRail({ binder }: { binder: RequestBinder }): JSX.Element {
  const uploads = binder.props.uploads ?? [];
  return (
    <Pane header={false} className="flex-[1_1_0%]">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center hairline-b">
        <BinderPicker name={binder.props.binder} />
      </div>
      <DropZone
        progress={averageProgress(uploads)}
        onChoose={() => {
          binder.choose(null);
        }}
      />
      <UploadList uploads={uploads} />
      <CategoryRail
        categories={CATEGORIES}
        states={binder.states}
        selected={binder.category}
        onSelect={binder.setCategory}
      />
    </Pane>
  );
}

// ---- Documents pane -------------------------------------------------------------------------------

function ShowPicker({ binder }: { binder: RequestBinder }): JSX.Element {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);
  const label = FILTERS.find((f) => f.value === binder.filter)?.label ?? "Requested";
  return (
    <span className="relative inline-flex">
      <button
        ref={ref}
        type="button"
        aria-label={`Show · ${label}`}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className={cn(
          "inline-flex h-[28px] items-center gap-[5px] rounded-pill bg-nav-fill pr-[9px] pl-[12px] text-body whitespace-nowrap hover:bg-sel-bg aria-expanded:bg-sel-bg",
          PRESS,
        )}
      >
        {label}
        <Icon name="chevrons-up-down" size={12} className="text-ink-3" />
      </button>
      <SimpleMenu
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        trigger={ref}
        label="Show"
        width={200}
        align="start"
        items={FILTERS.map((f) => ({
          label: f.label,
          checked: f.value === binder.filter,
          onSelect: () => {
            binder.setFilter(f.value);
          },
        }))}
      />
    </span>
  );
}

function emptyKind(binder: RequestBinder): RequestEmptyKind {
  if (binder.items.length === 0) return "none";
  return binder.filter === "fu" ? "fu" : "other";
}

/** The Documents pane: Show picker, title, Upload something else and Mark as Done over the well of
 * RequestSections; the drop target, the done banner, the unsorted section and the empty states.
 * `reduced` (T7g) names the upload button "Upload…". */
export function RequestDocuments({
  binder,
  reduced = false,
}: {
  binder: RequestBinder;
  reduced?: boolean;
}): JSX.Element {
  const { props, items } = binder;
  const well = useRef<HTMLDivElement>(null);
  const setLive = binder.setOver;
  const view = doneButton(items, binder.done);
  const shown = items.filter((r) => keep(r, binder.filter, binder.category, props.sections));
  const groups = props.sections
    .map((s) => ({ section: s, rows: shown.filter((r) => r.sec === s.key) }))
    .filter((g) => g.rows.length > 0);
  const unsorted = props.unsorted ?? [];

  const onDone = (): void => {
    if (view.ready && !binder.done) {
      binder.markDone();
      return;
    }
    if (view.ready) return;
    const first = well.current?.querySelector<HTMLElement>("[data-open-request]");
    if (first !== null && first !== undefined && well.current !== null) {
      well.current.scrollTop = first.offsetTop - 60;
    }
    props.onBlocked?.(view.open);
  };

  const dragOver = (event: DragEvent<HTMLDivElement>): void => {
    if (!event.dataTransfer.types.includes("Files")) return;
    event.preventDefault();
    setLive(true);
  };
  const drop = (event: DragEvent<HTMLDivElement>): void => {
    event.preventDefault();
    setLive(false);
    const files = Array.from(event.dataTransfer.files);
    if (files.length > 0) props.onFiles?.(files, null);
  };

  return (
    <Pane
      title="Documents"
      left={<ShowPicker binder={binder} />}
      right={
        items.length === 0 ? undefined : (
          <>
            <button
              type="button"
              onClick={() => {
                binder.chooseOther();
              }}
              className={cn(
                "inline-flex h-[30px] items-center gap-[6px] rounded-pill bg-card pr-[13px] pl-[11px] text-body whitespace-nowrap shadow-e1 hover:bg-nav-fill",
                PRESS,
              )}
            >
              <Icon name="upload" size={13} />
              {reduced ? "Upload…" : "Upload something else"}
            </button>
            <MarkAsDone view={view} onClick={onDone} />
          </>
        )
      }
      className="relative flex-[1_1_0%]"
    >
      {binder.input}
      <div
        ref={well}
        data-part="well"
        data-over={binder.over ? "true" : "false"}
        onDragOver={dragOver}
        onDragLeave={() => {
          setLive(false);
        }}
        onDrop={drop}
        className={cn(
          "flex h-full flex-col gap-[8px] overflow-y-auto p-[10px] transition-[background-color,box-shadow] duration-[180ms]",
          binder.over ? "bg-nested inset-ring-2 inset-ring-espresso" : "bg-shell",
        )}
      >
        {binder.done && (
          <DoneBanner today={props.today} firm={props.firm} onUndo={binder.undoDone} />
        )}
        {groups.map(({ section, rows }) => (
          <RequestSection key={section.key} title={section.title} icon={section.icon}>
            {rows.map((r) => (
              <RequestRow
                key={r.id}
                item={r}
                firm={props.firm}
                today={props.today}
                ignoreOpen={props.openIgnore === r.id}
                onUpload={(id) => {
                  binder.choose(id);
                }}
                onIgnore={(id, reason, note) => {
                  binder.update(id, (x) => ({
                    ...x,
                    st: "na",
                    reason,
                    ...(note === "" ? {} : { naNote: note }),
                  }));
                  props.onIgnore?.(id, reason, note);
                }}
                onUndoIgnore={(id) => {
                  binder.update(id, (x) => ({
                    ...withoutKeys(x, ["reason", "naNote"]),
                    st: "req",
                  }));
                  props.onUndoIgnore?.(id);
                }}
                onRemove={(id) => {
                  binder.update(id, (x) => ({
                    ...withoutKeys(x, ["file", "files", "on", "upText", "matched"]),
                    st: "req",
                  }));
                  props.onRemove?.(id);
                }}
                onReply={(id, text) => {
                  binder.update(id, (x) => ({ ...x, replied: props.today }));
                  props.onReply?.(id, text);
                }}
              />
            ))}
          </RequestSection>
        ))}
        {unsorted.length > 0 && binder.filter !== "fu" && (
          <RequestSection title={`${props.firm} will sort this`} icon="inbox">
            <p className="px-[14px] pb-[12px] text-dense leading-[1.5] text-ink-2">
              We couldn’t tell which request this belongs to. Your team will file it.
            </p>
            {unsorted.map((name) => (
              <div
                key={name}
                className="flex flex-col gap-[4px] bg-card px-[14px] py-[12px] hairline-t last:rounded-b-pane"
              >
                <span className="text-body font-medium">{name}</span>
                <ReceiptLine>{`You uploaded ${props.today}`}</ReceiptLine>
              </div>
            ))}
          </RequestSection>
        )}
        {groups.length === 0 && unsorted.length === 0 && (
          <RequestEmpty kind={emptyKind(binder)} firm={props.firm} />
        )}
      </div>
      {binder.over && (
        <div className="pointer-events-none absolute inset-x-0 top-(--pane-hd-h) bottom-0">
          <DragStack
            count={props.drag?.count ?? 1}
            {...(props.drag?.names === undefined ? {} : { names: props.drag.names })}
          />
        </div>
      )}
    </Pane>
  );
}

// ---- 390 ----------------------------------------------------------------------------------------

/** The binder at 390 (TPL-07-M): the binder picker with "n to do" (or "All in"), the 96 tap-to-upload
 * card, and the sections with 56 rows and a 32 "Upload…" pill on each open request. */
export function RequestMobile({ binder }: { binder: RequestBinder }): JSX.Element {
  const { props, items } = binder;
  const uploads = props.uploads ?? [];
  const groups = props.sections
    .map((s) => ({ section: s, rows: items.filter((r) => r.sec === s.key && r.extra !== true) }))
    .filter((g) => g.rows.length > 0);
  const line = (r: RequestItem): { text: string; ok: boolean } => {
    if (r.st === "up") return { text: r.upText ?? `You uploaded ${r.on ?? ""}`, ok: true };
    if (r.st === "acc") return { text: `Accepted by ${props.firm} · ${r.on ?? ""}`, ok: true };
    if (r.st === "firm") return { text: `${props.firm} adds this for you`, ok: false };
    if (r.st === "fu") return { text: "Needs follow-up", ok: false };
    return { text: `Requested ${r.req}`, ok: false };
  };
  return (
    <>
      {binder.input}
      <div className="flex items-center gap-[8px] px-[2px]">
        <BinderPicker name={props.binder} size="mobile" />
        <span className="flex-1" />
        {binder.open > 0 ? (
          <span className="inline-flex h-[22px] items-center rounded-pill bg-amber-tint px-[9px] text-pill text-amber-ink">
            {`${String(binder.open)} to do`}
          </span>
        ) : (
          <span className="inline-flex h-[22px] items-center rounded-pill bg-green-tint px-[9px] text-pill text-green-ink">
            All in
          </span>
        )}
      </div>
      <button
        type="button"
        aria-label="Tap to upload or take a photo"
        onClick={() => {
          binder.choose(null);
        }}
        className="flex h-[96px] flex-none items-center gap-[14px] rounded-pane bg-card px-[16px] text-left shadow-e1"
      >
        <DropRing progress={averageProgress(uploads)} icon="camera" well />
        <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
          <span className="text-btn-lg font-medium tracking-[-0.01em]">
            Tap to upload or take a photo
          </span>
          <span className="text-dense leading-[1.4] text-ink-2">
            Files are sorted into the right request
          </span>
        </span>
      </button>
      {groups.map(({ section, rows }) => (
        <section
          key={section.key}
          aria-label={section.title}
          className="flex-none overflow-hidden rounded-pane bg-card shadow-e1"
        >
          <div className="flex h-[42px] items-center gap-[9px] px-[14px] text-section">
            <Icon name={section.icon} size={15} className="text-ink-2" />
            <span className="min-w-0 truncate">{section.title}</span>
          </div>
          {rows.map((r) => {
            const l = line(r);
            const isOpen = !satisfied(r);
            return (
              <div
                key={r.id}
                data-request={r.id}
                className="flex min-h-[56px] items-center gap-[10px] py-[8px] pr-[10px] pl-[14px] hairline-t"
              >
                <span className="flex min-w-0 flex-1 flex-col gap-[3px]">
                  <span className="truncate text-body leading-[1.3] font-medium">{r.title}</span>
                  {l.ok ? (
                    <span className="flex items-center gap-[5px] text-pill text-green-ink">
                      <StatusDisc state="done" size={13} />
                      {l.text}
                    </span>
                  ) : (
                    <span className="text-pill leading-[1.35] font-normal text-ink-3">
                      {l.text}
                    </span>
                  )}
                </span>
                {isOpen && r.st === "req" && (
                  <button
                    type="button"
                    aria-label={`Upload… ${r.title}`}
                    onClick={() => {
                      binder.choose(r.id);
                    }}
                    className={cn("inline-flex h-[44px] flex-none items-center", PRESS)}
                  >
                    <span className="inline-flex h-[32px] items-center rounded-pill bg-card px-[13px] text-body font-medium whitespace-nowrap shadow-e1">
                      Upload…
                    </span>
                  </button>
                )}
              </div>
            );
          })}
        </section>
      ))}
    </>
  );
}
