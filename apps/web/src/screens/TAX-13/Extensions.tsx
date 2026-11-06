import type { EstimateRowOut, ExtensionRowOut } from "@abacus/api-client";
import { estimatesExport, extensionsExport } from "@abacus/api-client";
import { extensionsOptions, taxEstimatesOptions } from "@abacus/api-client/query";
import {
  Button,
  EmptyState,
  Pill,
  SearchField,
  Segmented,
  Skeleton,
  Tooltip,
  amount,
  cn,
  date,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { COPY } from "./copy";

// TAX-13 · Extensions, estimates & payments (T-03-T11; T-03 §3 F5; the handoff spec): the T6 workbook
// grammar at `/tax-returns/extensions`. Tallies and rows are the server's (T-03-T07); a tile filters
// the rows. Cells carry no dollar sign. Likely-to-extend rows offer Prepare…, disabled with the
// server's blocked reason in the tooltip (Thornbury's 706 waits on G1 and G3). Nothing here files or
// pays: the firm files and the client pays.

type Tab = keyof typeof COPY.tabs;
type Segment = keyof typeof COPY.segments;
const SEGMENTS: readonly Segment[] = ["open", "filed", "likely"];
const EXTENSION_TILES = ["extended", "open", "filed", "likely", "acks_pending"] as const;
const ESTIMATE_TILES = [
  "due",
  "paid",
  "scheduled",
  "confirmation_requested",
  "not_required",
] as const;
type Tile = (typeof EXTENSION_TILES)[number] | (typeof ESTIMATE_TILES)[number];
const URGENT_DAYS = 7;

const figure = (v: string | null | undefined): string =>
  v === null || v === undefined ? "—" : amount(v, "whole").text.replace("$", "");

function Tiles({
  tiles,
  counts,
  active,
  onTile,
}: {
  tiles: readonly Tile[];
  counts: Record<string, number> | undefined;
  active: Tile | null;
  onTile: (tile: Tile | null) => void;
}): JSX.Element {
  return (
    <div data-tax13="tally" className="flex h-[52px] shrink-0 items-center gap-[10px] px-[12px]">
      {tiles.map((tile) => (
        <button
          key={tile}
          type="button"
          data-tile={tile}
          aria-pressed={active === tile}
          onClick={() => {
            onTile(active === tile ? null : tile);
          }}
          className={cn(
            "flex h-[40px] flex-1 flex-col justify-center rounded-[10px] bg-card px-[12px] text-left shadow-e1",
            active === tile && "ring-[1px] ring-ink",
          )}
        >
          <span className="text-micro font-medium tracking-[.07em] text-ink-3 uppercase">
            {COPY.tiles[tile]}
          </span>
          <span className="text-[13px] font-medium tabular-nums">{counts?.[tile] ?? 0}</span>
        </button>
      ))}
    </div>
  );
}

function ExtensionRow({
  row,
  onReturn,
  onPrepare,
}: {
  row: ExtensionRowOut;
  onReturn?: (id: string) => void;
  onPrepare?: (row: ExtensionRowOut) => void;
}): JSX.Element {
  const now = useNow();
  const urgent = row.days_to_extended_due != null && row.days_to_extended_due <= URGENT_DAYS;
  const line = row.lines[0];
  const blocked = row.prepare_blocked_reason ?? null;
  return (
    <tr
      data-row={row.work_item_id}
      data-client={row.client_name}
      className="h-[40px] text-[12.5px] hairline-t"
    >
      <td className="px-[12px]">
        <button
          type="button"
          className="text-left text-ink hover:underline"
          onClick={() => onReturn?.(row.tax_return_id)}
        >
          {row.client_name}
        </button>
      </td>
      <td>{row.return_form}</td>
      <td>{row.lines.map((l) => l.form).join(" + ")}</td>
      <td>{line?.filed_on == null ? COPY.notFiled : date(line.filed_on, { now })}</td>
      <td>
        {line === undefined || line.status === "not_filed" ? (
          COPY.ack.not_filed
        ) : (
          <Pill
            size="chip"
            variant={
              line.status === "accepted"
                ? "green-tint"
                : line.status === "rejected"
                  ? "red-tint"
                  : "neutral"
            }
          >
            {COPY.ack[line.status]}
          </Pill>
        )}
      </td>
      <td className="text-right tabular-nums">{figure(row.projected_liability)}</td>
      <td className="text-right tabular-nums">{figure(row.withholding_plus_estimates)}</td>
      <td className="text-right tabular-nums">
        {figure(row.safe_harbor_target)}
        {row.safe_harbor_pct != null && (
          <span className="ml-[3px] text-ink-3">({row.safe_harbor_pct}%)</span>
        )}
      </td>
      <td data-col="paid" className="tabular-nums">
        {row.payments.length === 0
          ? "—"
          : row.payments.map((p) => `${p.jurisdiction} ${figure(p.amount)}`).join(" · ")}
      </td>
      <td>
        {row.confirmation?.confirmed === true ? `✓ ${row.confirmation.contact_name ?? ""}` : "—"}
      </td>
      <td>
        <span
          className={cn(urgent && "font-medium text-red-ink")}
          data-due={urgent ? "urgent" : "ok"}
        >
          {date(row.extended_due_on, { now, withYear: true })}
          {urgent &&
            row.days_to_extended_due != null &&
            ` · ${COPY.day(row.days_to_extended_due)}`}
        </span>
        {row.likely_to_extend && (
          <span className="ml-[6px] inline-flex items-center gap-[6px]">
            <Pill size="chip" variant="amber">
              {COPY.likelyTag}
            </Pill>
            {blocked === null ? (
              <Button size="xs" variant="secondary" onClick={() => onPrepare?.(row)}>
                {COPY.prepare(row.lines[0]?.form ?? "")}
              </Button>
            ) : (
              <Tooltip content={blocked}>
                <span data-blocked={blocked}>
                  <Button size="xs" variant="secondary" disabled>
                    {COPY.prepare(row.lines[0]?.form ?? "")}
                  </Button>
                </span>
              </Tooltip>
            )}
          </span>
        )}
      </td>
    </tr>
  );
}

function EstimateRow({
  row,
  onResend,
}: {
  row: EstimateRowOut;
  onResend?: (row: EstimateRowOut) => void;
}): JSX.Element {
  const installment = row.installment;
  const awaiting = installment?.status === "confirmation_requested";
  return (
    <tr
      data-row={row.schedule_id}
      data-client={row.client_name}
      className="h-[40px] text-[12.5px] hairline-t"
    >
      <td className="px-[12px]">{row.client_name}</td>
      <td>{row.forms.join(" · ")}</td>
      <td>{COPY.methods[row.method]}</td>
      <td className="text-right tabular-nums">{figure(row.annual_required)}</td>
      <td className="text-right tabular-nums">{figure(installment?.amount)}</td>
      <td data-col="status">
        {installment === null || installment === undefined
          ? "—"
          : COPY.estimateStatus[installment.status]}
      </td>
      <td>
        {awaiting && (
          <Button size="xs" variant="secondary" onClick={() => onResend?.(row)}>
            {COPY.resend}
          </Button>
        )}
      </td>
    </tr>
  );
}

export interface ExtensionsProps {
  taxYear: number;
  quarter?: number;
  tab?: Tab;
  segment?: Segment;
  onBack?: () => void;
  onReturn?: (id: string) => void;
  onPrepare?: (row: ExtensionRowOut) => void;
  onResend?: (row: EstimateRowOut) => void;
  /** DF-08: Payments is a composed union, hidden until its read exists. */
  showPayments?: boolean;
}

/** Only the visible rows of this view leave, with fresh MFA and an audit row (T-03-T07). */
async function openInExcel(
  tab: Tab,
  taxYear: number,
  quarter: number,
  segment: Segment,
): Promise<void> {
  const { data } =
    tab === "estimates"
      ? await estimatesExport({
          query: { tax_year: taxYear, quarter },
          parseAs: "blob",
          throwOnError: true,
        })
      : await extensionsExport({
          query: { tax_year: taxYear, segment },
          parseAs: "blob",
          throwOnError: true,
        });
  const url = URL.createObjectURL(data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${tab}-TY${String(taxYear)}.xlsx`;
  link.click();
  URL.revokeObjectURL(url);
}

export function Extensions({
  taxYear,
  quarter = 3,
  tab: initialTab = "extensions",
  segment: initialSegment = "open",
  onBack,
  onReturn,
  onPrepare,
  onResend,
  showPayments = false,
}: ExtensionsProps): JSX.Element {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [segment, setSegment] = useState<Segment>(initialSegment);
  const [tile, setTile] = useState<Tile | null>(null);
  const [q, setQ] = useState("");
  const extensions = useQuery({
    ...extensionsOptions({
      query: {
        tax_year: taxYear,
        segment,
        ...(tile === null ? {} : { tile: tile as "extended" }),
        ...(q === "" ? {} : { q }),
      },
    }),
    enabled: tab === "extensions",
  });
  const estimates = useQuery({
    ...taxEstimatesOptions({
      query: {
        tax_year: taxYear,
        quarter,
        ...(tile === null ? {} : { tile: tile as "due" }),
        ...(q === "" ? {} : { q }),
      },
    }),
    enabled: tab === "estimates",
  });
  const page = tab === "estimates" ? estimates.data : extensions.data;
  const shown = page?.items.length ?? 0;
  const total = page?.total ?? 0;
  const tabs: Tab[] = showPayments
    ? ["extensions", "estimates", "payments"]
    : ["extensions", "estimates"];
  return (
    <div data-screen="TAX-13" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[42px] shrink-0 items-center justify-center text-[15px] font-medium">
        {onBack !== undefined && (
          <Button variant="secondary" size="sm" className="absolute left-[12px]" onClick={onBack}>
            {COPY.back}
          </Button>
        )}
        {COPY.title} <span className="ml-[6px] font-normal text-ink-2">TY{taxYear}</span>
      </div>
      <div className="flex h-[50px] shrink-0 items-center justify-center">
        <Segmented
          label={COPY.title}
          options={tabs.map((t) => COPY.tabs[t])}
          active={COPY.tabs[tab]}
          onChange={(label) => {
            const next = tabs.find((t) => COPY.tabs[t] === label);
            if (next !== undefined) {
              setTab(next);
              setTile(null);
            }
          }}
        />
      </div>
      <div className="flex h-[44px] shrink-0 items-center justify-between px-[12px]">
        {tab === "extensions" ? (
          <Segmented
            size="small"
            label={COPY.pane}
            options={SEGMENTS.map((s) => COPY.segments[s])}
            active={COPY.segments[segment]}
            onChange={(label) => {
              const next = SEGMENTS.find((s) => COPY.segments[s] === label);
              if (next !== undefined) setSegment(next);
            }}
          />
        ) : (
          <span />
        )}
        <span className="text-pane-title font-medium">
          {tab === "extensions" ? COPY.control(taxYear) : COPY.estimatesControl(taxYear, quarter)}
        </span>
        <Button
          variant="ghost"
          size="sm"
          icon="cloud-download"
          onClick={() => {
            void openInExcel(tab, taxYear, quarter, segment);
          }}
        >
          {COPY.openInExcel}
        </Button>
      </div>
      <Tiles
        tiles={tab === "extensions" ? EXTENSION_TILES : ESTIMATE_TILES}
        counts={page?.counts}
        active={tile}
        onTile={setTile}
      />
      <section className="m-[12px] mt-0 flex min-h-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e1">
        <header className="flex h-[46px] shrink-0 items-center justify-between px-[12px] hairline-b">
          <SearchField label={COPY.search} value={q} onChange={setQ} />
          <span className="text-pane-title font-medium">{COPY.pane}</span>
          <span data-tax13="showing" className="text-[12px] text-ink-3">
            {COPY.showing(shown, total)}
          </span>
        </header>
        <div className="min-h-0 flex-1 overflow-auto">
          {page === undefined ? (
            <Skeleton className="m-[12px] h-[200px]" />
          ) : shown === 0 ? (
            <EmptyState icon="list" title={COPY.empty} />
          ) : tab === "estimates" ? (
            <table className="w-full" data-tax13="estimates">
              <thead>
                <tr className="h-[30px] text-[11.5px] font-medium text-ink-2">
                  <th className="px-[12px] text-left font-medium">{COPY.columns.client}</th>
                  <th className="text-left font-medium">{COPY.columns.return}</th>
                  <th className="text-left font-medium">{COPY.columns.method}</th>
                  <th className="text-right font-medium">{COPY.columns.annual}</th>
                  <th className="text-right font-medium">{COPY.columns.q}</th>
                  <th className="text-left font-medium">{COPY.columns.status}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {estimates.data?.items.map((row) => (
                  <EstimateRow
                    key={row.schedule_id}
                    row={row}
                    {...(onResend === undefined ? {} : { onResend })}
                  />
                ))}
              </tbody>
            </table>
          ) : (
            <table className="w-full" data-tax13="extensions">
              <thead>
                <tr className="h-[30px] text-[11.5px] font-medium text-ink-2">
                  <th className="px-[12px] text-left font-medium">{COPY.columns.client}</th>
                  <th className="text-left font-medium">{COPY.columns.return}</th>
                  <th className="text-left font-medium">{COPY.columns.form}</th>
                  <th className="text-left font-medium">{COPY.columns.filed}</th>
                  <th className="text-left font-medium">{COPY.columns.ack}</th>
                  <th className="text-right font-medium">{COPY.columns.projected}</th>
                  <th className="text-right font-medium">{COPY.columns.withholding}</th>
                  <th className="text-right font-medium">{COPY.columns.target}</th>
                  <th className="text-left font-medium">{COPY.columns.paid}</th>
                  <th className="text-left font-medium">{COPY.columns.confirmation}</th>
                  <th className="text-left font-medium">{COPY.columns.due}</th>
                </tr>
              </thead>
              <tbody>
                {extensions.data?.items.map((row) => (
                  <ExtensionRow
                    key={row.work_item_id}
                    row={row}
                    {...(onReturn === undefined ? {} : { onReturn })}
                    {...(onPrepare === undefined ? {} : { onPrepare })}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
    </div>
  );
}
