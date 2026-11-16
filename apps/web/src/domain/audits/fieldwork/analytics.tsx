import type { AnalyticsLineOut } from "@abacus/api-client";
import { Amount, Pill, Spinner, cn } from "@abacus/ui";
import type { JSX } from "react";
import { FIELDWORK_COPY } from "./copy";
import { BlockCard } from "./je";

// AnalyticsTable and RunRows (A-08-T26; AUD-13, AUD-26): the flux lines the shared engine
// evaluated (A-08-T20) and the stage runs. Amounts are whole numbers without a dollar sign (AUD-13
// acceptance); an over-threshold line nobody has explained is amber. The browser compares nothing:
// `over` and `status` are the server's.

const C = FIELDWORK_COPY.analytics;
const TH = "h-[28px] bg-nested px-[8px] text-[11.5px] font-normal text-ink-2";
const TD = "h-[29px] px-[8px] text-cell";

const TONE: Record<string, "amber" | "green-tint" | "muted" | "neutral"> = {
  unexplained: "amber",
  explained: "neutral",
  accepted: "green-tint",
  within: "muted",
};

export function AnalyticsTable({
  title,
  lines,
  onLine,
}: {
  title: string;
  lines: readonly AnalyticsLineOut[];
  onLine?: (key: string) => void;
}): JSX.Element {
  return (
    <BlockCard title={title}>
      <table className="w-full border-collapse" data-fieldwork="analytics">
        <caption className="sr-only">{title}</caption>
        <thead>
          <tr className="hairline-b">
            {C.columns.map((h, i) => (
              <th
                key={h}
                scope="col"
                className={cn(TH, i === 0 || i === 5 ? "text-left" : "text-right")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {lines.map((l) => {
            const unexplained = l.over && l.status === "unexplained";
            return (
              <tr
                key={l.fs_line_key}
                data-line={l.fs_line_key}
                data-over={l.over ? "" : undefined}
                className={cn("hairline-b", unexplained && "bg-amber-tint")}
              >
                <th scope="row" className={cn(TD, "text-left font-normal")}>
                  <button
                    type="button"
                    className="text-left"
                    onClick={() => onLine?.(l.fs_line_key)}
                  >
                    {l.caption}
                  </button>
                </th>
                <td className={cn(TD, "text-right")}>
                  <Amount value={l.cy} style="whole" />
                </td>
                <td className={cn(TD, "text-right")}>
                  <Amount value={l.py} style="whole" />
                </td>
                <td className={cn(TD, "text-right")}>
                  <Amount value={l.change} style="whole" />
                </td>
                <td className={cn(TD, "text-right tabular-nums")}>{`${l.change_pct}%`}</td>
                <td className={TD}>
                  {l.status !== null && (
                    <Pill variant={TONE[l.status] ?? "muted"}>
                      {C.status[l.status] ?? l.status}
                    </Pill>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </BlockCard>
  );
}

export interface RunRow {
  id: string;
  label: string;
  meta: string;
  state: "done" | "running" | "failed";
}

export function RunRows({ rows }: { rows: readonly RunRow[] }): JSX.Element {
  return (
    <BlockCard title={FIELDWORK_COPY.runs.title}>
      <ul data-fieldwork="runs">
        {rows.map((r) => (
          <li
            key={r.id}
            data-run={r.state}
            className="flex h-[33px] items-center gap-[10px] px-[14px] text-cell hairline-b"
          >
            {r.state === "running" ? <Spinner label={r.label} /> : null}
            <span className="flex-1">{r.label}</span>
            <span
              className={cn("text-[11.5px]", r.state === "failed" ? "text-red-ink" : "text-ink-3")}
            >
              {r.meta}
            </span>
          </li>
        ))}
      </ul>
    </BlockCard>
  );
}
