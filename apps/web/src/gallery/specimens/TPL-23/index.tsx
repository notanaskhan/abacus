// TPL-23 "Insights — Client responsiveness" (F-08-T15; TASK-8847; handoff TPL-23 a–f): the T21
// AnalyticsLayout with the season-to-date seed slice (fixtures/seed/insights-responsiveness.ts,
// footed by its test), Thu Oct 1, 2026 9:30 AM CT, viewer Margaret Okonkwo (e: Felix Andersen).
//   a default · b the donut's Past due now hovered (others dim to 45%) · c filtered to Granite Peak
//   d loading · e restricted (names locked, Draft follow-ups… hidden) · f flag off
// No peer data, no red deltas, and the dashboard sends nothing (Draft follow-ups… opens BND-04).
import {
  AnalyticsLayout,
  type AnalyticsLayoutProps,
  Bar,
  BoxPlot,
  Button,
  ChartCard,
  Donut,
  Line,
  LockedName,
  Pill,
  count,
  pct,
} from "@abacus/ui";
import type { JSX } from "react";
import {
  AGES,
  DUE,
  FIRM_TILES,
  GRANITE,
  GRANITE_PAST_DUE,
  GRANITE_TILES,
  LOWEST,
  QUARTERS,
  RESPONSE,
} from "../../../fixtures/seed/insights-responsiveness";
import type { FixtureParams } from "../../fixture-mode";

export const TPL23_STATES = ["a", "b", "c", "d", "e", "f"] as const;
type State = (typeof TPL23_STATES)[number];
const TABS = [
  "Performance",
  "Engagements",
  "Time saved",
  "AI adoption",
  "Client responsiveness",
  "Requests",
  "Time",
];
const n = (v: number): string => count(v);
const table = (rows: { key: string; label: string; value: number }[]) => ({
  columns: [{ key: "v", header: "Requests" }],
  rows: rows.map((r) => ({ key: r.key, label: r.label, values: { v: r.value } })),
});

function props(state: State): AnalyticsLayoutProps {
  const granite = state === "c";
  const prefix = granite ? `${GRANITE} · season to date · ` : "";
  const due = granite ? DUE.granite : DUE.firm;
  const donut = [
    { key: "on_time", label: "Completed on time", value: due.onTime },
    { key: "late", label: "Completed late", value: due.late },
    {
      key: "past_due",
      label: "Past due now",
      value: due.pastDue,
      share: `${pct(due.pastDue / due.due, { decimals: 1 })} of ${n(due.due)} due`,
      intent: "Open in request tracker ›",
    },
  ];
  const restricted = state === "e";
  return {
    variant: "home",
    title: "Insights",
    scope: [
      { key: "season", label: "Season to date", icon: "calendar-range", narrowed: false },
      { key: "office", label: "All offices", icon: "map-pin", narrowed: false },
      { key: "line", label: "All service lines", icon: "layers", narrowed: false },
      ...(granite ? [{ key: "client", label: `Client │ ${GRANITE}`, narrowed: true }] : []),
    ],
    tabs: TABS,
    activeTab: "Client responsiveness",
    tiles: (granite ? GRANITE_TILES : FIRM_TILES).map((t) => ({
      label: t.label,
      comparisonBasis: t.basis,
      caption: t.basis,
      value: t.value,
      ...(t.delta ? { delta: t.delta } : {}),
    })),
    view:
      state === "d" ? "loading" : state === "f" ? "flag-off" : restricted ? "restricted" : "ready",
    cards: [
      {
        key: "a",
        span: 4,
        title: "Requests due to date",
        basis: `${prefix}Basis: ${n(due.due)} requests due Jan 1 – Sep 30, 2026${granite ? "" : " · 362 open requests not yet due are excluded"}`,
        card: (
          <ChartCard
            title="Requests due to date"
            label="Requests due to date"
            comparisonBasis={`${prefix}Basis: ${n(due.due)} requests due Jan 1 – Sep 30, 2026${granite ? "" : " · 362 open requests not yet due are excluded"}`}
            table={table(donut)}
            csvName="requests-due"
          >
            <Donut
              label="Requests due to date"
              comparisonBasis="on time"
              data={donut}
              center={due.centre}
            />
          </ChartCard>
        ),
      },
      {
        key: "b",
        span: 5,
        title: "On-time rate by quarter",
        basis: `${prefix}Compared with the same quarters of last season · firm history only, no peer data`,
        card: (
          <ChartCard
            title="On-time rate by quarter"
            label="On-time rate by quarter"
            comparisonBasis={`${prefix}Compared with the same quarters of last season · firm history only, no peer data`}
            table={{
              columns: [
                { key: "y2026", header: "2026" },
                { key: "y2025", header: "2025" },
              ],
              rows: QUARTERS.categories.map((q, i) => ({
                key: q,
                label: q,
                values: { y2026: QUARTERS.y2026[i] ?? 0, y2025: QUARTERS.y2025[i] ?? 0 },
              })),
            }}
            csvName="on-time-by-quarter"
          >
            <Line
              label="On-time rate by quarter"
              comparisonBasis="vs the same quarters of last season"
              categories={QUARTERS.categories}
              series={[
                { key: "2026", label: "2026", values: QUARTERS.y2026 },
                { key: "2025", label: "2025", values: QUARTERS.y2025 },
              ]}
            />
          </ChartCard>
        ),
      },
      {
        key: "c",
        span: 3,
        title: "Days to respond to a request",
        basis: `${prefix}Median days from a message on a request to the other side's reply · season to date`,
        card: (
          <ChartCard
            title="Days to respond to a request"
            label="Days to respond to a request"
            comparisonBasis={`${prefix}Median days from a message on a request to the other side's reply · season to date`}
            table={{
              columns: [{ key: "median", header: "Median" }],
              rows: RESPONSE.map((r) => ({
                key: r.key,
                label: r.label,
                values: { median: r.median },
              })),
            }}
            csvName="days-to-respond"
          >
            <BoxPlot
              label="Days to respond to a request"
              comparisonBasis="days, season to date"
              data={RESPONSE}
            />
          </ChartCard>
        ),
      },
      {
        key: "d",
        span: 8,
        title: granite ? "Requests past due" : "Lowest on-time rates",
        basis: granite
          ? `${prefix}3 requests past due as of Oct 1, 9:00 AM`
          : "Firm on-time rate 63% · on time = completed by the due date · clients with fewer than 5 such requests are not ranked",
        card: (
          <ChartCard
            title={granite ? "Requests past due" : "Lowest on-time rates"}
            label={granite ? "Requests past due" : "Lowest on-time rates"}
            comparisonBasis={
              granite
                ? `${prefix}3 requests past due as of Oct 1, 9:00 AM`
                : "Firm on-time rate 63% · on time = completed by the due date · clients with fewer than 5 such requests are not ranked"
            }
            table={table(
              LOWEST.map((r) => ({ key: r.client, label: r.client, value: r.onTimePct })),
            )}
            csvName="lowest-on-time"
          >
            {granite ? (
              <table className="w-full text-[12.5px]">
                <thead>
                  <tr className="h-[30px] bg-nested text-left text-[11.5px] text-ink-3">
                    {["Request", "Client owner", "Due", "Days late", "Status"].map((h) => (
                      <th key={h} className="px-[8px] font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {GRANITE_PAST_DUE.map((r) => (
                    <tr key={r.request} className="h-[40px] border-t border-hair">
                      <td className="px-[8px]">{r.request}</td>
                      <td className="px-[8px]">{r.owner}</td>
                      <td className="px-[8px]">{r.due}</td>
                      <td className="px-[8px] text-right tabular-nums">{r.late}</td>
                      <td className="px-[8px]">
                        <Pill variant="red">Late</Pill>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <div className="flex flex-col">
                {restricted ? null : (
                  <div className="flex justify-end pb-[6px]">
                    <Button variant="secondary" size="sm">
                      Draft follow-ups…
                    </Button>
                  </div>
                )}
                <table className="w-full text-[12.5px]">
                  <thead>
                    <tr className="h-[30px] bg-nested text-left text-[11.5px] text-ink-3">
                      {[
                        "Client",
                        "Service line",
                        "Requests",
                        "Past due now",
                        "On-time rate",
                        "Median first response",
                        "Last client activity",
                      ].map((h) => (
                        <th key={h} className="px-[8px] font-medium">
                          {h}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {LOWEST.map((r) => (
                      <tr key={r.client} data-low-row="" className="h-[40px] border-t border-hair">
                        <td className="px-[8px]">
                          {restricted ? (
                            <LockedName name={r.client} />
                          ) : (
                            <button type="button">{r.client}</button>
                          )}
                        </td>
                        <td className="px-[8px]">{r.line}</td>
                        <td className="px-[8px] text-right tabular-nums">{r.requests}</td>
                        <td className="px-[8px] text-right">
                          <Pill variant="red">{String(r.pastDue)}</Pill>
                        </td>
                        <td className="px-[8px]">
                          <span className="inline-flex items-center gap-[6px]">
                            <span
                              aria-hidden
                              className="relative inline-block h-[6px] w-[72px] rounded-[3px] bg-nested"
                            >
                              <span
                                className="absolute inset-y-0 left-0 rounded-[3px] bg-ink-3"
                                style={{ width: `${String(r.onTimePct)}%` }}
                              />
                            </span>
                            <span className="tabular-nums">{`${String(r.onTimePct)}%`}</span>
                          </span>
                        </td>
                        <td className="px-[8px] text-right tabular-nums">{r.firstResponse}</td>
                        <td className="px-[8px] text-right">
                          {r.lastActivity}
                          {r.silent ? (
                            <span className="ml-[6px] text-[11px] text-amber-ink">{r.silent}</span>
                          ) : null}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </ChartCard>
        ),
      },
      {
        key: "e",
        span: 4,
        title: "Past due by age",
        basis: `${prefix}214 requests past due as of Oct 1, 9:00 AM · age = days since the due date`,
        card: (
          <ChartCard
            title="Past due by age"
            label="Past due by age"
            comparisonBasis={`${prefix}214 requests past due as of Oct 1, 9:00 AM · age = days since the due date`}
            table={table(AGES)}
            csvName="past-due-by-age"
          >
            <Bar label="Past due by age" comparisonBasis="days since the due date" data={AGES} />
          </ChartCard>
        ),
      },
    ],
  };
}

export function Tpl23Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: State = TPL23_STATES.find((s) => s === params.st) ?? "a";
  return (
    <div data-artboard={state} {...(state === "b" ? { "data-hover": "past_due" } : {})}>
      <div className="relative flex h-[860px] w-[1400px] flex-col bg-shell">
        <AnalyticsLayout {...props(state)} />
      </div>
    </div>
  );
}

export { props as tpl23Props };
