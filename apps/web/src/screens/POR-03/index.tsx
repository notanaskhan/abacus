import type { PortalBinderOut, PortalBinderRefOut } from "@abacus/api-client";
import {
  Button,
  CATEGORIES,
  CategoryRail,
  DEFAULT_TZ,
  DropZone,
  EmptyState,
  Icon,
  MarkAsDone,
  Pane,
  PortalBrandProvider,
  PortalLayout,
  type PortalNavItem,
  type RequestBinder,
  RequestDocuments,
  RequestMobile,
  SimpleMenu,
  type UploadInFlight,
  UploadList,
  averageProgress,
  bytes,
  date,
  doneButton,
  satisfied,
  toastStore,
  useMotion,
  usePortalBrand,
  useRequestBinder,
} from "@abacus/ui";
import { type JSX, useEffect, useRef, useState } from "react";
import { useNow } from "../../app-core/clock";
import {
  DOCUMENT_WORDS,
  type DropOutcome,
  SHEET_WORDS,
  type RefusedFile,
  binderView,
  brandOf,
  dropOutcome,
  useBinder,
  useBinderActions,
  useBinders,
  useBranding,
  useDropBatch,
  usePortalToolbar,
} from "../../domain/portal";
import { COPY, UPLOAD_ACCEPT } from "./copy";

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
// Part 2 (R-01-T10):
//
//   b       three files over the list: the well on --nested with the 2px espresso ring
//   motion  the drop: the packet of 3 chips and "3 files", then the rows rise 135ms apart into
//           c and d; still under prefers-reduced-motion or `?static=1`
//   c       the drop batch polled until settled (`GET /v1/portal/drops/{batch}`): the two files on
//           their request, "Suggested — … will confirm", announced in a polite live region
//   c2      the 9:12 AM email filed to the 1095-C (fixture until N-01 files email)
//   d       Scan_0914.pdf matched nothing: "Brightwater Hale will sort this"
//   i       Dana Kowalski's audit binder: folder bands with discs and the other-parties note
//   M       the binder at 390: "2 to do", tap to upload or take a photo (the native picker with
//           the camera), Mark as Done sticky above the tab bar
//
// White label: the firm's name comes from the branding; nothing here names the product, the agent
// or a firm status (INV-5, DEC-01). No bell (DEC-58 d).

export interface POR03Hold {
  /** Files over the list (b), named. */
  dragging?: readonly string[];
  /** The drop motion plays, then sorts (motion). */
  motion?: boolean;
  /** Freeze the motion at its sorted frame (`?static=1`). */
  still?: boolean;
  /** The drop batch to poll (c, d). */
  dropBatch?: string;
  /** The request whose Ignore popover is open (f). */
  ignoreOpenOn?: string;
  /** Files uploading from this browser (a), `percent` 0–100. */
  uploads?: readonly { name: string; sizeBytes: number; percent: number }[];
}

export interface POR03Props {
  /** The binder to open; undefined opens the first the person can see. */
  binderId?: string;
  /** T7-M at 390 (the portal entry decides from the viewport). */
  mobile?: boolean;
  /** A nav item was chosen (the portal entry routes it). */
  onNavigate?: (area: string) => void;
  frame?: boolean;
  /** A specimen's held interaction (the gallery replays an artboard). */
  hold?: POR03Hold;
  /** A row's title opens the request in full (POR-04, R-01-T12). */
  onOpenRequest?: (id: string) => void;
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

/** i's rail rows: each band with its open requests (the audit variant has no nine categories). */
function BandRail({ kit }: { kit: RequestBinder }): JSX.Element {
  return (
    <div className="flex flex-col px-[8px] pt-[14px]">
      <h2 className="px-[8px] pb-[6px] text-meta text-ink-3">{COPY.categories}</h2>
      <ul className="flex flex-col">
        {kit.props.sections.map((band) => {
          const open = kit.items.filter(
            (r) => r.sec === band.key && r.extra !== true && !satisfied(r),
          ).length;
          return (
            <li
              key={band.key}
              className="flex min-h-[39px] items-center gap-[10px] px-[8px] hairline-b last:shadow-none"
            >
              <Icon name="folder" size={15} className="flex-none text-ink-2" />
              <span className="min-w-0 flex-1 truncate text-body">{band.title}</span>
              {open > 0 && <span className="text-meta text-ink-3">{COPY.bandOpen(open)}</span>}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

interface DropView {
  /** The packet is over the list (motion's first beat). */
  flying: boolean;
  /** The rows rise one by one (motion's last beat). */
  reveal: boolean;
  /** A settled drop's outcome; null while it sorts or when nothing was dropped. */
  outcome: DropOutcome | null;
  refused: readonly RefusedFile[];
}

function Binder({
  binder,
  binders,
  onPick,
  user,
  nav,
  frame,
  mobile,
  hold,
  drop,
  onDropped,
  onNavigate,
  onOpenRequest,
}: {
  binder: PortalBinderOut;
  binders: readonly PortalBinderRefOut[];
  onPick: (id: string) => void;
  user: string;
  nav: readonly PortalNavItem[];
  frame: boolean;
  mobile: boolean;
  hold: POR03Hold;
  drop: DropView;
  onDropped: (batch: string | null, refused: readonly RefusedFile[]) => void;
  onNavigate: ((area: string) => void) | undefined;
  onOpenRequest: ((id: string) => void) | undefined;
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
    void act
      .send(files, requestId)
      .then((result) => {
        if (requestId === null) onDropped(result.batch, result.refused);
      })
      .finally(() => {
        setSending([]);
      });
  };
  const bands = binder.layout === "bands";
  const dragging = drop.flying ? hold.dragging : hold.motion === true ? undefined : hold.dragging;
  const unsorted = drop.flying ? [] : (drop.outcome?.unsorted ?? []).map((f) => f.file_name);
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
    accept: UPLOAD_ACCEPT,
    unsorted,
    reveal: drop.reveal,
    ...(bands ? { bands: true } : {}),
    ...((binder.other_parties ?? []).length > 0
      ? { note: COPY.otherParties(binder.other_parties ?? []) }
      : {}),
    ...(hold.ignoreOpenOn === undefined ? {} : { openIgnore: hold.ignoreOpenOn }),
    ...(dragging === undefined
      ? {}
      : {
          drag: {
            count: dragging.length,
            names: dragging,
            ...(hold.motion === true ? { badge: COPY.motionBadge(dragging.length) } : {}),
          },
        }),
    onFiles: send,
    // R-01-T33: shown only when the firm published it and the intake route is on.
    uploadOther: binder.upload_something_else === true,
    onUploadOther: (files) => {
      void act.sendOther(files).then(() => {
        toastStore.show(SHEET_WORDS.sent(firm));
      });
    },
    ...(onOpenRequest === undefined ? {} : { onOpen: onOpenRequest }),
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
  const refusals = drop.refused.length > 0 && (
    <ul aria-label={COPY.refusedLabel} className="flex flex-col gap-[4px] px-[14px] py-[8px]">
      {drop.refused.map((f) => (
        <li key={f.name} className="flex items-start gap-[6px] text-dense text-ink-2">
          <Icon name="circle-alert" size={13} className="mt-[1px] flex-none text-ink-3" />
          {DOCUMENT_WORDS.refused[f.code](f.name)}
        </li>
      ))}
    </ul>
  );
  if (mobile) {
    return (
      <PortalLayout
        variant="mobile"
        user={user}
        nav={nav}
        active="Documents"
        frame={frame}
        {...(frame ? { height: 844 } : {})}
        {...(onNavigate === undefined ? {} : { onNavigate })}
        {...(view.readOnly || kit.items.length === 0
          ? {}
          : {
              mobileFooter: (
                <MarkAsDone
                  wide
                  view={doneButton(kit.items, kit.done)}
                  onClick={() => {
                    if (doneButton(kit.items, kit.done).ready && !kit.done) kit.markDone();
                  }}
                />
              ),
            })}
      >
        <RequestMobile binder={kit} />
        {refusals}
      </PortalLayout>
    );
  }
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
      {refusals}
      <UploadList uploads={uploads} />
      {bands ? (
        <BandRail kit={kit} />
      ) : (
        <CategoryRail
          categories={CATEGORIES}
          states={kit.states}
          selected={kit.category}
          onSelect={kit.setCategory}
        />
      )}
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
      {...(onNavigate === undefined ? {} : { onNavigate })}
      rail={rail}
    >
      <RequestDocuments binder={kit} />
    </PortalLayout>
  );
}

/** The drop's beats: the packet over the list, then the sort. Under reduced motion or `still` the
 * screen opens on the sorted frame; a live drop has no packet (the person's own drag was it). */
function useDropView(
  hold: POR03Hold,
  batchId: string | undefined,
  refused: readonly RefusedFile[],
) {
  const animate = useMotion(hold.still === true);
  const motion = hold.motion === true && animate;
  const [flying, setFlying] = useState(motion);
  useEffect(() => {
    if (!flying) return undefined;
    const timer = setTimeout(() => {
      setFlying(false);
    }, DROP_FLIGHT_MS);
    return () => {
      clearTimeout(timer);
    };
  }, [flying]);
  const batch = useDropBatch(batchId);
  const outcome = dropOutcome(batch.data);
  const view: DropView = { flying, reveal: motion && !flying, outcome, refused };
  return { view, settledAt: outcome === null ? 0 : batch.dataUpdatedAt };
}

/** How long the packet hangs over the list before the sort (motion's first beat). */
const DROP_FLIGHT_MS = 900;

export function POR03({
  binderId,
  mobile = false,
  onNavigate,
  frame = false,
  hold = {},
  onOpenRequest,
}: POR03Props): JSX.Element | null {
  const bar = usePortalToolbar(null);
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const [picked, setPicked] = useState<string | undefined>(binderId);
  const [dropped, setDropped] = useState<{
    batch: string | null;
    refused: readonly RefusedFile[];
  }>({ batch: hold.dropBatch ?? null, refused: [] });
  const binders = useBinders(null);
  const list = binders.data?.items ?? [];
  const chosen = picked ?? list.find((b) => !b.closed)?.id ?? list[0]?.id;
  const binder = useBinder(chosen);
  const { view: drop, settledAt } = useDropView(hold, dropped.batch ?? undefined, dropped.refused);
  // A settled sort changed the binder: read it again once (the rows move onto their requests).
  const { refetch } = binder;
  useEffect(() => {
    if (settledAt > 0 && hold.dropBatch === undefined) void refetch();
  }, [settledAt, refetch, hold.dropBatch]);
  if (bar === undefined) return null;
  const data = binder.data;
  const live =
    drop.outcome === null || drop.flying
      ? ""
      : DOCUMENT_WORDS.sorted(drop.outcome.matched.length, drop.outcome.unsorted.length, firm);
  const announce = (
    <div role="status" aria-live="polite" data-part="sort-live" className="sr-only">
      {live}
    </div>
  );
  if (data === undefined) {
    const failed = binder.isError || binders.isError;
    const body = failed ? (
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
    );
    return (
      <div data-screen="POR-03" className="flex min-h-0 flex-1 flex-col">
        {mobile ? (
          <PortalLayout
            variant="mobile"
            user={bar.user}
            nav={bar.nav}
            active="Documents"
            frame={frame}
            {...(frame ? { height: 844 } : {})}
            {...(onNavigate === undefined ? {} : { onNavigate })}
          >
            {body}
          </PortalLayout>
        ) : (
          <PortalLayout
            variant="split"
            user={bar.user}
            nav={bar.nav}
            active="Documents"
            frame={frame}
            {...(frame ? { height: 860 } : {})}
            {...(onNavigate === undefined ? {} : { onNavigate })}
            rail={<Pane header={false} />}
          >
            <Pane title={COPY.pane}>{body}</Pane>
          </PortalLayout>
        )}
      </div>
    );
  }
  return (
    <div data-screen="POR-03" className="flex min-h-0 flex-1 flex-col">
      {announce}
      <Binder
        // A fresh read replaces the kit's view of the rows (its edits show at once until then).
        key={`${data.binder.id}:${String(binder.dataUpdatedAt)}:${drop.flying ? "fly" : "rest"}`}
        binder={data}
        binders={list}
        onPick={setPicked}
        user={bar.user}
        nav={bar.nav}
        frame={frame}
        mobile={mobile}
        hold={hold}
        drop={drop}
        onDropped={(batch, refused) => {
          setDropped({ batch, refused });
        }}
        onNavigate={onNavigate}
        onOpenRequest={onOpenRequest}
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
