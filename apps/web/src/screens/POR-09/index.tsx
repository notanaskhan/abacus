import type {
  DeliverableBandOut,
  DeliverableOut,
  DeliverableRowOut,
  DeliverablesOut,
  DeliverableVersionOut,
  K1RowOut,
} from "@abacus/api-client";
import { downloadDeliverable, getDeliverablePage } from "@abacus/api-client";
import {
  approveDeliverableMutation,
  getDeliverableOptions,
  listDeliverablesOptions,
  listPageCommentsOptions,
  portalK1sOptions,
} from "@abacus/api-client/query";
import {
  Button,
  ConfirmDialog,
  EmptyState,
  Icon,
  Pill,
  PortalBrandProvider,
  PortalLayout,
  RegistryStatus,
  date as formatDate,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { useNow } from "../../app-core/clock";
import { brandOf, useBranding, usePortalToolbar } from "../../domain/portal";
import { PackageCard } from "../POR-13";
import { COPY } from "./copy";

// POR-09 · Deliverables (R-02-T17; docs/screens/POR-09.md) on T7 split: the rail (bands by work
// item, Coming next, My K-1s) and the viewer (pager and zoom over the server's page images, the
// DRAFT watermark while a version is a draft, the comment column). Every title, page count, date,
// status and K-1 amount is the server's; the browser adds nothing up. Approve is management's own
// act on the latest draft (fresh MFA at the server, `statement.client_approve`); it renders only
// when the version lists `approve`, and a stale `seen_hash` answers 409 ("A newer draft is
// available"). Release stays the firm's (AUD-24). A firm with `portal.deliverables` off answers
// 404 with that flag's name: the designed flag-off state, never a 404 page.
//
//   a   Dana, draft v3 for review, page 2 of 14, comment 1      a2  draft v4, the approve confirm
//   b   approved by Dana Oct 8, watermark stays                   c   final: no watermark, Download
//   d   Meera's role union: Not ready yet and her released K-1   e   Copperleaf (fixture, AR-C 70)
//   f   nothing delivered yet

export interface Por09Props {
  mobile?: boolean;
  /** Presentation only (the gallery): the 1400 window or the 390 phone. */
  frame?: boolean;
  /** The deliverable open on arrival (`/deliverables/$deliverableId`). */
  deliverableId?: string;
  /** `?section=k1s` (T-02's DV-11 banner): My K-1s selected. */
  section?: "k1s";
  /** The page open on arrival (a: page 2). */
  page?: number;
  /** a2: the approve confirm held open. */
  confirming?: boolean;
  onNavigate?: (area: string) => void;
}

type Selected = { kind: "deliverable"; id: string } | { kind: "k1"; id: string };

const ZOOMS = [0.75, 1, 1.25, 1.5] as const;

/** The list is the person's own (a wall or an out-of-scope grant only narrows it), so its one 404
 * is the firm's `portal.deliverables` flag being off (DEC-3130): the designed state, never a 404. */
function isFlagOff(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { detail?: unknown }).detail === "not found"
  );
}

function firstSelection(data: DeliverablesOut | undefined, section?: "k1s"): Selected | null {
  if (data === undefined) return null;
  if (section === "k1s" && data.k1s[0] !== undefined) {
    return { kind: "k1", id: data.k1s[0].package_id };
  }
  for (const band of data.bands) {
    const row = band.rows.find((r) => r.status !== "not_ready_yet");
    if (row !== undefined) return { kind: "deliverable", id: row.id };
  }
  return data.k1s[0] === undefined ? null : { kind: "k1", id: data.k1s[0].package_id };
}

async function save(blob: Blob, name: string): Promise<void> {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
  await Promise.resolve();
}

function RailRow({
  row,
  selected,
  onSelect,
}: {
  row: DeliverableRowOut;
  selected: boolean;
  onSelect: () => void;
}): JSX.Element {
  const now = useNow();
  const ready = row.status !== "not_ready_yet";
  const sub = [
    row.latest_version === null || row.latest_version === undefined
      ? null
      : `v${String(row.latest_version)}`,
    row.page_count === null || row.page_count === undefined
      ? null
      : `${String(row.page_count)} pages`,
    row.released_on === null || row.released_on === undefined
      ? null
      : formatDate(row.released_on, { now }),
  ]
    .filter((s) => s !== null)
    .join(" · ");
  return (
    <li>
      <button
        type="button"
        data-deliverable-row={row.id}
        aria-current={selected ? "true" : undefined}
        disabled={!ready}
        onClick={onSelect}
        className={`flex min-h-[52px] w-full items-center gap-[8px] rounded-nested px-[10px] text-left ${selected ? "bg-sel-bg" : "hover:bg-nested"}`}
      >
        <Icon name={ready ? "file-text" : "circle"} size={15} className="text-ink-3" />
        <span className="min-w-0 flex-1">
          <span className="block truncate text-body font-medium text-ink">{row.title}</span>
          {sub !== "" && <span className="block text-meta text-ink-3">{sub}</span>}
        </span>
        <RegistryStatus object="deliverable" code={row.status} client />
      </button>
    </li>
  );
}

function Rail({
  data,
  selected,
  onSelect,
}: {
  data: DeliverablesOut;
  selected: Selected | null;
  onSelect: (s: Selected) => void;
}): JSX.Element {
  const now = useNow();
  const band = (b: DeliverableBandOut): JSX.Element => (
    <section key={b.key} aria-label={b.label}>
      <h3 className="flex h-[31px] items-center bg-band-hd px-[10px] text-dense font-medium">
        {b.label}
      </h3>
      <ul className="py-[2px]">
        {b.rows.map((r) => (
          <RailRow
            key={r.id}
            row={r}
            selected={selected?.kind === "deliverable" && selected.id === r.id}
            onSelect={() => {
              onSelect({ kind: "deliverable", id: r.id });
            }}
          />
        ))}
      </ul>
    </section>
  );
  const k1 = (r: K1RowOut): JSX.Element => {
    const on = selected?.kind === "k1" && selected.id === r.package_id;
    return (
      <li key={r.package_id}>
        <button
          type="button"
          data-k1-row={r.package_id}
          aria-current={on ? "true" : undefined}
          onClick={() => {
            onSelect({ kind: "k1", id: r.package_id });
          }}
          className={`flex min-h-[52px] w-full items-center gap-[8px] rounded-nested px-[10px] text-left ${on ? "bg-sel-bg" : "hover:bg-nested"}`}
        >
          <Icon name="file-text" size={15} className="text-ink-3" />
          <span className="min-w-0 flex-1 text-body font-medium text-ink">{r.title}</span>
          <Pill variant="green-tint">{COPY.k1Released(formatDate(r.released_on, { now }))}</Pill>
        </button>
      </li>
    );
  };
  return (
    <nav aria-label={COPY.title} className="flex flex-col">
      {data.bands.map(band)}
      {data.k1s.length > 0 && (
        <section aria-label={COPY.myK1s}>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[10px] text-dense font-medium">
            {COPY.myK1s}
          </h3>
          <ul className="py-[2px]">{data.k1s.map(k1)}</ul>
        </section>
      )}
      {data.coming_next.length > 0 && (
        <section aria-label={COPY.comingNext}>
          <h3 className="flex h-[31px] items-center bg-band-hd px-[10px] text-dense font-medium">
            {COPY.comingNext}
          </h3>
          <ul className="py-[2px]">
            {data.coming_next.map((c) => (
              <li
                key={c.label}
                data-coming-next
                className="flex min-h-[52px] items-center gap-[8px] px-[10px]"
              >
                <Icon name="circle" size={15} className="text-ink-3" />
                <span className="min-w-0 flex-1">
                  <span className="block text-body font-medium text-ink">{c.label}</span>
                  {c.expected !== null && c.expected !== undefined && (
                    <span className="block text-meta text-ink-3">{c.expected}</span>
                  )}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </nav>
  );
}

/** One server page image (PNG), through the generated client as a blob URL. */
function PageImage({
  deliverableId,
  version,
  page,
  zoom,
}: {
  deliverableId: string;
  version: number;
  page: number;
  zoom: number;
}): JSX.Element {
  const image = useQuery({
    queryKey: ["deliverable-page", deliverableId, version, page],
    queryFn: async () => {
      const { data } = await getDeliverablePage({
        path: { deliverable_id: deliverableId, version_no: version, page },
        parseAs: "blob",
        throwOnError: true,
      });
      return data as unknown as Blob;
    },
    retry: false,
  });
  const [src, setSrc] = useState<string | null>(null);
  useEffect(() => {
    if (image.data === undefined) return undefined;
    const url = URL.createObjectURL(image.data);
    setSrc(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [image.data]);
  return src === null ? (
    <div aria-busy="true" className="h-[776px] w-full rounded-[6px] bg-card" />
  ) : (
    <img
      src={src}
      alt={`Page ${String(page)}`}
      data-page={page}
      style={{ width: `${String(600 * zoom)}px` }}
      className="block max-w-none"
    />
  );
}

function Comments({
  deliverableId,
  version,
}: {
  deliverableId: string;
  version: DeliverableVersionOut;
}): JSX.Element | null {
  const now = useNow();
  const listed = useQuery({
    ...listPageCommentsOptions({
      path: { deliverable_id: deliverableId, version_no: version.version_no },
    }),
    enabled: version.page_comments && version.allowed_actions.includes("comment"),
    retry: false,
  });
  if (!version.page_comments) return null;
  const threads = listed.data?.items ?? [];
  return (
    <aside aria-label="Comments" className="flex w-[280px] shrink-0 flex-col bg-card hairline-l">
      <h3 className="flex h-[44px] items-center px-[12px] text-body font-medium">
        {COPY.comments(threads.length)}
      </h3>
      <ol className="flex flex-col gap-[8px] px-[12px]">
        {threads.map((c, i) => (
          <li key={c.id} data-comment={c.id} className="rounded-nested p-[12px] shadow-e1">
            <p className="flex items-center gap-[6px] text-meta text-ink-3">
              <span className="inline-flex size-[18px] items-center justify-center rounded-full bg-ink text-[10.5px] font-medium text-card">
                {i + 1}
              </span>
              {`Page ${String(c.page)}${c.line_ref ? ` · ${c.line_ref}` : ""}`}
            </p>
            <p className="pt-[4px] text-dense font-medium">
              {c.author} · {formatDate(c.created_at, { now })}
            </p>
            <p className="whitespace-pre-wrap text-[12.5px] leading-[1.5]">{c.body}</p>
          </li>
        ))}
      </ol>
      {version.allowed_actions.includes("comment") && (
        <div className="mt-auto px-[12px] pb-[12px]">
          <div className="flex h-[40px] items-center rounded-nested bg-nested px-[10px] text-dense text-ink-3">
            {COPY.composer}
          </div>
          <p className="pt-[6px] text-meta text-ink-3">{COPY.composerHint}</p>
        </div>
      )}
    </aside>
  );
}

function Viewer({
  deliverable,
  mobile,
  initialPage,
  confirming,
}: {
  deliverable: DeliverableOut;
  mobile: boolean;
  initialPage: number;
  confirming: boolean;
}): JSX.Element {
  const now = useNow();
  const queryClient = useQueryClient();
  const latest = deliverable.versions[deliverable.versions.length - 1];
  const [page, setPage] = useState(initialPage);
  const [zoom, setZoom] = useState<(typeof ZOOMS)[number]>(1);
  const [confirm, setConfirm] = useState(confirming);
  const approve = useMutation({
    ...approveDeliverableMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
    onError: () => {
      toast.show(COPY.newerDraft);
      void queryClient.invalidateQueries();
    },
  });
  if (latest === undefined) return <EmptyState title={COPY.empty}>{COPY.emptyBody}</EmptyState>;
  const draft = latest.is_draft;
  const pages = latest.page_count;
  const canApprove = latest.allowed_actions.includes("approve");
  const canDownload = latest.allowed_actions.includes("download");
  const approved = deliverable.status === "approved_by_you";
  const doDownload = async (): Promise<void> => {
    try {
      const { data } = await downloadDeliverable({
        path: { deliverable_id: deliverable.id, version_no: latest.version_no },
        parseAs: "blob",
        throwOnError: true,
      });
      await save(data as unknown as Blob, `${deliverable.title}.pdf`);
    } catch {
      toast.show(COPY.downloadFailed);
    }
  };
  const approveButton = canApprove && (
    <Button
      size={mobile ? "lg" : "sm"}
      onClick={() => {
        setConfirm(true);
      }}
      className={mobile ? "w-full" : ""}
    >
      {mobile ? COPY.approveMobile : COPY.approve}
    </Button>
  );
  const header = (
    <header className="flex h-[46px] shrink-0 items-center gap-[10px] px-[12px] hairline-b">
      <h2 className="min-w-0 truncate text-[13.5px] font-medium">
        {draft ? `${deliverable.title} — draft v${String(latest.version_no)}` : deliverable.title}
      </h2>
      {draft && !approved && <Pill variant="amber">{COPY.draftForReview}</Pill>}
      {approved && (
        <RegistryStatus object="deliverable" code="approved_by_you" client />
      )}
      <div className="mx-auto flex items-center gap-[6px]">
        <span className="inline-flex items-center gap-[2px] rounded-pill bg-card p-[3px] shadow-e1">
          <button
            type="button"
            aria-label={COPY.previous}
            disabled={page <= 1}
            onClick={() => {
              setPage(page - 1);
            }}
            className="inline-flex h-[26px] min-w-[27px] items-center justify-center rounded-pill disabled:text-ink-4"
          >
            <Icon name="chevron-up" size={13} />
          </button>
          <span className="px-[6px] text-dense tabular-nums">{COPY.page(page, pages)}</span>
          <button
            type="button"
            aria-label={COPY.next}
            disabled={page >= pages}
            onClick={() => {
              setPage(page + 1);
            }}
            className="inline-flex h-[26px] min-w-[27px] items-center justify-center rounded-pill disabled:text-ink-4"
          >
            <Icon name="chevron-down" size={13} />
          </button>
        </span>
        {!mobile && (
          <span className="inline-flex items-center gap-[2px] rounded-pill bg-card p-[3px] shadow-e1">
            <button
              type="button"
              aria-label={COPY.zoomOut}
              disabled={zoom === ZOOMS[0]}
              onClick={() => {
                setZoom(ZOOMS[Math.max(0, ZOOMS.indexOf(zoom) - 1)] ?? 1);
              }}
              className="inline-flex h-[26px] min-w-[27px] items-center justify-center rounded-pill disabled:text-ink-4"
            >
              <Icon name="zoom-out" size={13} />
            </button>
            <button
              type="button"
              onClick={() => {
                setZoom(1);
              }}
              className="inline-flex h-[26px] items-center rounded-pill px-[6px] text-dense"
            >
              {COPY.fit}
            </button>
            <button
              type="button"
              aria-label={COPY.zoomIn}
              disabled={zoom === ZOOMS[ZOOMS.length - 1]}
              onClick={() => {
                setZoom(ZOOMS[Math.min(ZOOMS.length - 1, ZOOMS.indexOf(zoom) + 1)] ?? 1);
              }}
              className="inline-flex h-[26px] min-w-[27px] items-center justify-center rounded-pill disabled:text-ink-4"
            >
              <Icon name="zoom-in" size={13} />
            </button>
          </span>
        )}
      </div>
      {canDownload && (
        <Button
          size="sm"
          variant={draft ? "ghost" : "primary"}
          onClick={() => {
            void doDownload();
          }}
        >
          {draft ? COPY.downloadDraft : COPY.download}
        </Button>
      )}
      {!mobile && approveButton}
    </header>
  );
  return (
    <section aria-label={deliverable.title} className="flex min-h-0 flex-1 flex-col">
      {header}
      {approved && <p className="px-[12px] py-[6px] text-[12.5px] text-ink-3">{COPY.approvedNote}</p>}
      <div className="flex min-h-0 flex-1">
        <div className="relative min-h-0 flex-1 overflow-auto bg-shell p-[14px]">
          <div className="relative mx-auto w-fit overflow-hidden rounded-[6px] shadow-page">
            <PageImage
              deliverableId={deliverable.id}
              version={latest.version_no}
              page={page}
              zoom={mobile ? 0.6 : zoom}
            />
            {draft && (
              <span
                aria-hidden="true"
                data-watermark="draft"
                className="pointer-events-none absolute inset-0 flex -rotate-[30deg] items-center justify-center text-[72px] font-medium text-ink/[.06]"
              >
                DRAFT
              </span>
            )}
            {deliverable.legend_kind === "ar_c_70" && (
              <p data-legend="ar_c_70" className="bg-card px-[36px] pb-[12px] text-[10.5px] text-ink-3">
                {COPY.legend}
              </p>
            )}
          </div>
        </div>
        {!mobile && <Comments deliverableId={deliverable.id} version={latest} />}
      </div>
      {mobile && approveButton !== false && (
        <div className="sticky bottom-0 bg-card p-[12px] hairline-t" data-sticky-approve>
          {approveButton}
        </div>
      )}
      <ConfirmDialog
        open={confirm && canApprove}
        onOpenChange={setConfirm}
        title={COPY.approveTitle}
        confirmLabel={COPY.approveConfirm}
        destructive={false}
        onConfirm={() => {
          approve.mutate({
            path: { deliverable_id: deliverable.id, version_no: latest.version_no },
            body: { seen_hash: latest.seen_hash },
            headers: { "Idempotency-Key": `${deliverable.id}:${latest.seen_hash}` },
          });
        }}
      />
      {latest.withdrawn_on !== null && latest.withdrawn_on !== undefined && (
        <p className="px-[12px] text-meta text-ink-3">
          {COPY.newerDraft} · {formatDate(latest.withdrawn_on, { now })}
        </p>
      )}
    </section>
  );
}

function K1Summary({ packageId }: { packageId: string }): JSX.Element | null {
  const branding = useBranding();
  const rows = useQuery(portalK1sOptions());
  const row = (rows.data ?? []).find((r) => r.id === packageId);
  if (row === undefined) return null;
  return (
    <section aria-label={row.issuer_name ?? COPY.myK1s} className="flex flex-col gap-[10px] p-[14px]">
      <PackageCard
        row={row}
        firm={branding.data?.firm_name ?? ""}
        showDetails={false}
        opening={undefined}
      />
      <p className="text-[12.5px] text-ink-2">{COPY.k1Added}</p>
    </section>
  );
}

function Deliverables(props: Por09Props): JSX.Element {
  const bar = usePortalToolbar(null);
  const listed = useQuery({
    ...listDeliverablesOptions(props.section === undefined ? {} : { query: { section: props.section } }),
    retry: false,
  });
  const [selected, setSelected] = useState<Selected | null>(
    props.deliverableId === undefined ? null : { kind: "deliverable", id: props.deliverableId },
  );
  const current = selected ?? firstSelection(listed.data, props.section);
  const open = useQuery({
    ...getDeliverableOptions({
      path: { deliverable_id: current?.kind === "deliverable" ? current.id : "" },
    }),
    enabled: current?.kind === "deliverable",
    retry: false,
  });
  const mobile = props.mobile === true;
  const flagOff = listed.isError && isFlagOff(listed.error);
  const empty =
    listed.data !== undefined &&
    listed.data.bands.every((b) => b.rows.length === 0) &&
    listed.data.k1s.length === 0;

  let main: JSX.Element | null = null;
  if (flagOff) {
    main = <EmptyState title={COPY.flagOff} icon="file-text" />;
  } else if (empty) {
    main = (
      <EmptyState title={COPY.empty} icon="file-text">
        {COPY.emptyBody}
      </EmptyState>
    );
  } else if (current?.kind === "k1") {
    main = <K1Summary packageId={current.id} />;
  } else if (open.data !== undefined) {
    main = (
      <Viewer
        key={open.data.id}
        deliverable={open.data}
        mobile={mobile}
        initialPage={props.page ?? 1}
        confirming={props.confirming === true}
      />
    );
  }

  const rail =
    listed.data === undefined || flagOff || empty ? null : (
      <Rail data={listed.data} selected={current} onSelect={setSelected} />
    );
  return (
    <PortalLayout
      variant={mobile ? "mobile" : "split"}
      user={bar?.user ?? ""}
      nav={bar?.nav ?? []}
      active={COPY.active}
      frame={props.frame === true}
      {...(props.onNavigate === undefined ? {} : { onNavigate: props.onNavigate })}
    >
      <div data-screen="POR-09" className={`flex min-h-0 flex-1 gap-[10px] ${mobile ? "flex-col" : ""}`}>
        {rail !== null && (
          <section
            aria-label={COPY.title}
            className={`${mobile ? "" : "w-[336px] shrink-0"} overflow-y-auto rounded-pane bg-card p-[10px] shadow-e2`}
          >
            <h2 className="flex h-[46px] items-center text-[14.5px] font-medium">{COPY.title}</h2>
            {rail}
          </section>
        )}
        <div className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e2">
          {main}
        </div>
      </div>
    </PortalLayout>
  );
}

export function POR09(props: Por09Props = {}): JSX.Element | null {
  const branding = useBranding();
  if (branding.data === undefined) return null;
  return (
    <PortalBrandProvider brand={brandOf(branding.data)}>
      <Deliverables {...props} />
    </PortalBrandProvider>
  );
}
