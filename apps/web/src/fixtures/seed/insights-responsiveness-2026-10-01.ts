// F-08-T03 (DEC-5618): Insights › Client responsiveness at Thu Oct 1, 2026, 9:30 AM CT (TPL-23a,
// addendum §9.7.4). Every figure is the TPL-23 handoff's; rates and sums are tests
// (insights-addin.foot.test.ts), never constants on screen. No peer benchmark (D6).
import type { ResponsivenessDraft } from "../contracts/insights";

export const RESPONSIVENESS = {
  asOf: "2026-10-01T09:00:00-05:00",
  due: { onTime: 2804, late: 1432, pastDue: 214 },
  openNotDue: 362,
  pastDueByAge: [
    { label: "1–7 days", count: 78 },
    { label: "8–14 days", count: 46 },
    { label: "15–30 days", count: 44 },
    { label: "31–60 days", count: 34 },
    { label: "Over 60 days", count: 12 },
  ],
  quarters: [
    { label: "Q1", due: 1610, onTime: 1020 },
    { label: "Q2", due: 1720, onTime: 1101 },
    { label: "Q3", due: 1120, onTime: 683 },
  ],
  lowest: [
    {
      client: "Fenwick Family Foundation",
      serviceLine: "Tax · Audit & assurance",
      requests: 9,
      pastDue: 6,
      onTimePct: 22,
      firstResponseDays: 11.5,
      lastActivity: "2026-08-11",
    },
    {
      client: "Estate of Walter Thornbury",
      serviceLine: "Tax",
      requests: 13,
      pastDue: 3,
      onTimePct: 31,
      firstResponseDays: 7.0,
      lastActivity: "2026-09-29",
    },
    {
      client: "Gloria Mendez",
      serviceLine: "Tax",
      requests: 11,
      pastDue: 7,
      onTimePct: 36,
      firstResponseDays: 6.5,
      lastActivity: "2026-09-18",
    },
    {
      client: "Granite Peak Outdoor Supply, Inc.",
      serviceLine: "Audit & assurance",
      requests: 65,
      pastDue: 3,
      onTimePct: 48,
      firstResponseDays: 4.0,
      lastActivity: "2026-09-30",
    },
    {
      client: "Northwind Robotics",
      serviceLine: "Audit & assurance",
      requests: 28,
      pastDue: 2,
      onTimePct: 57,
      firstResponseDays: 3.5,
      lastActivity: "2026-09-30",
    },
  ],
} satisfies ResponsivenessDraft;
