import { type JSX, useState } from "react";
import { type WorkbookCell, WorkbookGrid } from "../data/workbook-grid";
import { Sheet } from "./frame";

// WorkbookGrid (T-05-T12): TXP-11 A verbatim, Ridgeline's sheet 05 Capital with H12 selected from
// the M-2 issue, H8:H12, J13 and J15 cited, and the open-issue dot on its tab.

const SHEETS = [
  { title: "01 Trial Balance" },
  { title: "05 Capital", openIssue: true },
  { title: "06 Schedule K" },
  { title: "07 M-2" },
];

const CELLS: Readonly<Record<string, WorkbookCell>> = {
  B8: { display: "Ridgeline GP LLC", align: "left" },
  B9: { display: "Meera Shah", align: "left" },
  B10: { display: "Pell Street Ventures LLC", align: "left" },
  B11: { display: "Pell Street II LLC", align: "left" },
  B12: { display: "Jonah Feld", align: "left" },
  D12: { display: "1,500,000", comment: "2024 K-1 Item L" },
  E12: { display: "250,000" },
  F12: { display: "312,500" },
  H12: { display: "", expected: "='06 Schedule K'!C31 × 25% → 1,550" },
  I12: { display: "(150,000)" },
  J12: { display: "1,912,500", formula: "=SUM(D12:I12)" },
  J13: { display: "6,860,000", formula: "=SUM(J8:J12)" },
  J15: { display: "6,866,200" },
};

export function WorkbookGridSpecimen(): JSX.Element {
  const [selected, setSelected] = useState("H12");
  return (
    <Sheet title="WorkbookGrid" meta="name box · formula bar · sheet tabs · Sheet!Cell footer">
      <WorkbookGrid
        label="Ridgeline workbook"
        sheet="05 Capital"
        sheets={SHEETS}
        columns={10}
        rows={16}
        cells={CELLS}
        cited={["H8:H12", "J13", "J15"]}
        selected={selected}
        onSelect={setSelected}
        footerMeta="Cited by 1 issue · Evidence: 06 Schedule K!C31"
        widths={{ 1: 180 }}
      />
    </Sheet>
  );
}
