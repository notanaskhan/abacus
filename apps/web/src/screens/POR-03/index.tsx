import type { PortalBinderOut, PortalBinderRefOut } from "@abacus/api-client";
import {
  Button,
  CATEGORIES,
  CategoryRail,
  DEFAULT_TZ,
  DropZone,
  EmptyState,
  Icon,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  type PortalNavItem,
  RequestDocuments,
  SimpleMenu,
  type UploadInFlight,
  UploadList,
  averageProgress,
  bytes,
  date,
  usePortalBrand,
  useRequestBinder,
} from "@abacus/ui";
import { type JSX, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import {
  binderView,
  brandOf,
  useBinder,
  useBinderActions,
  useBinders,
  useBranding,
  usePortalToolbar,
} from "../../domain/portal";
import { COPY } from "./copy";

// POR-03 · Documents, part 1 (R-01-T06; docs/screens/POR-03.md). T7 split over C5 section
// portal-pbc: the rail (binder picker with the closed 2024 binder read-only, the DropZone, the
// Uploading band, the nine categories with code-computed ticks) and the C-16 Request kit's
// documents pane (Requested ⇕, the rows in client words, Ignore with three reasons and a note,
// Undo, Withdraw with the DF-15 line, Mark as Done tonal then olive, the banner with Undo, the
// empty state). Each artboard is its data (fixtures/scenarios/POR-03.ts):
//
//   a  two requests open (Intake 2), two files uploading in the rail
//   c  Claire's 9:24 AM drop sorted onto the estimated payments, "Suggested — … will confirm"
//   e  marked done: the green-tint banner with Undo
//   f  the Ignore popover open on the 1095-C
//   g  the 2024 form returned by Kevin Osei ("Returned · wrong year")
//   h  nothing requested: "You’re all caught up."
//
// b, motion, c2, d, i and M are R-01-T10's. White label: the firm's name comes from the branding;
// nothing here names the product, the agent or a firm status (INV-5, DEC-01). No bell (DEC-58 d).

export interface POR03Hold {
  /** Files over the list (b), named. */
  dragging?: readonly string[];
  /** The request whose Ignore popover is open (f). */
  ignoreOpenOn?: string;
  /** Files uploading from this browser (a), `percent` 0–100. */
  uploads?: readonly { name: string; sizeBytes: number; percent: number }[];
}

export interface POR03Props {
  /** The binder to open; undefined opens the first the person can see. */
  binderId?: string;
  frame?: boolean;
  /** A specimen's held interaction (the gallery replays an artboard). */
  hold?: POR03Hold;
}

const TZ = DEFAULT_TZ;

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

function BinderPicker({
  current,
  binders,
  onPick,
}: {
  current: PortalBinderRefOut;
  binders: readonly PortalBinderRefOut[];
  onPick: (id: string) => void;
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
        className="inline-flex h-[30px] items-center gap-[6px] rounded-pill pr-[10px] pl-[12px] text-pane font-medium tracking-[-0.012em] whitespace-nowrap hover:bg-nav-fill aria-expanded:bg-nav-fill"
      >
        {current.title}
        <Icon name="chevron-down" size={13} className="text-ink-3" />
      </button>
      <SimpleMenu
        open={open}
        onClose={() => {
          setOpen(false);
        }}
        trigger={ref}
        label={COPY.binderPicker}
        width={220}
        align="end"
        items={binders.map((b) => ({
          label: b.title,
          checked: b.id === current.id,
          onSelect: () => {
            onPick(b.id);
          },
        }))}
      />
    </span>
  );
}

function Loading(): JSX.Element {
  return (
    <div role="status" aria-label={COPY.loading} className="flex flex-col gap-[8px] p-[10px]">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-[96px] rounded-pane bg-nested" />
      ))}
    </div>
  );
}

function Binder({
  binder,
  binders,
  onPick,
  user,
  nav,
  frame,
  hold,
}: {
  binder: PortalBinderOut;
  binders: readonly PortalBinderRefOut[];
  onPick: (id: string) => void;
  user: string;
  nav: readonly PortalNavItem[];
  frame: boolean;
  hold: POR03Hold;
}): JSX.Element {
  const now = useNow();
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const day = (iso: string): string => date(onDay(iso), { now, tz: TZ });
  const today = date(now, { now, tz: TZ });
  const view = binderView(binder, firm, day);
  const act = useBinderActions(binder);
  const [sending, setSending] = useState<readonly UploadInFlight[]>([]);
  const uploads: UploadInFlight[] = [
    ...(hold.uploads ?? []).map((u) => ({
      name: u.name,
      size: bytes(u.sizeBytes),
      p: u.percent / 100,
    })),
    ...sending,
  ];
  const send = (files: readonly File[], requestId: string | null): void => {
    setSending(files.map((f) => ({ name: f.name, size: bytes(f.size), p: 0 })));
    void act.send(files, requestId).finally(() => {
      setSending([]);
    });
  };
  const kit = useRequestBinder({
    firm,
    today,
    binder: binder.binder.title,
    requests: view.requests,
    sections: view.sections,
    uploads,
    doneCats: view.doneCats,
    marked: view.marked,
    withdraw: true,
    readOnly: view.readOnly,
    ...(hold.ignoreOpenOn === undefined ? {} : { openIgnore: hold.ignoreOpenOn }),
    ...(hold.dragging === undefined
      ? {}
      : { drag: { count: hold.dragging.length, names: hold.dragging } }),
    onFiles: send,
    onIgnore: (id, reason, note) => {
      void act.ignore(id, reason, note);
    },
    onUndoIgnore: (id) => {
      void act.undoIgnore(id);
    },
    onRemove: (id) => {
      const file = view.withdrawable.get(id);
      if (file !== undefined) void act.withdraw(id, file);
    },
    onMarkDone: () => {
      void act.markDone();
    },
    onUndoDone: () => {
      void act.undoMarkDone();
    },
  });
  const rail = (
    <Pane header={false} className="flex-[1_1_0%]">
      <div className="flex h-(--pane-hd-h) flex-none items-center justify-center hairline-b">
        <BinderPicker current={binder.binder} binders={binders} onPick={onPick} />
      </div>
      {!view.readOnly && (
        <DropZone
          progress={averageProgress(uploads)}
          onChoose={() => {
            kit.choose(null);
          }}
        />
      )}
      <UploadList uploads={uploads} />
      <CategoryRail
        categories={CATEGORIES}
        states={kit.states}
        selected={kit.category}
        onSelect={kit.setCategory}
      />
    </Pane>
  );
  return (
    <PortalLayout
      variant="split"
      user={user}
      nav={nav}
      active="Documents"
      frame={frame}
      {...(frame ? { height: 860 } : {})}
      rail={rail}
    >
      <RequestDocuments binder={kit} />
    </PortalLayout>
  );
}

export function POR03({ binderId, frame = false, hold = {} }: POR03Props): JSX.Element | null {
  const bar = usePortalToolbar(null);
  const [picked, setPicked] = useState<string | undefined>(binderId);
  const binders = useBinders(null);
  const list = binders.data?.items ?? [];
  const chosen = picked ?? list.find((b) => !b.closed)?.id ?? list[0]?.id;
  const binder = useBinder(chosen);
  if (bar === undefined) return null;
  const data = binder.data;
  if (data === undefined) {
    return (
      <div data-screen="POR-03" className="flex min-h-0 flex-1 flex-col">
        <PortalLayout
          variant="split"
          user={bar.user}
          nav={bar.nav}
          active="Documents"
          frame={frame}
          {...(frame ? { height: 860 } : {})}
          rail={<Pane header={false} />}
        >
          <Pane title={COPY.pane}>
            {binder.isError || binders.isError ? (
              <EmptyState
                tone="error"
                icon="circle-alert"
                title={COPY.error.title}
                action={
                  <Button variant="secondary" size="sm" onClick={() => void binder.refetch()}>
                    {COPY.error.retry}
                  </Button>
                }
              >
                {COPY.error.body}
              </EmptyState>
            ) : (
              <Loading />
            )}
          </Pane>
        </PortalLayout>
      </div>
    );
  }
  return (
    <div data-screen="POR-03" className="flex min-h-0 flex-1 flex-col">
      <Binder
        // A fresh read replaces the kit's view of the rows (its edits show at once until then).
        key={`${data.binder.id}:${String(binder.dataUpdatedAt)}`}
        binder={data}
        binders={list}
        onPick={setPicked}
        user={bar.user}
        nav={bar.nav}
        frame={frame}
        hold={hold}
      />
    </div>
  );
}

/** The page: the firm's branding first, then the documents under its brand. */
export function PortalDocuments(props: POR03Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR03 {...props} />
    </PortalBrandProvider>
  );
}
