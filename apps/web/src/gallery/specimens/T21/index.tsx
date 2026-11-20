// T21 Analytics dashboard, the template board (F-08-T14; TASK-8846; handoff T21 a–g): AnalyticsLayout
// on the handoff's placeholder content only (tabs Tab A · Tab B · Tab C; four METRIC tiles "—" and
// "vs —"; a donut, a bar, a line and a table card, each footed "Basis: —"), registered for
// /components/screens/T21?st=a…g. a default · b scope narrowed (Chicago) · c loading · d empty
// card · e flag off · f restricted (Grace Holloway; names locked) · g record variant (ENG-12).
import {
  AnalyticsLayout,
  type AnalyticsLayoutProps,
  Bar,
  ChartCard,
  Donut,
  Line,
  LockedName,
} from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import type { FixtureParams } from "../../fixture-mode";

export const T21_STATES = ["a", "b", "c", "d", "e", "f", "g"] as const;
type T21State = (typeof T21_STATES)[number];
const BASIS = "Basis: —";
const TABLE = {
  columns: [{ key: "v", header: "Value" }],
  rows: [{ key: "a", label: "—", values: { v: 0 } }],
};

function card(key: string, title: string, body: ReactNode, scope?: string) {
  return {
    key,
    span: 6,
    title,
    basis: BASIS,
    card: (
      <ChartCard
        title={title}
        label={title}
        comparisonBasis={BASIS}
        table={TABLE}
        csvName={key}
        {...(scope ? { scope } : {})}
      >
        {body}
      </ChartCard>
    ),
  };
}

function boardProps(state: T21State): AnalyticsLayoutProps {
  const scope = state === "b" ? "Chicago" : undefined;
  const empty = (
    <p className="py-[40px] text-center text-[12.5px] text-ink-3">Not enough data yet.</p>
  );
  const data = [{ key: "a", label: "—", value: 1 }];
  return {
    variant: state === "g" ? "record" : "home",
    title: "Insights",
    ...(state === "g"
      ? {
          recordSubbar: <span className="text-[15px] font-medium text-ink">Record</span>,
          audience: "Preparer" as const,
        }
      : {}),
    scope: [
      { key: "season", label: "Season to date", icon: "calendar-range", narrowed: false },
      {
        key: "office",
        label: scope ?? "All offices",
        icon: "map-pin",
        narrowed: scope !== undefined,
      },
      { key: "line", label: "All service lines", icon: "layers", narrowed: false },
    ],
    tabs: ["Tab A", "Tab B", "Tab C"],
    activeTab: "Tab A",
    tiles: [1, 2, 3, 4].map((n) => ({
      label: "METRIC",
      comparisonBasis: `vs — (${String(n)})`,
      value: "—",
    })),
    cards: [
      card(
        "donut",
        "Donut card",
        state === "d" ? (
          empty
        ) : (
          <Donut label="Donut card" comparisonBasis={BASIS} data={data} center="—" />
        ),
        scope,
      ),
      card("bar", "Bar card", <Bar label="Bar card" comparisonBasis={BASIS} data={data} />, scope),
      card(
        "line",
        "Line card",
        <Line
          label="Line card"
          comparisonBasis={BASIS}
          categories={["—"]}
          series={[{ key: "s", label: "—", values: [0] }]}
        />,
        scope,
      ),
      card(
        "table",
        "Table card",
        state === "f" ? (
          <p className="text-[12.5px]">
            <LockedName name="Engagement" /> · 3
          </p>
        ) : (
          <p className="text-[12.5px] text-ink-3">—</p>
        ),
        scope,
      ),
    ],
    view:
      state === "c"
        ? "loading"
        : state === "e"
          ? "flag-off"
          : state === "f"
            ? "restricted"
            : "ready",
  };
}

export function T21Artboard({ params }: { params: FixtureParams }): JSX.Element {
  const state: T21State = T21_STATES.find((s) => s === params.st) ?? "a";
  return (
    <div data-artboard={state}>
      <div className="relative flex h-[860px] w-[1400px] flex-col bg-shell">
        <AnalyticsLayout {...boardProps(state)} />
      </div>
    </div>
  );
}
