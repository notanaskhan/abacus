import type { EstimateRowOut, ExtensionRowOut } from "@abacus/api-client";
import { estimatesExport, extensionsExport } from "@abacus/api-client";
import { extensionsOptions, taxEstimatesOptions } from "@abacus/api-client/query";
import {
  Button,
  Checkbox,
  EmptyState,
  Icon,
  Pill,
  SearchField,
  Segmented,
  Skeleton,
  StatusDisc,
  Tooltip,
  cn,
  date,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { useNow } from "../../app-core/clock";
import { hrefOf, to } from "../../routes/to";
import { COPY } from "./copy";
import { ExtendSheet } from "./ExtendSheet";
import { figure } from "./figure";
import { MarkFiledDialog } from "./MarkFiledDialog";

// TAX-13 · Extensions, estimates & payments (T-03-T11; T-03 §3 F5; the handoff spec): the T6 workbook
// grammar at `/tax-returns/extensions`. Tallies and rows are the server's (T-03-T07); a tile filters
// the rows. Cells carry no dollar sign. Likely-to-extend rows offer Prepare…, disabled with the
// server's blocked reason in the tooltip (Thornbury's 706 waits on G1 and G3). Nothing here files or
// pays: the firm files and the client pays. T-03-T16 adds the selection, the Extend sheet
// (`?ov=extend:<returnIds>`), the Mark filed dialog (`?ov=mark-filed:<extensionId>`) and the ack pills.

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

/** The line a row's Filed and Ack cells speak for: a rejection never hides behind an acceptance. */
const ATTENTION = ["rejected", "not_filed", "prepared", "filed", "accepted"] as const;
function lineInView(row: ExtensionRowOut): ExtensionRowOut["lines"][number] | undefined {
  for (const status of ATTENTION) {
    const found = row.lines.find((l) => l.status === status);
    if (found !== undefined) return found;
  }
  return row.lines[0];
}

const FILEABLE: readonly string[] = ["not_filed", "prepared", "rejected"];

/** A return can go on the sheet while it has a line not yet filed and no gate holds it. */
const extendable = (row: ExtensionRowOut): boolean =>
  row.prepare_blocked_reason == null &&
  row.lines.some((l) => l.status !== "filed" && l.status !== "accepted");

function AckCell({ line }: { line: ExtensionRowOut["lines"][number] | undefined }): JSX.Element {
  if (line === undefined || line.filed_on == null) return <>{COPY.ack.not_filed}</>;
  if (line.status === "accepted") {
    return (
      <Pill size="chip" variant="green">
        <Icon name="check" size={12} />
        {COPY.ack.accepted}
      </Pill>
    );
  }
  if (line.status === "rejected") {
    // The word and the code carry it, not the colour (T-03-T16's row).
    return (
      <span className="inline-flex flex-col items-start gap-[2px]">
        <Pill size="chip" variant="red-tint">
          {COPY.ack.rejected}
        </Pill>
        {line.reject_code != null && (
          <span data-reject-code className="text-meta text-ink-3">
            {line.reject_code}
          </span>
        )}
      </span>
    );
  }
  return (
    <Pill size="chip" variant={line.status === "filed" ? "green-tint" : "neutral"}>
      {COPY.ack[line.status]}
    </Pill>
  );
}

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
          <span className="text-[13px] font-medium tabular-nums">
            {(counts?.[tile] ?? 0) === 0 ? "—" : counts?.[tile]}
          </span>
        </button>
      ))}
    </div>
  );
}

function ExtensionRow({
  row,
  picked,
  onPick,
  showPrepare,
  onPrepare,
  onMarkFiled,
}: {
  row: ExtensionRowOut;
  picked: boolean;
  onPick: (picked: boolean) => void;
  showPrepare: boolean;
  onPrepare: (row: ExtensionRowOut) => void;
  onMarkFiled: (extensionId: string) => void;
}): JSX.Element {
  const now = useNow();
  const urgent = row.days_to_extended_due != null && row.days_to_extended_due <= URGENT_DAYS;
  const line = lineInView(row);
  const blocked = row.prepare_blocked_reason ?? null;
  return (
    <tr
      data-row={row.work_item_id}
      data-client={row.client_name}
      data-selected={picked || undefined}
      className={cn("h-[40px] text-[12.5px] hairline-t", picked && "bg-sel-bg")}
    >
      <td className="pl-[12px]">
        <Checkbox
          label={COPY.selectRow(row.client_name)}
          checked={picked}
          disabled={!extendable(row)}
          onChange={onPick}
        />
      </td>
      <td className="px-[12px]">
        <a
          href={hrefOf(to.TAX02({ returnId: row.tax_return_id }))}
          className="text-left text-ink hover:underline"
        >
          {row.client_name}
        </a>
      </td>
      <td>{row.return_form}</td>
      <td>{row.lines.map((l) => l.form).join(" + ")}</td>
      <td data-col="filed">
        {line?.filed_on == null ? COPY.notFiled : date(line.filed_on, { now })}
        {line !== undefined &&
          FILEABLE.includes(line.status) &&
          row.allowed_actions.includes("filing_extension.mark_filed") && (
            <Button
              size="xs"
              variant="link"
              className="ml-[6px]"
              onClick={() => {
                onMarkFiled(line.extension_id);
              }}
            >
              {COPY.markFiled.open}
            </Button>
          )}
      </td>
      <td data-col="ack">
        <AckCell line={line} />
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
          : row.payments
              .map((p) =>
                p.jurisdiction === "federal"
                  ? figure(p.amount)
                  : `${p.jurisdiction} ${figure(p.amount)}`,
              )
              .join(" · ")}
      </td>
      <td data-col="confirmation">
        {row.confirmation?.confirmed === true ? (
          <>
            {`✓ ${row.confirmation.contact_name ?? ""}`}
            {row.confirmation.confirmed_on != null && (
              <span className="ml-[4px] text-ink-3">
                {date(row.confirmation.confirmed_on, { now })}
              </span>
            )}
          </>
        ) : row.likely_to_extend || row.confirmation != null ? (
          <span title={COPY.notConfirmed}>
            <StatusDisc state="todo" />
          </span>
        ) : (
          "—"
        )}
      </td>
      <td>
        <span
          className={cn(urgent && "font-medium text-red-ink")}
          data-due={urgent ? "urgent" : "ok"}
        >
          {row.likely_to_extend ? (
            <span className="block text-ink-3">
              {COPY.dueFrom(date(row.original_due_on, { now, withYear: true }))}
            </span>
          ) : null}
          {row.likely_to_extend
            ? COPY.dueTo(date(row.extended_due_on, { now, withYear: true }))
            : date(row.extended_due_on, { now, withYear: true })}
          {urgent &&
            row.days_to_extended_due != null &&
            ` · ${COPY.day(row.days_to_extended_due)}`}
        </span>
        {row.likely_to_extend && (
          <span className="ml-[6px] inline-flex items-center gap-[6px]">
            <Pill size="chip" variant="amber">
              {COPY.likelyTag}
            </Pill>
            {!showPrepare ? null : blocked === null ? (
              <Button
                size="xs"
                variant="secondary"
                onClick={() => {
                  onPrepare(row);
                }}
              >
                {COPY.prepare(row.lines[0]?.form ?? "")}
              </Button>
            ) : (
              <Tooltip
                content={
                  row.client_id != null && row.engagement_id != null ? (
                    <a
                      className="underline"
                      href={hrefOf(
                        to.CLI07({ clientId: row.client_id, engagementId: row.engagement_id }),
                      )}
                    >
                      {blocked}
                    </a>
                  ) : (
                    blocked
                  )
                }
              >
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
  /** The overlay in the URL: `extend:<returnIds>` or `mark-filed:<extensionId>`. */
  ov?: string;
  /** Takes the overlay into the URL; without it the screen keeps it locally. */
  onOverlay?: (ov: string | null) => void;
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
  const url = URL.createObjectURL(data);
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
  ov,
  onOverlay,
  onResend,
  showPayments = false,
}: ExtensionsProps): JSX.Element {
  const [tab, setTab] = useState<Tab>(initialTab);
  const [segment, setSegment] = useState<Segment>(initialSegment);
  const [tile, setTile] = useState<Tile | null>(null);
  const [q, setQ] = useState("");
  const [localOverlay, setLocalOverlay] = useState<string | null>(ov ?? null);
  const overlay = onOverlay === undefined ? localOverlay : (ov ?? null);
  const showOverlay = (next: string | null): void => {
    setLocalOverlay(next);
    onOverlay?.(next);
  };
  const extendIds = overlay?.startsWith("extend:") === true ? overlay.slice(7).split(",") : [];
  const filedId = overlay?.startsWith("mark-filed:") === true ? overlay.slice(11) : null;
  const [chosen, setChosen] = useState<ReadonlySet<string>>(() => new Set(extendIds));
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
  const pickable = (extensions.data?.items ?? []).filter(extendable);
  const allPicked = pickable.length > 0 && pickable.every((r) => chosen.has(r.tax_return_id));
  const pickAll = (on: boolean): void => {
    setChosen(on ? new Set(pickable.map((r) => r.tax_return_id)) : new Set());
  };
  const tabs: Tab[] = showPayments
    ? ["extensions", "estimates", "payments"]
    : ["extensions", "estimates"];
  return (
    <div data-screen="TAX-13" data-tab={tab} className="flex min-h-0 flex-1 flex-col">
      <div className="relative flex h-[42px] shrink-0 items-center justify-center text-[15px] font-medium">
        <a
          href={hrefOf(to.TAX01())}
          className="absolute left-[12px] text-[12.5px] font-normal text-ink-2 hover:underline"
        >
          {COPY.back}
        </a>
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
        {tab === "extensions" && (
          <Button
            variant="secondary"
            size="sm"
            disabled={chosen.size === 0}
            onClick={() => {
              showOverlay(`extend:${[...chosen].join(",")}`);
            }}
          >
            {COPY.extendSelected}
          </Button>
        )}
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
                  <th className="w-[30px] pl-[12px] text-left font-medium">
                    <Checkbox
                      label={COPY.selectAll}
                      checked={allPicked ? true : chosen.size > 0 ? "mixed" : false}
                      disabled={pickable.length === 0}
                      onChange={pickAll}
                    />
                  </th>
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
                    picked={chosen.has(row.tax_return_id)}
                    onPick={(on) => {
                      setChosen((was) => {
                        const next = new Set(was);
                        if (on) next.add(row.tax_return_id);
                        else next.delete(row.tax_return_id);
                        return next;
                      });
                    }}
                    showPrepare={segment === "likely"}
                    onPrepare={(r) => {
                      showOverlay(`extend:${r.tax_return_id}`);
                    }}
                    onMarkFiled={(id) => {
                      showOverlay(`mark-filed:${id}`);
                    }}
                  />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>
      {extendIds.length > 0 && (
        <ExtendSheet
          taxYear={taxYear}
          returnIds={extendIds}
          onClose={(sent) => {
            showOverlay(null);
            if (sent) setChosen(new Set());
          }}
        />
      )}
      {filedId !== null && (
        <MarkFiledDialog
          taxYear={taxYear}
          extensionId={filedId}
          onClose={() => {
            showOverlay(null);
          }}
        />
      )}
    </div>
  );
}
