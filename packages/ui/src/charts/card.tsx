import { type JSX, useState } from "react";
import { cn } from "../cn";
import { DataGrid } from "../data/data-grid";
import type { TableColumn, TableRow } from "../data/types";
import { Sparkline } from "./charts";
import { toCsv } from "./scale";
import type { ChartCardProps, ChartTableData, KpiTileProps } from "./types";

// ChartCard, ChartTable and KpiTile (F-08-T10; F-08 §3 D1, D2). The card's 44 px header holds
// the title and "···" (View as table, Download CSV, Copy link); its 28 px footer states the basis
// and, when a chip narrows it, the scope. View as table draws the same numbers through the E4
// statement grammar; Download CSV is built client-side from the same table (no request).

export const CARD_HEADER_H = 44;
export const CARD_FOOTER_H = 28;
export const KPI_TILE_H = 72;
export const CHART_MENU = {
  table: "View as table",
  chart: "View as chart",
  csv: "Download CSV",
  link: "Copy link",
};

export function ChartTable({
  label,
  table,
}: {
  label: string;
  table: ChartTableData;
}): JSX.Element {
  const columns: TableColumn[] = [
    { key: "label", header: "", type: "label" },
    ...table.columns.map((c) => ({ key: c.key, header: c.header, format: "whole" as const })),
  ];
  const rows: TableRow[] = table.rows.map((r) => ({
    id: r.key,
    label: r.label,
    cells: Object.fromEntries(
      table.columns.map((c) => {
        const v = r.values[c.key];
        return [c.key, { value: v === undefined ? null : String(v) }];
      }),
    ),
  }));
  return <DataGrid label={label} grammar="statement" columns={columns} rows={rows} />;
}

function download(name: string, csv: string): void {
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `${name}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export function ChartCard({
  title,
  label,
  comparisonBasis,
  scope,
  table,
  csvName,
  onCopyLink,
  children,
}: ChartCardProps): JSX.Element {
  const [menu, setMenu] = useState(false);
  const [asTable, setAsTable] = useState(false);
  const item = "w-full px-[10px] py-[6px] text-left text-dense text-ink hover:bg-nested";
  return (
    <section
      data-chart-card=""
      aria-label={title}
      className="flex flex-col overflow-visible rounded-pane bg-card shadow-e1"
    >
      <header
        style={{ height: CARD_HEADER_H }}
        className="relative flex items-center justify-between border-b border-hair px-[14px]"
      >
        <h3 className="text-body font-medium text-ink">{title}</h3>
        <button
          type="button"
          aria-label={`${title}: more`}
          aria-expanded={menu}
          className="h-[28px] rounded-pill px-[8px] text-ink-2 hover:bg-nested"
          onClick={() => {
            setMenu(!menu);
          }}
        >
          ···
        </button>
        {menu && (
          <div
            role="menu"
            className="absolute top-[40px] right-[10px] z-20 flex w-[180px] flex-col rounded-menu bg-card py-[4px] shadow-e2"
          >
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => {
                setAsTable(!asTable);
                setMenu(false);
              }}
            >
              {asTable ? CHART_MENU.chart : CHART_MENU.table}
            </button>
            <button
              type="button"
              role="menuitem"
              className={item}
              onClick={() => {
                download(csvName, toCsv(table));
                setMenu(false);
              }}
            >
              {CHART_MENU.csv}
            </button>
            {onCopyLink !== undefined && (
              <button
                type="button"
                role="menuitem"
                className={item}
                onClick={() => {
                  onCopyLink();
                  setMenu(false);
                }}
              >
                {CHART_MENU.link}
              </button>
            )}
          </div>
        )}
      </header>
      <div className="p-[14px]">
        {asTable ? <ChartTable label={label} table={table} /> : children}
      </div>
      <footer
        data-chart-basis=""
        style={{ height: CARD_FOOTER_H }}
        className="flex items-center border-t border-hair px-[14px] text-meta text-ink-3"
      >
        {[comparisonBasis, ...(scope === undefined ? [] : [scope])].join(" · ")}
      </footer>
    </section>
  );
}

const GLYPH = { up: "▲", down: "▼", flat: "–" } as const;

/** The analytics KPI tile (D2): 72 px, value at 22 px, delta in words with its glyph. */
export function ChartKpiTile({
  label,
  comparisonBasis,
  value,
  delta,
  spark,
  caption,
}: KpiTileProps): JSX.Element {
  return (
    <div
      data-chart-kpi=""
      style={{ height: KPI_TILE_H }}
      className="flex flex-col justify-between rounded-pane bg-card px-[14px] py-[10px] shadow-e1"
    >
      <p className="text-kpi-label text-ink-3 uppercase">{label}</p>
      <div className="flex items-end justify-between gap-[10px]">
        <p className="text-kpi font-medium whitespace-nowrap text-ink">{value}</p>
        {spark !== undefined && (
          <Sparkline label={label} comparisonBasis={comparisonBasis} values={spark} />
        )}
      </div>
      {caption !== undefined && delta === undefined && (
        <p data-kpi-caption="" className="text-meta text-ink-2">
          {caption}
        </p>
      )}
      {delta !== undefined && (
        <p
          data-delta={delta.direction}
          className={cn("text-meta", delta.improvement === true ? "text-green-ink" : "text-ink-2")}
        >
          {`${GLYPH[delta.direction]} ${delta.words}`}
        </p>
      )}
    </div>
  );
}
