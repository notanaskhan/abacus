import type { ReactNode } from "react";

// ChartKit C-36 view model (F-08-T10; F-08 §3 D1; T21, TPL-23). Every chart and card says what it
// compares against: `comparisonBasis` is required on every prop type (R8, D6), so a chart without
// one fails type-checking. The kit draws what the consumer computed; it never totals a column
// (ADR-050). Values are plain numbers for geometry; `display` is the consumer's formatted figure.

export interface ChartBase {
  /** The chart's accessible name ("Requests outstanding by age"). */
  label: string;
  /** What the figures compare against ("vs last season", "of 4,450 due"). Required (D1). */
  comparisonBasis: string;
}

export interface ChartDatum {
  key: string;
  label: string;
  value: number;
  /** The figure as the consumer formats it ("214"); default: the whole number. */
  display?: string;
  /** The tooltip's share line ("4.8% of 4,450 due"), computed by the consumer. */
  share?: string;
  /** The tooltip's link, an intent the consumer handles ("Open in request tracker"). */
  intent?: string;
}

export interface ChartSeries {
  key: string;
  label: string;
  /** One value per category, in the chart's category order. */
  values: readonly number[];
}

export interface BoxStats {
  key: string;
  label: string;
  min: number;
  q1: number;
  median: number;
  q3: number;
  max: number;
}

/** What "View as table" and "Download CSV" draw: the same numbers as the SVG. */
export interface ChartTableData {
  columns: readonly { key: string; header: string }[];
  rows: readonly { key: string; label: string; values: Readonly<Record<string, number>> }[];
}

export interface DonutProps extends ChartBase {
  /** At most four slices (DF-38: --p1…--p4); more is refused, use a Bar. */
  data: readonly ChartDatum[];
  /** The figure in the hole ("4,450"). */
  center?: string;
  size?: number;
  onIntent?: (datum: ChartDatum) => void;
}

export interface BarProps extends ChartBase {
  data: readonly ChartDatum[];
  width?: number;
  height?: number;
  onIntent?: (datum: ChartDatum) => void;
}

export interface StackedProps extends ChartBase {
  categories: readonly string[];
  /** At most four series (one fill each). */
  series: readonly ChartSeries[];
  width?: number;
  height?: number;
}

export interface LineProps extends ChartBase {
  categories: readonly string[];
  series: readonly ChartSeries[];
  width?: number;
  height?: number;
}

export interface BoxPlotProps extends ChartBase {
  data: readonly BoxStats[];
  width?: number;
  height?: number;
}

export interface SparklineProps extends ChartBase {
  values: readonly number[];
  width?: number;
  height?: number;
}

export type DeltaDirection = "up" | "down" | "flat";

export interface KpiTileProps extends ChartBase {
  value: string;
  delta?: {
    direction: DeltaDirection;
    /** "5 pts vs last season (58%)". */
    words: string;
    /** An improvement may read green-ink; nothing reads red (D2). */
    improvement?: boolean;
  };
  spark?: readonly number[];
}

export interface ChartCardProps extends ChartBase {
  title: string;
  /** The scope the footer names when a chip narrows it ("Denver office"). */
  scope?: string;
  table: ChartTableData;
  /** The CSV's file name, without extension. */
  csvName: string;
  /** "Copy link": the consumer copies its URL state. */
  onCopyLink?: () => void;
  children: ReactNode;
}
