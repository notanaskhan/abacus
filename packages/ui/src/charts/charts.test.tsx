// F-08-T10 (TASK-8749; DEC-5739): every chart requires a comparisonBasis prop, donuts refuse more
// than four slices, no chart uses purple, and View as table shows the same numbers as the SVG.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  Bar,
  BoxPlot,
  ChartCard,
  ChartKpiTile,
  DONUT_REFUSAL,
  Donut,
  FILLS,
  Line,
  Sparkline,
  Stacked,
  datumTable,
  seriesTable,
  toCsv,
} from ".";
import type { ChartDatum } from ".";

afterEach(cleanup);

const DUE: ChartDatum[] = [
  { key: "lt30", label: "Under 30 days", value: 3112 },
  { key: "30-60", label: "30 to 60 days", value: 870 },
  {
    key: "60-90",
    label: "60 to 90 days",
    value: 214,
    share: "4.8% of 4,450 due",
    intent: "Open in request tracker",
  },
  { key: "gt90", label: "Over 90 days", value: 254 },
];
const BASIS = "of 4,450 due";
const FIGURES: Record<string, string> = {
  lt30: "3,112",
  "30-60": "870",
  "60-90": "214",
  gt90: "254",
};

const values = (root: ParentNode): number[] =>
  [...root.querySelectorAll("[data-value]")].map((el) => Number(el.getAttribute("data-value")));

describe("comparisonBasis is required", () => {
  it("a chart or card without it fails type-checking", () => {
    // @ts-expect-error comparisonBasis is required (D1)
    const donut = <Donut label="Requests by age" data={DUE} />;
    // @ts-expect-error comparisonBasis is required (D1)
    const bar = <Bar label="Requests by age" data={DUE} />;
    // @ts-expect-error comparisonBasis is required (D1)
    const tile = <ChartKpiTile label="On time" value="63%" />;
    const card = (
      // @ts-expect-error comparisonBasis is required (D1)
      <ChartCard title="t" label="t" table={datumTable("n", DUE)} csvName="x">
        x
      </ChartCard>
    );
    expect([donut, bar, tile, card]).toHaveLength(4);
  });

  it("every SVG is role=img with a summary ending in the basis", () => {
    render(
      <>
        <Donut label="Requests by age" comparisonBasis={BASIS} data={DUE} center="4,450" />
        <Bar label="Requests by age" comparisonBasis={BASIS} data={DUE} />
        <Stacked
          label="By office"
          comparisonBasis="vs last season"
          categories={["Denver", "Boulder"]}
          series={[
            { key: "open", label: "Open", values: [12, 8] },
            { key: "done", label: "Done", values: [30, 22] },
          ]}
        />
        <Line
          label="Weekly"
          comparisonBasis="vs last season"
          categories={["W1", "W2", "W3"]}
          series={[{ key: "this", label: "This season", values: [5, 9, 14] }]}
        />
        <BoxPlot
          label="Days to respond"
          comparisonBasis="median by office"
          data={[{ key: "d", label: "Denver", min: 1, q1: 3, median: 5, q3: 9, max: 20 }]}
        />
        <Sparkline label="Trend" comparisonBasis="vs last season" values={[1, 3, 2, 5]} />
      </>,
    );
    const imgs = screen.getAllByRole("img");
    expect(imgs).toHaveLength(6);
    for (const img of imgs) expect(img.getAttribute("aria-label")).toMatch(/\.$/);
    expect(imgs[0]?.getAttribute("aria-label")).toBe(
      "Requests by age: Under 30 days 3,112, 30 to 60 days 870, 60 to 90 days 214, Over 90 days 254. of 4,450 due.",
    );
  });
});

describe("donut", () => {
  it("refuses more than four slices with a dev error", () => {
    const five = [...DUE, { key: "x", label: "Fifth", value: 1 }];
    expect(() => render(<Donut label="t" comparisonBasis={BASIS} data={five} />)).toThrow(
      DONUT_REFUSAL(5),
    );
  });

  it("holding a slice keeps it, dims the others to 45%, and shows the 220 tooltip intent", () => {
    const onIntent = vi.fn();
    render(<Donut label="t" comparisonBasis={BASIS} data={DUE} onIntent={onIntent} />);
    const slice = document.querySelector('[data-key="60-90"]');
    if (slice === null) throw new Error("no slice");
    fireEvent.mouseEnter(slice);
    const ops = [...document.querySelectorAll("path[data-key]")].map((p) =>
      p.getAttribute("opacity"),
    );
    expect(ops).toEqual(["0.45", "0.45", "1", "0.45"]);
    const tip = screen.getByRole("tooltip");
    expect(tip.textContent).toBe(
      "60 to 90 days214 · 4.8% of 4,450 due · Open in request tracker ›",
    );
    fireEvent.click(within(tip).getByRole("button", { name: "Open in request tracker ›" }));
    expect(onIntent).toHaveBeenCalledWith(DUE[2]);
  });
});

describe("no purple", () => {
  it("fills are --p1…--p4 and strokes --d1…--d4 only", () => {
    const { container } = render(
      <>
        <Donut label="t" comparisonBasis={BASIS} data={DUE} />
        <Bar label="t" comparisonBasis={BASIS} data={DUE} />
      </>,
    );
    const html = container.innerHTML;
    expect(html).not.toMatch(/purple|violet|match|#7e4590|#dacfeb|gradient/i);
    for (const el of container.querySelectorAll("[fill]")) {
      const fill = el.getAttribute("fill") ?? "";
      if (fill === "none") continue;
      expect(fill).toMatch(/^var\(--color-viz-[pd][1-4]\)$/);
    }
    expect(FILLS).toHaveLength(4);
  });
});

describe("View as table", () => {
  it("shows the same numbers as the SVG, and CSV is built from the same table", () => {
    const table = datumTable("Requests", DUE);
    render(
      <ChartCard
        title="Requests by age"
        label="Requests by age"
        comparisonBasis={BASIS}
        table={table}
        csvName="requests"
      >
        <Donut label="Requests by age" comparisonBasis={BASIS} data={DUE} />
      </ChartCard>,
    );
    const svgNumbers = values(document);
    fireEvent.click(screen.getByRole("button", { name: "Requests by age: more" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "View as table" }));
    const grid = screen.getByRole("grid", { name: "Requests by age" });
    const shown = DUE.map((d) => within(grid).getByText(FIGURES[d.key] ?? ""));
    expect(shown).toHaveLength(svgNumbers.length);
    expect(svgNumbers).toEqual(DUE.map((d) => d.value));
    expect(toCsv(table)).toBe(
      ",Requests\nUnder 30 days,3112\n30 to 60 days,870\n60 to 90 days,214\nOver 90 days,254",
    );
    expect(document.querySelector("[data-chart-basis]")?.textContent).toBe(BASIS);
  });

  it("a series table carries every stacked value", () => {
    const series = [
      { key: "open", label: "Open", values: [12, 8] },
      { key: "done", label: "Done", values: [30, 22] },
    ];
    render(
      <Stacked
        label="t"
        comparisonBasis="vs last season"
        categories={["Denver", "Boulder"]}
        series={series}
      />,
    );
    const t = seriesTable(["Denver", "Boulder"], series);
    const fromTable = t.rows.flatMap((r) => t.columns.map((c) => r.values[c.key]));
    expect(values(document).sort()).toEqual([...fromTable].sort());
  });
});

describe("KPI tile", () => {
  it("is 72 px with the delta in words and glyph; an improvement reads green-ink, never red", () => {
    render(
      <ChartKpiTile
        label="On time"
        comparisonBasis="vs last season"
        value="63%"
        delta={{ direction: "up", words: "5 pts vs last season (58%)", improvement: true }}
      />,
    );
    const tile = document.querySelector<HTMLElement>("[data-chart-kpi]");
    expect(tile?.style.height).toBe("72px");
    const delta = document.querySelector("[data-delta]");
    expect(delta?.textContent).toBe("▲ 5 pts vs last season (58%)");
    expect(delta?.className).toContain("text-green-ink");
    expect(tile?.innerHTML).not.toMatch(/red|brick/);
  });
});
