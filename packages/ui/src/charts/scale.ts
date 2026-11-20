// Plain-math scales for ChartKit (F-08-T10; DEC-16: no d3). Geometry only: these place marks on
// the page and never produce a figure a person reads (ADR-050).
import { count } from "../format";
import type { ChartDatum, ChartSeries, ChartTableData } from "./types";

/** The fills (DF-38): --p1…--p4 with their --d1…--d4 strokes. Never purple, never a gradient. */
export const FILLS = [
  "var(--color-viz-p1)",
  "var(--color-viz-p2)",
  "var(--color-viz-p3)",
  "var(--color-viz-p4)",
] as const;
export const STROKES = [
  "var(--color-viz-d1)",
  "var(--color-viz-d2)",
  "var(--color-viz-d3)",
  "var(--color-viz-d4)",
] as const;
export const MAX_SLICES = 4;
export const DIM = 0.45;

/** Map `v` from [d0, d1] onto [r0, r1]; a flat domain maps to r0. */
export function linear(d0: number, d1: number, r0: number, r1: number): (v: number) => number {
  const span = d1 - d0;
  return (v) => (span === 0 ? r0 : r0 + ((v - d0) / span) * (r1 - r0));
}

/** A round ceiling for an axis: 1, 2 or 5 times a power of ten, at least `max`. */
export function niceMax(max: number): number {
  if (max <= 0) return 1;
  const step = 10 ** Math.floor(Math.log10(max));
  for (const m of [1, 2, 5, 10]) if (m * step >= max) return m * step;
  return 10 * step;
}

export const fillAt = (i: number): string => FILLS[i % FILLS.length] ?? FILLS[0];
export const strokeAt = (i: number): string => STROKES[i % STROKES.length] ?? STROKES[0];

/** The whole-number figure, grouped ("4,450"), through format.ts. */
export const figure = (n: number): string => count(String(Math.round(n)));

export const shown = (d: ChartDatum): string => d.display ?? figure(d.value);

/** The SVG's generated summary: name, each figure, then the basis. */
export function summary(label: string, parts: readonly string[], basis: string): string {
  return `${label}: ${parts.join(", ")}. ${basis}.`;
}

export function datumTable(header: string, data: readonly ChartDatum[]): ChartTableData {
  return {
    columns: [{ key: "value", header }],
    rows: data.map((d) => ({ key: d.key, label: d.label, values: { value: d.value } })),
  };
}

export function seriesTable(
  categories: readonly string[],
  series: readonly ChartSeries[],
): ChartTableData {
  return {
    columns: series.map((s) => ({ key: s.key, header: s.label })),
    rows: categories.map((c, i) => ({
      key: c,
      label: c,
      values: Object.fromEntries(series.map((s) => [s.key, s.values[i] ?? 0])),
    })),
  };
}

const cell = (v: string): string => (/[",\n]/.test(v) ? `"${v.replace(/"/g, '""')}"` : v);

/** "Download CSV": built client-side from the same table the SVG draws. */
export function toCsv(table: ChartTableData): string {
  const head = ["", ...table.columns.map((c) => c.header)].map(cell).join(",");
  const body = table.rows.map((r) =>
    [r.label, ...table.columns.map((c) => String(r.values[c.key] ?? ""))].map(cell).join(","),
  );
  return [head, ...body].join("\n");
}
