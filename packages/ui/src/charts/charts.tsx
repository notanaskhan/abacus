import { type JSX, type ReactNode, useState } from "react";
import { devAssert } from "../dev";
import { ErrorRow } from "../components/states";
import { ChartTooltip } from "./tooltip";
import {
  DIM,
  fillAt,
  linear,
  MAX_SLICES,
  niceMax,
  shown,
  strokeAt,
  summary,
  figure,
} from "./scale";
import type {
  BarProps,
  BoxPlotProps,
  ChartDatum,
  DonutProps,
  LineProps,
  SparklineProps,
  StackedProps,
} from "./types";

// ChartKit C-36 marks (F-08-T10; F-08 §3 D1): hand-rolled SVG on plain-math scales (DEC-16: no
// Recharts, Chart.js, ECharts or d3). Fills are --p1…--p4 with --d1…--d4 strokes (DF-38): no
// purple, gradients, 3D, radar or rainbow, and no peer benchmarks (D6). Every SVG is role="img"
// with a generated summary that ends in the comparison basis; each mark carries `data-value`, the
// number "View as table" shows. Holding a mark keeps it and dims the others to 45%.

export const DONUT_REFUSAL = (n: number): string =>
  `A donut takes at most ${String(MAX_SLICES)} slices, not ${String(n)}: use a Bar.`;

const AXIS = "var(--color-hair)";

function Svg({
  label,
  width,
  height,
  parts,
  basis,
  children,
}: {
  label: string;
  width: number;
  height: number;
  parts: readonly string[];
  basis: string;
  children: ReactNode;
}): JSX.Element {
  return (
    <svg
      role="img"
      aria-label={summary(label, parts, basis)}
      width={width}
      height={height}
      viewBox={`0 0 ${String(width)} ${String(height)}`}
      data-chart=""
    >
      {children}
    </svg>
  );
}

function useHeld(): [string | null, (key: string | null) => void, (key: string) => number] {
  const [held, setHeld] = useState<string | null>(null);
  return [held, setHeld, (key) => (held === null || held === key ? 1 : DIM)];
}

type Pt = [number, number];

function arc(cx: number, cy: number, r: number, a0: number, a1: number): [Pt, Pt] {
  const at = (a: number): Pt => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
  return [at(a0), at(a1)];
}

/** One ring segment from angle a0 to a1 (radians, clockwise from 12 o'clock). */
function segment(c: number, outer: number, inner: number, a0: number, a1: number): string {
  const large = a1 - a0 > Math.PI ? 1 : 0;
  const [[ox0, oy0], [ox1, oy1]] = arc(c, c, outer, a0, a1);
  const [[ix0, iy0], [ix1, iy1]] = arc(c, c, inner, a0, a1);
  return [
    `M ${String(ox0)} ${String(oy0)}`,
    `A ${String(outer)} ${String(outer)} 0 ${String(large)} 1 ${String(ox1)} ${String(oy1)}`,
    `L ${String(ix1)} ${String(iy1)}`,
    `A ${String(inner)} ${String(inner)} 0 ${String(large)} 0 ${String(ix0)} ${String(iy0)}`,
    "Z",
  ].join(" ");
}

export function Donut({
  label,
  comparisonBasis,
  data,
  center,
  size = 132,
  onIntent,
}: DonutProps): JSX.Element {
  devAssert(data.length <= MAX_SLICES, DONUT_REFUSAL(data.length));
  const [held, setHeld, opacity] = useHeld();
  if (data.length > MAX_SLICES) {
    return <ErrorRow title={DONUT_REFUSAL(data.length)} />;
  }
  const total = data.reduce((sum, d) => sum + Math.max(d.value, 0), 0); // geometry only
  const c = size / 2;
  const outer = c - 2;
  const inner = outer - 18;
  let angle = 0;
  const paths = data.map((d, i) => {
    const sweep = total === 0 ? 0 : (Math.max(d.value, 0) / total) * 2 * Math.PI;
    const a0 = angle;
    angle += sweep;
    // A full ring cannot be one arc: stop a hair short.
    const a1 = sweep >= 2 * Math.PI ? a0 + sweep - 0.0001 : angle;
    return { d, i, path: segment(c, outer, inner, a0, a1) };
  });
  const heldDatum = data.find((d) => d.key === held);
  return (
    <div className="relative inline-flex" data-donut="">
      <Svg
        label={label}
        width={size}
        height={size}
        parts={data.map((d) => `${d.label} ${shown(d)}`)}
        basis={comparisonBasis}
      >
        {paths.map(({ d, i, path }) => (
          <path
            key={d.key}
            d={path}
            fill={fillAt(i)}
            stroke={strokeAt(i)}
            strokeWidth={0.5}
            opacity={opacity(d.key)}
            data-key={d.key}
            data-value={d.value}
            onMouseEnter={() => {
              setHeld(d.key);
            }}
            onMouseLeave={() => {
              setHeld(null);
            }}
          />
        ))}
        {center !== undefined && (
          <text
            x={c}
            y={c}
            textAnchor="middle"
            dominantBaseline="central"
            className="fill-ink text-kpi font-medium"
          >
            {center}
          </text>
        )}
      </Svg>
      {heldDatum !== undefined && (
        <ChartTooltip datum={heldDatum} {...(onIntent === undefined ? {} : { onIntent })} />
      )}
    </div>
  );
}

const PAD = { top: 8, right: 8, bottom: 20, left: 8 };

export function Bar({
  label,
  comparisonBasis,
  data,
  width = 320,
  height = 160,
  onIntent,
}: BarProps): JSX.Element {
  const [held, setHeld, opacity] = useHeld();
  const max = niceMax(Math.max(0, ...data.map((d) => d.value)));
  const y = linear(0, max, height - PAD.bottom, PAD.top);
  const band = (width - PAD.left - PAD.right) / Math.max(data.length, 1);
  const heldDatum: ChartDatum | undefined = data.find((d) => d.key === held);
  return (
    <div className="relative inline-flex" data-bar="">
      <Svg
        label={label}
        width={width}
        height={height}
        parts={data.map((d) => `${d.label} ${shown(d)}`)}
        basis={comparisonBasis}
      >
        <line
          x1={PAD.left}
          x2={width - PAD.right}
          y1={y(0)}
          y2={y(0)}
          stroke={AXIS}
          strokeWidth={0.5}
        />
        {data.map((d, i) => {
          const x = PAD.left + i * band + band * 0.2;
          return (
            <g key={d.key}>
              <rect
                x={x}
                y={y(d.value)}
                width={band * 0.6}
                height={Math.max(y(0) - y(d.value), 0)}
                fill={fillAt(0)}
                stroke={strokeAt(0)}
                strokeWidth={0.5}
                opacity={opacity(d.key)}
                data-key={d.key}
                data-value={d.value}
                onMouseEnter={() => {
                  setHeld(d.key);
                }}
                onMouseLeave={() => {
                  setHeld(null);
                }}
              />
              <text
                x={x + band * 0.3}
                y={height - 6}
                textAnchor="middle"
                className="fill-ink-3 text-micro"
              >
                {d.label}
              </text>
            </g>
          );
        })}
      </Svg>
      {heldDatum !== undefined && (
        <ChartTooltip datum={heldDatum} {...(onIntent === undefined ? {} : { onIntent })} />
      )}
    </div>
  );
}

export function Stacked({
  label,
  comparisonBasis,
  categories,
  series,
  width = 320,
  height = 160,
}: StackedProps): JSX.Element {
  devAssert(
    series.length <= MAX_SLICES,
    `A stacked bar takes at most ${String(MAX_SLICES)} series`,
  );
  const [, setHeld, opacity] = useHeld();
  const sums = categories.map((_, ci) => series.reduce((s, x) => s + (x.values[ci] ?? 0), 0));
  const y = linear(0, niceMax(Math.max(0, ...sums)), height - PAD.bottom, PAD.top);
  const band = (width - PAD.left - PAD.right) / Math.max(categories.length, 1);
  return (
    <Svg
      label={label}
      width={width}
      height={height}
      parts={categories.map(
        (c, ci) =>
          `${c} ${series.map((s) => `${s.label} ${figure(s.values[ci] ?? 0)}`).join(" · ")}`,
      )}
      basis={comparisonBasis}
    >
      {categories.map((c, ci) => {
        let base = 0;
        const x = PAD.left + ci * band + band * 0.2;
        return (
          <g key={c}>
            {series.map((s, si) => {
              const v = s.values[ci] ?? 0;
              const top = y(base + v);
              const bottom = y(base);
              base += v;
              return (
                <rect
                  key={s.key}
                  x={x}
                  y={top}
                  width={band * 0.6}
                  height={Math.max(bottom - top, 0)}
                  fill={fillAt(si)}
                  stroke={strokeAt(si)}
                  strokeWidth={0.5}
                  opacity={opacity(s.key)}
                  data-key={`${c}:${s.key}`}
                  data-value={v}
                  onMouseEnter={() => {
                    setHeld(s.key);
                  }}
                  onMouseLeave={() => {
                    setHeld(null);
                  }}
                />
              );
            })}
            <text
              x={x + band * 0.3}
              y={height - 6}
              textAnchor="middle"
              className="fill-ink-3 text-micro"
            >
              {c}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

export function Line({
  label,
  comparisonBasis,
  categories,
  series,
  width = 320,
  height = 160,
}: LineProps): JSX.Element {
  const [, setHeld, opacity] = useHeld();
  const all = series.flatMap((s) => s.values);
  const y = linear(0, niceMax(Math.max(0, ...all)), height - PAD.bottom, PAD.top);
  const x = linear(0, Math.max(categories.length - 1, 1), PAD.left + 4, width - PAD.right - 4);
  return (
    <Svg
      label={label}
      width={width}
      height={height}
      parts={series.map((s) => `${s.label} ${s.values.map(figure).join(" to ")}`)}
      basis={comparisonBasis}
    >
      <line
        x1={PAD.left}
        x2={width - PAD.right}
        y1={y(0)}
        y2={y(0)}
        stroke={AXIS}
        strokeWidth={0.5}
      />
      {series.map((s, si) => (
        <g
          key={s.key}
          opacity={opacity(s.key)}
          onMouseEnter={() => {
            setHeld(s.key);
          }}
          onMouseLeave={() => {
            setHeld(null);
          }}
        >
          <polyline
            fill="none"
            stroke={strokeAt(si)}
            strokeWidth={1.5}
            points={s.values.map((v, i) => `${String(x(i))},${String(y(v))}`).join(" ")}
          />
          {s.values.map((v, i) => (
            <circle
              key={categories[i] ?? i}
              cx={x(i)}
              cy={y(v)}
              r={2}
              fill={strokeAt(si)}
              data-key={`${categories[i] ?? String(i)}:${s.key}`}
              data-value={v}
            />
          ))}
        </g>
      ))}
      {categories.map((c, i) => (
        <text
          key={c}
          x={x(i)}
          y={height - 6}
          textAnchor="middle"
          className="fill-ink-3 text-micro"
        >
          {c}
        </text>
      ))}
    </Svg>
  );
}

export function BoxPlot({
  label,
  comparisonBasis,
  data,
  width = 320,
  height = 160,
}: BoxPlotProps): JSX.Element {
  const [, setHeld, opacity] = useHeld();
  const y = linear(
    0,
    niceMax(Math.max(0, ...data.map((d) => d.max))),
    height - PAD.bottom,
    PAD.top,
  );
  const band = (width - PAD.left - PAD.right) / Math.max(data.length, 1);
  return (
    <Svg
      label={label}
      width={width}
      height={height}
      parts={data.map(
        (d) =>
          `${d.label} median ${figure(d.median)} (${figure(d.q1)} to ${figure(d.q3)}; ${figure(d.min)} to ${figure(d.max)})`,
      )}
      basis={comparisonBasis}
    >
      {data.map((d, i) => {
        const mid = PAD.left + i * band + band / 2;
        const half = band * 0.25;
        return (
          <g
            key={d.key}
            data-key={d.key}
            data-value={d.median}
            opacity={opacity(d.key)}
            onMouseEnter={() => {
              setHeld(d.key);
            }}
            onMouseLeave={() => {
              setHeld(null);
            }}
          >
            <line
              x1={mid}
              x2={mid}
              y1={y(d.min)}
              y2={y(d.max)}
              stroke={strokeAt(0)}
              strokeWidth={1}
            />
            <rect
              x={mid - half}
              y={y(d.q3)}
              width={half * 2}
              height={Math.max(y(d.q1) - y(d.q3), 0)}
              fill={fillAt(0)}
              stroke={strokeAt(0)}
              strokeWidth={0.5}
            />
            <line
              x1={mid - half}
              x2={mid + half}
              y1={y(d.median)}
              y2={y(d.median)}
              stroke={strokeAt(0)}
              strokeWidth={1.5}
            />
            <text x={mid} y={height - 6} textAnchor="middle" className="fill-ink-3 text-micro">
              {d.label}
            </text>
          </g>
        );
      })}
    </Svg>
  );
}

export function Sparkline({
  label,
  comparisonBasis,
  values,
  width = 64,
  height = 20,
}: SparklineProps): JSX.Element {
  const y = linear(Math.min(...values, 0), Math.max(...values, 1), height - 2, 2);
  const x = linear(0, Math.max(values.length - 1, 1), 1, width - 1);
  return (
    <Svg
      label={label}
      width={width}
      height={height}
      parts={[values.map(figure).join(", ")]}
      basis={comparisonBasis}
    >
      <polyline
        fill="none"
        stroke={strokeAt(0)}
        strokeWidth={1.25}
        points={values.map((v, i) => `${String(x(i))},${String(y(v))}`).join(" ")}
      />
    </Svg>
  );
}
