// ac-test-author: ayushkbhatia (independent; ADR-078)
// F-08-T16 (TASK-8848; F-08 §D; T21, TPL-23): the analytics kit's acceptance, proved apart from
// its builder's tests. "Tests prove restricted mode renders no name or link (INV-3), flag-off never
// 404s, no chart renders without a basis footer, and no peer-benchmark copy exists (D6)."
import { cleanup, render, screen } from "@testing-library/react";
import { readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import { ChartCard } from "../charts/card";
import { Bar, Donut, Line } from "../charts/charts";
import { installDomShims } from "../test-dom";
import { AnalyticsLayout, LockedName } from "./analytics-layout";

installDomShims();
const HERE = dirname(fileURLToPath(import.meta.url));
afterEach(cleanup);

const TABLE = {
  columns: [{ key: "v", header: "V" }],
  rows: [{ key: "a", label: "A", values: { v: 1 } }],
};

describe("analytics kit AC (F-08-T16)", () => {
  it("restricted: a locked name is no link and no button, and carries no href (INV-3)", () => {
    const { container } = render(
      <p>
        <LockedName name="Fenwick Family Foundation" />
      </p>,
    );
    expect(
      container.querySelector("a, button, [href], [role='link'], [role='button']"),
    ).toBeNull();
    expect(screen.getByText("Fenwick Family Foundation")).toBeTruthy();
  });

  it("flag off renders the designed state in place, never a 404 or not-found copy", () => {
    const { container } = render(
      <AnalyticsLayout
        variant="home"
        title="Insights"
        scope={[]}
        tabs={["A"]}
        activeTab="A"
        tiles={[]}
        cards={[]}
        view="flag-off"
      />,
    );
    expect(screen.getByText("Insights is not turned on for this firm.")).toBeTruthy();
    expect(container.textContent).not.toMatch(/404|not found/iu);
  });

  it("every chart card has a footer stating its basis", () => {
    render(
      <>
        {[
          <Donut
            key="d"
            label="D"
            comparisonBasis="of 4,450 due"
            data={[{ key: "a", label: "A", value: 1 }]}
          />,
          <Bar
            key="b"
            label="B"
            comparisonBasis="days since due"
            data={[{ key: "a", label: "A", value: 1 }]}
          />,
          <Line
            key="l"
            label="L"
            comparisonBasis="vs last season"
            categories={["Q1"]}
            series={[{ key: "s", label: "S", values: [1] }]}
          />,
        ].map((chart, i) => (
          <ChartCard
            key={String(i)}
            title={`Card ${String(i)}`}
            label={`Card ${String(i)}`}
            comparisonBasis={`Basis ${String(i)}`}
            table={TABLE}
            csvName={`c${String(i)}`}
          >
            {chart}
          </ChartCard>
        ))}
      </>,
    );
    const cards = document.querySelectorAll("[data-chart-card]");
    expect(cards).toHaveLength(3);
    cards.forEach((card, i) => {
      const footer = card.querySelector("footer");
      expect(footer?.textContent).toContain(`Basis ${String(i)}`);
    });
  });

  it("no peer-benchmark copy anywhere in the charts or analytics kit (D6)", () => {
    const roots = [join(HERE, "../charts"), HERE];
    const peer =
      /similar firms|peer (benchmark|group|average|firms)|industry average|benchmark network/iu;
    for (const dir of roots) {
      for (const f of readdirSync(dir)) {
        if (!/\.(tsx?|ts)$/u.test(f) || f.endsWith(".test.tsx") || f.endsWith(".test.ts"))
          continue;
        expect(readFileSync(join(dir, f), "utf8")).not.toMatch(peer);
      }
    }
  });
});
