// F-08-T14 (TASK-8846; F-08 §D; T21 a–g): "T21a to T21g render, a narrowed chip turns amber and
// every footer names the scope, T21e is a designed flag-off state and T21f shows counts with
// names locked."
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ChartCard } from "../charts/card";
import { Donut } from "../charts/charts";
import { installDomShims } from "../test-dom";
import {
  AUDIENCES,
  AnalyticsLayout,
  type AnalyticsLayoutProps,
  HOME_SEGMENTS,
  LockedName,
} from "./analytics-layout";

installDomShims();
afterEach(cleanup);

const TABLE = {
  columns: [{ key: "v", header: "Value" }],
  rows: [{ key: "a", label: "A", values: { v: 1 } }],
};

function card(key: string, scope?: string) {
  return {
    key,
    span: 6,
    title: `Card ${key}`,
    basis: "Basis: —",
    card: (
      <ChartCard
        title={`Card ${key}`}
        label={`Card ${key}`}
        comparisonBasis="Basis: —"
        table={TABLE}
        csvName={key}
        {...(scope ? { scope } : {})}
      >
        <Donut
          label={`Card ${key}`}
          comparisonBasis="Basis: —"
          data={[{ key: "a", label: "A", value: 1 }]}
        />
      </ChartCard>
    ),
  };
}

function props(over: Partial<AnalyticsLayoutProps> = {}): AnalyticsLayoutProps {
  return {
    variant: "home",
    title: "Insights",
    scope: [
      { key: "season", label: "Season to date", icon: "calendar-range", narrowed: false },
      { key: "office", label: "All offices", icon: "map-pin", narrowed: false },
      { key: "line", label: "All service lines", icon: "layers", narrowed: false },
    ],
    tabs: ["Tab A", "Tab B", "Tab C"],
    activeTab: "Tab A",
    tiles: [1, 2, 3, 4].map((n) => ({
      label: `METRIC ${String(n)}`,
      comparisonBasis: "vs —",
      value: "—",
    })),
    cards: ["donut", "bar", "line", "table"].map((k) => card(k)),
    ...over,
  };
}

describe("AnalyticsLayout T21 (F-08-T14)", () => {
  it("a: the Home segmented with Insights on, three scope chips, four tiles, four cards", () => {
    render(<AnalyticsLayout {...props()} />);
    expect(HOME_SEGMENTS.at(-1)).toBe("Insights");
    expect(document.querySelectorAll("[data-scope]")).toHaveLength(3);
    expect(document.querySelectorAll("[data-chart-kpi]")).toHaveLength(4);
    expect(document.querySelectorAll("[data-chart-card]")).toHaveLength(4);
  });

  it("b: a narrowed chip turns amber and every footer names the scope", () => {
    const narrowed = props({
      scope: [{ key: "office", label: "Chicago", icon: "map-pin", narrowed: true }],
      cards: ["donut", "bar"].map((k) => card(k, "Chicago")),
    });
    render(<AnalyticsLayout {...narrowed} />);
    expect(document.querySelector('[data-scope="office"]')?.className).toContain("bg-amber-tint");
    for (const c of document.querySelectorAll("[data-chart-card]")) {
      expect(c.textContent).toContain("Chicago");
    }
  });

  it("c: loading pulses tiles and bodies with real headers and footers", () => {
    render(<AnalyticsLayout {...props({ view: "loading" })} />);
    expect(document.querySelectorAll("[data-tile-loading]")).toHaveLength(4);
    expect(document.querySelectorAll("[data-card-loading]")).toHaveLength(4);
    expect(screen.getAllByText("Basis: —")).toHaveLength(4);
  });

  it("e: flag off is the designed state", () => {
    render(<AnalyticsLayout {...props({ view: "flag-off" })} />);
    expect(screen.getByText("Insights is not turned on for this firm.")).toBeTruthy();
  });

  it("f: a locked name opens nothing", () => {
    render(<LockedName name="Granite Peak" />);
    const name = screen.getByText("Granite Peak");
    expect(name.closest("a,button")).toBeNull();
    expect(screen.getByRole("img", { name: "Locked" })).toBeTruthy();
  });

  it("g: the record variant carries the audience segmented", () => {
    render(
      <AnalyticsLayout
        {...props({
          variant: "record",
          audience: "Reviewer",
          recordSubbar: <span>Granite Peak FY2026</span>,
        })}
      />,
    );
    expect(screen.getByText("Granite Peak FY2026")).toBeTruthy();
    for (const a of AUDIENCES) expect(screen.getByText(a)).toBeTruthy();
  });
});
