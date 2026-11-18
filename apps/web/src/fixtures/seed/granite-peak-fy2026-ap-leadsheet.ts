// F-08-T03 (DEC-5618): the Granite Peak AP leadsheet in Excel (TPL-24a, Wed Sep 30, 2026, 2:15 PM
// CT) and the Word host's incoming changes (TPL-24f, Mon Oct 26, 2026, 4:15 PM). Every figure is
// the TPL-24 handoff's; the footings are tests (insights-addin.foot.test.ts).
import type { AddinDraft } from "../contracts/addin";

export const AP_LEADSHEET = {
  workbook: "AP leadsheet.xlsx",
  rows: [
    {
      row: 12,
      account: "2010",
      label: "Trade payables",
      prior: 3128600,
      current: 3962400,
      ref: "AP-1",
    },
    {
      row: 13,
      account: "2040",
      label: "Freight and duties payable",
      prior: 181400,
      current: 217600,
      ref: "AP-2",
    },
  ],
  totalRow: 14,
  links: [{ cell: "D14", evidence: "AP aging 6/30/2026.xlsx", page: 1 }],
  tickmarks: [
    { mark: "✓", count: 2 },
    { mark: "⊕", count: 1 },
    { mark: "∧", count: 0 },
    { mark: "◊", count: 3 },
    { mark: "¢", count: 0 },
  ],
  wordIncoming: [
    { label: "Long-term debt, net of current portion", old: "3,200,000", new: "2,600,000" },
    { label: "Dividends paid", old: "(1,000,000)", new: "(1,100,000)" },
  ],
} satisfies AddinDraft;
