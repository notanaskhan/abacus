import type { PortalRequestOut } from "@abacus/api-client";
import {
  Button,
  DEFAULT_TZ,
  EmptyState,
  PortalBrandProvider,
  SheetModal,
  date,
  toast,
  usePortalBrand,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import {
  RequestSheet,
  type SheetDecision,
  type SheetQuestion,
  type SheetSlot,
  brandOf,
  useBranding,
  usePortalToolbar,
  useRequestSheet,
  useSheetActions,
  useThread,
} from "../../domain/portal";
import { POR03 } from "../POR-03";
import { UPLOAD_ACCEPT } from "../POR-03/copy";
import { COPY } from "./copy";

// POR-04 · Request detail / ignore reason sheet (R-01-T12; docs/screens/POR-04.md). The O3 sheet
// over POR-03 at `/documents/requests/$requestId` (the whole width at 390): one request through
// the caller's grant (`GET /v1/portal/request-items/{id}`, C5 portal-pbc), its shared thread, the
// upload, Withdraw, "This doesn't apply to me…" with the three reasons and a note, and Undo. Each
// artboard is its data (fixtures/scenarios/POR-04.ts):
//
//   a  the 1095-C to do, requested Feb 3, last year's file named, Kevin Osei's comment
//   b  "This doesn't apply to me…" pressed: the reasons and the note
//   c  the copy Claire emailed at 9:12 AM, filed by the firm: "Received by email Sep 14", no
//      Withdraw (the portal-upload variant has Withdraw with the DF-15 words)
//   d  the 2024 form returned: "Returned · wrong year", Kevin's note, the struck file, Upload…
//   e  a question from the firm (the typed slot C-01 wires; fixture only)
//   f  a decision from the firm (the typed slot T-06 / T-09 wire; fixture only)
//   g  a portal upload at 46%, held for review
//
// ✕, the scrim and Esc close it back to POR-03, and focus returns to the row that opened it.
// White label: nothing names the product, the agent or a firm status (DEC-01, INV-5).

export interface POR04Hold {
  /** "This doesn't apply to me…" pressed (b). */
  ignoreOpen?: boolean;
  /** A file in flight from this browser (g). */
  uploading?: { name: string; sizeBytes: number; percent: number };
  /** The question slot (e): C-01's transaction question. */
  question?: SheetQuestion;
  /** The decision slot (f): T-06 / T-09's client decision. */
  decision?: SheetDecision;
}

export interface POR04Props {
  /** The request to open (the `request` variant). */
  requestId: string;
  /** The binder behind the sheet; undefined opens the first the person can see. */
  binderId?: string;
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** ✕, the scrim or Esc: back to POR-03. */
  onClose?: () => void;
  onNavigate?: (area: string) => void;
  hold?: POR04Hold;
}

function onDay(day: string): string {
  return `${day}T12:00:00Z`;
}

/** The sheet's frame while the request loads or cannot be read (404 says nothing more, INV-4). */
function SheetState({
  open,
  onClose,
  mobile,
  failed,
  missing,
  onRetry,
}: {
  open: boolean;
  onClose: () => void;
  mobile: boolean;
  failed: boolean;
  missing: boolean;
  onRetry: () => void;
}): JSX.Element {
  return (
    <SheetModal
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
      title={COPY.header.request}
      fullScreen={mobile}
    >
      {missing ? (
        <EmptyState icon="circle-help" title={COPY.notFound} />
      ) : failed ? (
        <EmptyState
          tone="error"
          icon="circle-alert"
          title={COPY.loadError}
          action={
            <Button variant="secondary" size="sm" onClick={onRetry}>
              {COPY.retry}
            </Button>
          }
        />
      ) : (
        <div role="status" aria-label={COPY.loading} className="flex flex-col gap-[12px]">
          {[0, 1, 2].map((i) => (
            <div key={i} className="h-[120px] rounded-nested bg-nested" />
          ))}
        </div>
      )}
    </SheetModal>
  );
}

function notFound(error: unknown): boolean {
  return typeof error === "object" && error !== null && "detail" in error;
}

/** The sheet bound to its data: the request variant reads the request and its thread; the
 * question and decision variants take their slot from the caller (fixture only in R-01). */
export function PortalRequestSheet({
  requestId,
  open,
  onClose,
  mobile = false,
  hold = {},
}: {
  requestId: string;
  open: boolean;
  onClose: () => void;
  mobile?: boolean;
  hold?: POR04Hold;
}): JSX.Element | null {
  const now = useNow();
  const brand = usePortalBrand();
  const firm = brand.portalName ?? brand.name;
  const bar = usePortalToolbar(null);
  const slotted = hold.question !== undefined || hold.decision !== undefined;
  const sheet = useRequestSheet(slotted ? undefined : requestId);
  const data: PortalRequestOut | undefined = sheet.data;
  const thread = useThread(data?.engagement_id, data?.id);
  const act = useSheetActions(data);
  const [sending, setSending] = useState<{ name: string; sizeBytes: number } | null>(null);
  const day = (iso: string): string => date(onDay(iso), { now, tz: DEFAULT_TZ });
  if (bar === undefined) return null;
  const viewer = { kind: "human" as const, name: bar.user };
  const sent = (): void => {
    toast.show({ kind: "success", text: COPY.sent(firm) });
  };
  /** A write that failed: say so in fixed words; the next read shows what stands. */
  const settle = (work: Promise<unknown>): void => {
    work.catch(() => {
      toast.show({ kind: "error", text: COPY.failed });
    });
  };
  let slot: SheetSlot | null = null;
  if (hold.question !== undefined) {
    slot = { variant: "question", question: hold.question, onSend: sent };
  } else if (hold.decision !== undefined) {
    slot = { variant: "decision", decision: hold.decision, onSend: sent };
  } else if (data !== undefined) {
    const uploading =
      sending !== null ? { ...sending, percent: 0 } : (hold.uploading ?? undefined);
    slot = {
      variant: "request",
      request: data,
      thread: thread.data ?? [],
      ...(uploading === undefined ? {} : { uploading }),
      ...(hold.ignoreOpen === true ? { ignoreOpen: true } : {}),
      onUpload: (files) => {
        const first = files[0];
        if (first !== undefined) setSending({ name: first.name, sizeBytes: first.size });
        settle(
          act.upload(files).finally(() => {
            setSending(null);
          }),
        );
      },
      onIgnore: (reason, note) => {
        settle(act.ignore(reason, note).then(onClose));
      },
      onUndoIgnore: () => {
        settle(act.undoIgnore());
      },
      onWithdraw: (file) => {
        settle(act.withdraw(file));
      },
      onComment: (text) => {
        settle(act.comment(text));
      },
    };
  }
  if (slot === null) {
    return (
      <SheetState
        open={open}
        onClose={onClose}
        mobile={mobile}
        failed={sheet.isError}
        missing={sheet.isError && notFound(sheet.error)}
        onRetry={() => void sheet.refetch()}
      />
    );
  }
  return (
    <RequestSheet
      slot={slot}
      open={open}
      onClose={onClose}
      viewer={viewer}
      day={day}
      mobile={mobile}
      accept={UPLOAD_ACCEPT}
    />
  );
}

/** POR-04: POR-03 behind, the sheet over it. */
export function POR04({
  requestId,
  binderId,
  mobile = false,
  frame = false,
  onClose,
  onNavigate,
  hold = {},
}: POR04Props): JSX.Element {
  const [open, setOpen] = useState(true);
  return (
    <div data-screen="POR-04" className="flex min-h-0 flex-1 flex-col">
      <POR03
        {...(binderId === undefined ? {} : { binderId })}
        mobile={mobile}
        frame={frame}
        {...(onNavigate === undefined ? {} : { onNavigate })}
      />
      <PortalRequestSheet
        requestId={requestId}
        open={open}
        mobile={mobile}
        hold={hold}
        onClose={() => {
          setOpen(false);
          onClose?.();
        }}
      />
    </div>
  );
}

/** The page: the firm's branding first, then the sheet over the documents under its brand. */
export function PortalRequest(props: POR04Props): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <POR04 {...props} />
    </PortalBrandProvider>
  );
}
