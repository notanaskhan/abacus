import type { JSX } from "react";
import {
  Bar,
  BoxPlot,
  ChartCard,
  type ChartDatum,
  ChartKpiTile,
  datumTable,
  Donut,
  Line,
  seriesTable,
  Sparkline,
  Stacked,
} from "../charts";
import { Row, Sheet } from "./frame";

// The C-36 ChartKit specimens (F-08-T10; /components/c/C-36): every mark on plain-math SVG with
// its comparison basis, the card with View as table and Download CSV, and the KPI tile. The
// figures are the F-08 §3 D1 example ("214 · 4.8% of 4,450 due") and neutral shapes; the TPL-23
// specimen draws the Brightwater Hale seed.

const AGES: ChartDatum[] = [
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
const WEEKS = ["W1", "W2", "W3", "W4", "W5"];
const SEASONS = [
  { key: "this", label: "This season", values: [140, 310, 520, 760, 980] },
  { key: "last", label: "Last season", values: [120, 260, 470, 690, 900] },
];

export function ChartKitSpecimen(): JSX.Element {
  return (
    <Sheet title="ChartKit" meta="C-36 · hand-rolled SVG · --p1…--p4">
      <Row name="Donut" meaning="At most four slices; hover holds one" spec="132 · ring 18">
        <Donut
          label="Requests by age"
          comparisonBasis={BASIS}
          data={AGES}
          center="4,450"
          onIntent={() => undefined}
        />
      </Row>
      <Row name="Bar" spec="320 × 160">
        <Bar label="Requests by age" comparisonBasis={BASIS} data={AGES} />
      </Row>
      <Row name="Stacked" spec="320 × 160 · four series at most">
        <Stacked
          label="Weekly returns by season"
          comparisonBasis="vs last season"
          categories={WEEKS}
          series={SEASONS}
        />
      </Row>
      <Row name="Line" spec="320 × 160 · --d strokes">
        <Line
          label="Returns filed"
          comparisonBasis="vs last season"
          categories={WEEKS}
          series={SEASONS}
        />
      </Row>
      <Row name="Box plot" spec="median, quartiles, range">
        <BoxPlot
          label="Days to respond"
          comparisonBasis="median by office"
          data={[
            { key: "a", label: "Office A", min: 1, q1: 3, median: 5, q3: 9, max: 20 },
            { key: "b", label: "Office B", min: 2, q1: 4, median: 7, q3: 12, max: 26 },
          ]}
        />
      </Row>
      <Row name="Sparkline" spec="64 × 20">
        <Sparkline
          label="Trend"
          comparisonBasis="vs last season"
          values={SEASONS[0]?.values ?? []}
        />
      </Row>
      <Row name="KPI tile" spec="72 · value 22 · delta in words">
        <ChartKpiTile
          label="On time"
          comparisonBasis="vs last season"
          value="63%"
          delta={{ direction: "up", words: "5 pts vs last season (58%)", improvement: true }}
        />
      </Row>
      <Row
        name="ChartCard"
        meaning="··· › View as table · Download CSV"
        spec="header 44 · footer 28"
      >
        <div className="w-[420px]">
          <ChartCard
            title="Requests by age"
            label="Requests by age"
            comparisonBasis={BASIS}
            table={datumTable("Requests", AGES)}
            csvName="requests-by-age"
          >
            <Donut label="Requests by age" comparisonBasis={BASIS} data={AGES} center="4,450" />
          </ChartCard>
        </div>
      </Row>
      <Row name="ChartCard · series" spec="the same table drives CSV">
        <div className="w-[420px]">
          <ChartCard
            title="Returns filed"
            label="Returns filed"
            comparisonBasis="vs last season"
            scope="All offices"
            table={seriesTable(WEEKS, SEASONS)}
            csvName="returns-filed"
          >
            <Line
              label="Returns filed"
              comparisonBasis="vs last season"
              categories={WEEKS}
              series={SEASONS}
            />
          </ChartCard>
        </div>
      </Row>
    </Sheet>
  );
}
