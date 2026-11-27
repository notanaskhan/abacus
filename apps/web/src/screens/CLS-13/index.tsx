// CLS-13 · 1099 / W-9 tracker (C-02-T47; TASK-9025; DEC-6030; T1 IndexList). One client entity's
// vendors for a tax year from C-02-T45's read (`GET …/information-returns`): code classified each
// vendor (ADR-050) and computed the tiles; the browser formats, masks nothing itself (the server
// sends only the last four), filters the shown rows by name and form, and never sums or decides.
// Requests (W-9s), backup withholding and the batch approval are a person's acts on C8's routes;
// the vendor link channel is shown unavailable until R-03's link principal (DEC-5509).
import type { DeliveryInformationReturnsOut, DeliveryVendorRowOut } from "@abacus/api-client";
import {
  backupWithholdingMutation,
  informationReturnsOptions,
  informationReturnsQueryKey,
  w9RequestMutation,
} from "@abacus/api-client/query";
import {
  Button,
  DASH,
  Dialog,
  Drawer,
  EmptyState,
  FilterChip,
  Icon,
  Label,
  Pane,
  Pill,
  SearchField,
  Skeleton,
  StatusTile,
  Tag,
  amount,
  cn,
  date,
  einMask,
  ssnMask,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { type JSX, type ReactNode, useState } from "react";
import { useNow } from "../../app-core/clock";
import { useOpenOverlay } from "../../app-core/open";
import { VIEWER_OVERLAY, sourceViewerArgs } from "../../app-core/overlays";
import { to } from "../../routes/to";
import { COPY as C } from "./copy";

type Row = DeliveryVendorRowOut;
type FormFilter = "nec" | "misc" | "exempt";
type W9Filter = "on_file" | "requested" | "tin_mismatch";

export interface CLS13Props {
  clientEntityId: string;
  taxYear?: number;
  onTaxYear?: (year: number) => void;
  /** b: the W-9 request drawer opens with the page (`?w9=1`). */
  requestOpen?: boolean;
  /** c: a TIN-mismatch row expanded (`?vendor=`). */
  expandedVendorId?: string | null;
}

const TH = "h-[30px] bg-thead px-[10px] text-left text-[11.5px] font-medium text-ink-2";
const TD = "px-[10px] text-[13px]";

function idempotency(prefix: string): { "Idempotency-Key": string } {
  return { "Idempotency-Key": `${prefix}-${crypto.randomUUID()}` };
}

function money(v: string | number): string {
  return amount(String(v), "money").text;
}

/** What the vendor was paid: the server's counted amount, or for a vendor paid only by card the
 * card payments' total the server sent (never summed here, ADR-050). */
function paid(r: Row): string {
  if (r.reportability === "paid_by_card") {
    const card = (r.payments ?? []).find((p) => p.method === "card");
    if (card !== undefined) return money(card.amount);
  }
  return money(r.amount);
}

function entityLabel(r: Row): string {
  if (r.entity_type === "unknown") return DASH;
  if (r.is_attorney && r.entity_type === "partnership") return C.entity.attorney ?? DASH;
  return C.entity[r.entity_type] ?? DASH;
}

function tin(r: Row): string {
  if (!r.tin_last4) return DASH;
  return r.tin_kind === "ssn" ? ssnMask(r.tin_last4) : einMask(r.tin_last4);
}

function formText(r: Row): { text: string; muted: boolean } {
  if (r.reportability === "paid_by_card") return { text: C.form.card, muted: true };
  if (r.reportability === "exempt_corporation") return { text: C.form.exempt, muted: true };
  if (r.form === "misc") return { text: C.form.misc(r.box ?? null), muted: false };
  return { text: r.is_attorney ? C.form.attorney : C.form.nec, muted: false };
}

function thresholdOf(rule: string): string | null {
  return /threshold (\$[\d,]+)/.exec(rule)?.[1] ?? null;
}

function formOf(r: Row): FormFilter | null {
  if (r.reportability === "exempt_corporation") return "exempt";
  return r.form ?? null;
}

function W9Pill({ r, now }: { r: Row; now: Date }): JSX.Element {
  if (r.w9_status === "on_file") return <Pill variant="green-tint">{C.w9.on_file}</Pill>;
  if (r.w9_status === "tin_mismatch") return <Pill variant="red-tint">{C.w9.tin_mismatch}</Pill>;
  if (r.w9_status === "requested") {
    return (
      <Pill variant="amber">
        {C.w9.requested(r.w9_requested_at ? date(r.w9_requested_at, { now }) : null)}
      </Pill>
    );
  }
  return <span className="text-ink-3">{DASH}</span>;
}

function EFile({
  r,
  view,
  now,
}: {
  r: Row;
  view: DeliveryInformationReturnsOut;
  now: Date;
}): JSX.Element {
  if (r.filed === true && view.batch_status === "accepted") {
    return (
      <span className="flex flex-col items-start gap-[2px]">
        <Pill variant="green">
          <Icon name="check" size={12} />
          {C.efile.accepted}
        </Pill>
        {view.accepted_at ? (
          <span className="text-[11.5px] text-ink-3">
            {date(view.accepted_at, { now, withYear: true })}
          </span>
        ) : null}
      </span>
    );
  }
  if (r.filed === true) return <Pill variant="green-tint">{C.efile.filed}</Pill>;
  if (r.reportability === "reportable") {
    return <Pill variant="neutral">{C.efile.notStarted}</Pill>;
  }
  return <span className="text-ink-3">{DASH}</span>;
}

function MismatchPanel({
  r,
  now,
  onRequest,
  onBackup,
}: {
  r: Row;
  now: Date;
  onRequest: () => void;
  onBackup: () => void;
}): JSX.Element {
  return (
    <tr data-mismatch={r.vendor_id}>
      <td colSpan={9} className="bg-red-tint/40 px-[14px] py-[10px]">
        <p className="max-w-[920px] text-[12.5px] leading-[1.45]">
          {C.mismatch.text(r.tin_mismatch_on ? date(r.tin_mismatch_on, { now }) : DASH)}
        </p>
        <span className="mt-[8px] flex gap-[8px]">
          <Button variant="secondary" size="sm" opensDialog onClick={onRequest}>
            {C.mismatch.requestCorrected}
          </Button>
          <Button variant="ghost" size="sm" opensDialog onClick={onBackup}>
            {C.mismatch.markStarted}
          </Button>
        </span>
      </td>
    </tr>
  );
}

function VendorDrawer({
  r,
  year,
  onClose,
}: {
  r: Row;
  year: number;
  onClose: () => void;
}): JSX.Element {
  const openOverlay = useOpenOverlay();
  const evidence = r.w9_evidence_version_id ?? null;
  return (
    <Drawer
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={r.display_name}
      description={C.paidYear(year)}
    >
      <section
        aria-label={C.drawer.payments}
        className="rounded-nested bg-card"
        data-cls13="payments"
      >
        <div className="flex h-[36px] items-center justify-between px-[14px] hairline-b">
          <h3 className="text-[13px] font-medium">{C.drawer.payments}</h3>
          <span className="text-[12px] text-ink-3">{C.drawer.source}</span>
        </div>
        <ul>
          {(r.payments ?? []).map((p) => (
            <li
              key={p.method}
              data-method={p.method}
              className="flex h-[36px] items-center gap-[10px] px-[14px] text-[13px] hairline-b"
            >
              <span className="flex-1">{C.drawer.method[p.method] ?? p.method}</span>
              <span className={cn("text-[11.5px]", p.counted ? "text-ink-3" : "text-amber-ink")}>
                {p.counted ? C.drawer.counted : C.drawer.excluded}
              </span>
              <span className="w-[110px] text-right tabular-nums">{money(p.amount)}</span>
            </li>
          ))}
        </ul>
      </section>
      <section aria-label={C.drawer.w9} className="mt-[10px] rounded-nested bg-card p-[14px]">
        <h3 className="pb-[6px] text-[13px] font-medium">{C.drawer.w9}</h3>
        {evidence === null ? (
          <p className="text-[12.5px] text-ink-3">{C.drawer.noW9}</p>
        ) : (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              openOverlay({
                key: VIEWER_OVERLAY,
                args: sourceViewerArgs({ evidenceVersionId: evidence }),
              });
            }}
          >
            {C.drawer.openW9}
          </Button>
        )}
      </section>
    </Drawer>
  );
}

function RequestDrawer({
  rows,
  client,
  clientEntityId,
  onClose,
  onSent,
}: {
  rows: readonly Row[];
  client: string;
  clientEntityId: string;
  onClose: () => void;
  onSent: () => void;
}): JSX.Element {
  const send = useMutation({
    ...w9RequestMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: C.request.sent(rows.length) });
      onSent();
    },
    onError: () => {
      toast.show({ kind: "error", text: C.failedToLoad });
    },
  });
  return (
    <Drawer
      open
      size="md"
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={C.request.title}
      footer={
        <span className="flex w-full justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {C.request.cancel}
          </Button>
          <Button
            variant="primary"
            disabled={rows.length === 0 || send.isPending}
            onClick={() => {
              send.mutate({
                path: { client_entity_id: clientEntityId },
                body: { vendor_ids: rows.map((r) => r.vendor_id), channel: "portal" },
                headers: idempotency("cls13-w9"),
              });
            }}
          >
            {C.request.send(rows.length)}
          </Button>
        </span>
      }
    >
      <div className="flex flex-col gap-[10px]" data-cls13="request">
        <ul className="rounded-nested bg-card">
          {rows.map((r) => (
            <li
              key={r.vendor_id}
              className="flex h-[40px] items-center justify-between px-[14px] text-[13px] hairline-b"
            >
              <span>{r.display_name}</span>
              <span className="tabular-nums">{paid(r)}</span>
            </li>
          ))}
        </ul>
        <fieldset className="flex flex-col gap-[8px] rounded-nested bg-card p-[14px] text-[13px]">
          <label className="flex items-center gap-[8px]">
            <input type="radio" name="cls13-channel" defaultChecked />
            {C.request.portal(client)}
          </label>
          <label className="flex items-center gap-[8px] text-ink-3">
            <input type="radio" name="cls13-channel" disabled aria-describedby="cls13-link-off" />
            {C.request.vendorLink}
            <span id="cls13-link-off" className="text-[11.5px]">
              {C.request.unavailable}
            </span>
          </label>
        </fieldset>
        <section aria-label={C.request.wordingLabel} className="rounded-nested bg-nested p-[14px]">
          <h3 className="pb-[4px] text-[11.5px] text-ink-3">{C.request.wordingLabel}</h3>
          <p className="text-[13px]">{C.request.wording}</p>
        </section>
      </div>
    </Drawer>
  );
}

function BackupDialog({
  r,
  onClose,
  onDone,
}: {
  r: Row;
  onClose: () => void;
  onDone: () => void;
}): JSX.Element {
  const [reason, setReason] = useState("");
  const mark = useMutation({
    ...backupWithholdingMutation(),
    onSuccess: () => {
      toast.show({ kind: "success", text: C.backupDialog.done(r.display_name) });
      onDone();
    },
    onError: () => {
      toast.show({ kind: "error", text: C.failedToLoad });
    },
  });
  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
      title={C.backupDialog.title}
    >
      <div className="flex flex-col gap-[12px]" data-cls13="backup-dialog">
        <p className="text-[13px] text-ink-2">{C.backupDialog.body(r.display_name)}</p>
        <span className="flex flex-col gap-[4px]">
          <Label htmlFor="cls13-backup-reason">{C.backupDialog.reason}</Label>
          <textarea
            id="cls13-backup-reason"
            rows={2}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="w-full rounded-control border border-stroke bg-card p-2 text-body text-ink"
          />
        </span>
        <div className="flex justify-end gap-[8px]">
          <Button variant="secondary" onClick={onClose}>
            {C.backupDialog.cancel}
          </Button>
          <Button
            variant="primary"
            disabled={reason.trim() === "" || mark.isPending}
            onClick={() => {
              mark.mutate({
                path: { vendor_id: r.vendor_id },
                body: { event: "started", reason: reason.trim() },
              });
            }}
          >
            {C.backupDialog.confirm}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}

export function CLS13({
  clientEntityId,
  taxYear: yearProp,
  onTaxYear,
  requestOpen = false,
  expandedVendorId = null,
}: CLS13Props): JSX.Element {
  const now = useNow();
  const queries = useQueryClient();
  const [ownYear, setOwnYear] = useState<number>(yearProp ?? 2026);
  const year = yearProp ?? ownYear;
  const [w9, setW9] = useState<W9Filter | null>(null);
  const [formFilter, setFormFilter] = useState<FormFilter | null>(null);
  const [search, setSearch] = useState("");
  const [expanded, setExpanded] = useState<string | null>(expandedVendorId);
  const [drawer, setDrawer] = useState<string | null>(null);
  const [request, setRequest] = useState<readonly Row[] | null>(null);
  const [backup, setBackup] = useState<Row | null>(null);
  const [requestedOnce, setRequestedOnce] = useState(requestOpen);
  const path = { client_entity_id: clientEntityId };
  const q = useQuery(
    informationReturnsOptions({
      path,
      query: { tax_year: year, ...(w9 === null ? {} : { w9 }) },
    }),
  );
  const refresh = (): void => {
    void queries.invalidateQueries({
      queryKey: informationReturnsQueryKey({ path, query: { tax_year: year } }),
    });
    void queries.invalidateQueries({ queryKey: ["informationReturns"] });
  };

  if (q.isPending) {
    return (
      <div data-screen="CLS-13" aria-busy="true" className="flex flex-col gap-[10px] p-[12px]">
        <Skeleton className="h-[42px] w-full" />
        <Skeleton className="h-[72px] w-[640px]" />
        <Skeleton className="h-[600px] w-full" />
      </div>
    );
  }
  if (q.isError) {
    return (
      <div
        data-screen="CLS-13"
        role="alert"
        className="flex flex-col items-start gap-[8px] p-[24px]"
      >
        <p className="text-[13px]">{C.failedToLoad}</p>
        <Button variant="secondary" size="sm" onClick={() => void q.refetch()}>
          {C.retry}
        </Button>
      </div>
    );
  }
  const view = q.data;
  const client = "Copperleaf Coffee Roasters, Inc.";
  const needle = search.trim().toLowerCase();
  const rows = view.items.filter(
    (r) =>
      (needle === "" || r.display_name.toLowerCase().includes(needle)) &&
      (formFilter === null || formOf(r) === formFilter),
  );
  // A W-9 is asked of a vendor paid this year who could need a 1099 (not card-only, not a
  // corporation the W-9 already exempts).
  const toRequest = view.items.filter(
    (r) =>
      (r.w9_status === "requested" || r.w9_status === "missing") &&
      (r.reportability === "reportable" || r.reportability === "below_threshold"),
  );
  const threshold = thresholdOf(view.threshold_rule);
  const synced = view.payments_synced !== false;
  const empty = synced && view.items.length === 0 && w9 === null;
  const chooseYear = (y: number): void => {
    setOwnYear(y);
    onTaxYear?.(y);
  };
  const openRequest = requestedOnce && request === null ? toRequest : request;
  const approveTarget = view.approval_target_on
    ? date(view.approval_target_on, { now, withYear: true })
    : null;

  return (
    <div data-screen="CLS-13" className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[42px] items-center px-[12px]">
        <Link
          {...to.CLS01()}
          className="z-10 flex h-[29px] items-center gap-[4px] rounded-full bg-card px-[10px] text-[13px] shadow-e1"
        >
          <Icon name="chevron-left" size={14} />
          {C.back}
        </Link>
        <h1 className="absolute inset-x-0 flex items-center justify-center gap-[8px] text-[15px]">
          <span className="font-medium">{C.title}</span>
          <span className="text-ink-2">{client}</span>
          <Tag>{C.taxYear(view.tax_year)}</Tag>
        </h1>
      </div>
      <div className="flex h-[50px] items-center gap-[8px] px-[12px]">
        <FilterChip
          label={C.filters.client}
          icon="building-2"
          options={[{ value: clientEntityId, label: client }]}
          value={clientEntityId}
        />
        <FilterChip
          label={C.filters.taxYear}
          icon="calendar"
          options={[
            { value: "2026", label: "2026" },
            { value: "2025", label: "2025" },
          ]}
          value={String(year)}
          onChange={(v) => {
            if (v !== null) chooseYear(Number(v));
          }}
        />
        <FilterChip
          label={C.filters.w9}
          icon="file-check"
          options={(["on_file", "requested", "tin_mismatch"] as const).map((k) => ({
            value: k,
            label: C.filters.w9Options[k],
          }))}
          value={w9}
          placeholder={C.filters.all}
          onChange={(v) => {
            setW9(v as W9Filter | null);
          }}
        />
        <FilterChip
          label={C.filters.form}
          icon="file-text"
          options={(["nec", "misc", "exempt"] as const).map((k) => ({
            value: k,
            label: C.filters.formOptions[k],
          }))}
          value={formFilter}
          placeholder={C.filters.all}
          onChange={(v) => {
            setFormFilter(v as FormFilter | null);
          }}
        />
      </div>
      <div className="flex items-end gap-[8px] px-[12px] pb-[10px]" data-cls13="tiles">
        {synced ? (
          <StatusTile count={view.vendors_paid} label={C.tiles.vendorsPaid} variant="neutral" />
        ) : (
          // CLS-13 e: a year whose payments never synced shows no Vendors paid figure.
          <div
            className="flex h-[72px] w-[120px] flex-col items-center justify-center gap-[7px] rounded-pane bg-card shadow-e1"
            data-cls13="vendors-paid-none"
          >
            <span className="text-[22px] text-ink-3">{DASH}</span>
            <Pill variant="neutral" size="state">
              {C.tiles.vendorsPaid}
            </Pill>
          </div>
        )}
        <StatusTile count={view.reportable} label={C.tiles.reportable} variant="state" />
        <StatusTile count={view.requested} label={C.tiles.requested} variant="amber" />
        <StatusTile count={view.w9_mismatches} label={C.tiles.mismatch} variant="red-tint" />
        <StatusTile count={view.filed} label={C.tiles.filed} variant="neutral" />
        <span className="flex-1" />
        <span className="max-w-[720px] pb-[2px] text-right text-[12.5px] leading-[1.4] text-ink-3">
          <span className="block">{view.threshold_rule}</span>
          {view.due_rule ? <span className="block">{view.due_rule}</span> : null}
        </span>
      </div>
      <div className="flex min-h-0 flex-1 px-[12px] pb-[12px]">
        <Pane
          title={C.pane}
          left={
            <SearchField
              label={C.search}
              placeholder={C.search}
              value={search}
              onChange={setSearch}
            />
          }
          right={
            <span className="flex gap-[8px]">
              <Button
                variant="secondary"
                size="sm"
                opensDialog
                disabled={toRequest.length === 0 || !synced}
                onClick={() => {
                  setRequest(toRequest);
                }}
              >
                {C.requestW9s(toRequest.length)}
              </Button>
              <Button
                variant="primary"
                size="sm"
                opensDialog
                disabled={!view.approval_open || view.batch_status !== "not_started"}
                title={view.approval_open ? undefined : C.approveClosed(approveTarget)}
                data-cls13="approve"
              >
                {C.approve}
              </Button>
            </span>
          }
        >
          {empty ? (
            <EmptyState icon="receipt" title={C.empty.title}>
              <Button variant="secondary" size="sm">
                {C.empty.connect}
              </Button>
            </EmptyState>
          ) : (
            <table className="w-full border-collapse" data-cls13="vendors">
              <thead>
                <tr className="hairline-b">
                  {C.columns.map((h, i) => (
                    <th key={h} scope="col" className={cn(TH, i === 5 && "text-right")}>
                      {i === 5 ? C.paidYear(view.tax_year) : h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => {
                  const f = formText(r);
                  const isOpen = expanded === r.vendor_id && r.w9_status === "tin_mismatch";
                  return (
                    <RowGroup key={r.vendor_id}>
                      <tr className="h-[40px] hairline-b" data-vendor={r.display_name}>
                        <td className={cn(TD, "font-medium")}>
                          <button
                            type="button"
                            className="text-left font-medium"
                            onClick={() => {
                              setDrawer(r.vendor_id);
                            }}
                          >
                            {r.display_name}
                          </button>
                          {r.w9_status === "tin_mismatch" ? (
                            <button
                              type="button"
                              aria-expanded={isOpen}
                              aria-label={isOpen ? C.mismatch.collapse : C.mismatch.expand}
                              className="ml-[6px] align-middle text-ink-3"
                              onClick={() => {
                                setExpanded(isOpen ? null : r.vendor_id);
                              }}
                            >
                              <Icon name={isOpen ? "chevron-up" : "chevron-down"} size={14} />
                            </button>
                          ) : null}
                        </td>
                        <td className={TD}>{entityLabel(r)}</td>
                        <td className={TD}>
                          <W9Pill r={r} now={now} />
                        </td>
                        <td className={cn(TD, "tabular-nums")} data-tin>
                          {tin(r)}
                        </td>
                        <td className={cn(TD, f.muted && "text-ink-3")}>{f.text}</td>
                        <td className={cn(TD, "text-right tabular-nums")}>{paid(r)}</td>
                        <td className={TD}>
                          <ThresholdCell r={r} threshold={threshold} />
                        </td>
                        <td className={TD}>
                          {r.backup_withholding === "watch" ||
                          r.backup_withholding === "started" ? (
                            <Pill variant="amber">{C.backup[r.backup_withholding]}</Pill>
                          ) : (
                            <span className="text-ink-3">{DASH}</span>
                          )}
                        </td>
                        <td className={cn(TD, "py-[6px]")}>
                          <EFile r={r} view={view} now={now} />
                        </td>
                      </tr>
                      {isOpen ? (
                        <MismatchPanel
                          r={r}
                          now={now}
                          onRequest={() => {
                            setRequest([r]);
                          }}
                          onBackup={() => {
                            setBackup(r);
                          }}
                        />
                      ) : null}
                    </RowGroup>
                  );
                })}
              </tbody>
            </table>
          )}
        </Pane>
      </div>
      {drawer !== null
        ? (() => {
            const r = view.items.find((x) => x.vendor_id === drawer);
            return r === undefined ? null : (
              <VendorDrawer
                r={r}
                year={view.tax_year}
                onClose={() => {
                  setDrawer(null);
                }}
              />
            );
          })()
        : null}
      {openRequest !== null ? (
        <RequestDrawer
          rows={openRequest}
          client={client}
          clientEntityId={clientEntityId}
          onClose={() => {
            setRequest(null);
            setRequestedOnce(false);
          }}
          onSent={() => {
            setRequest(null);
            setRequestedOnce(false);
            refresh();
          }}
        />
      ) : null}
      {backup !== null ? (
        <BackupDialog
          r={backup}
          onClose={() => {
            setBackup(null);
          }}
          onDone={() => {
            setBackup(null);
            refresh();
          }}
        />
      ) : null}
    </div>
  );
}

function RowGroup({ children }: { children: ReactNode }): JSX.Element {
  return <>{children}</>;
}

function ThresholdCell({ r, threshold }: { r: Row; threshold: string | null }): JSX.Element {
  switch (r.reportability) {
    case "reportable":
      return r.is_attorney ? (
        <span className="flex flex-col">
          <span>{C.threshold.attorney}</span>
          <span className="text-[11.5px] text-ink-3">{C.threshold.attorneyNote}</span>
        </span>
      ) : (
        <span>{C.threshold.reportable}</span>
      );
    case "below_threshold":
      return <span className="text-ink-3">{C.threshold.below(threshold)}</span>;
    case "exempt_corporation":
      return <span className="text-ink-3">{C.threshold.exempt}</span>;
    case "paid_by_card":
      return <span className="text-ink-3">{C.threshold.card}</span>;
  }
}
