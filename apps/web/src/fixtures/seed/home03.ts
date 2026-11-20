// T-08-T16 (TASK-8842): HOME-03's September 2026 deadlines in fixture mode, as
// `GET /v1/filing-deadlines` answers them (HOME-03 a–f, x1–x3). Chips, rules, stages and owners are
// the handoff's words; the two Sep 15 1065s the handoff leaves unnamed are the synthetic scenario's
// (`brightwater_hale/binders.py`) (spec CELL CONTENTS and LIST MODE); risk and its words are the server's (risk
// by days left: ≤ 7 or past due red, ≤ 30 amber, later neutral, done green). Sep 15 holds 12 items.
import type {
  FilingDeadlineCalendarOut,
  FilingDeadlineDayOut,
  FilingDeadlineDetailOut,
  FilingDeadlineItemOut,
} from "@abacus/api-client";
import { stableId } from "./prng";

export type Home03Variant = "e0" | "daniel" | "emptyFilter" | "postponed";
export const TODAY = "2026-09-14";
const DANIEL = stableId("user:daniel-reyes");

type I = readonly [
  key: string,
  due: string,
  client: string,
  filing: string,
  kind: FilingDeadlineItemOut["source_kind"],
  stage: string,
  owners: string,
  rule: string | null,
  done?: boolean,
  daniel?: boolean,
];

const ITEMS: readonly I[] = [
  [
    "juniper-close",
    "2026-09-10",
    "Juniper & Oak",
    "Aug close",
    "close",
    "Closed",
    "MA",
    null,
    true,
  ],
  [
    "copperleaf-close",
    "2026-09-10",
    "Copperleaf",
    "Aug close",
    "close",
    "In progress",
    "MA",
    null,
  ],
  [
    "rao-1040",
    "2026-09-11",
    "Sunil & Asha Rao",
    "1040 filed",
    "tax_return",
    "Filed",
    "KO",
    null,
    true,
  ],
  [
    "harborview-sync",
    "2026-09-11",
    "Harborview",
    "1065 synced",
    "tax_return",
    "Synced",
    "DS",
    null,
    true,
  ],
  [
    "summit-1120s",
    "2026-09-12",
    "Summit Line Logistics",
    "1120-S filed",
    "tax_return",
    "Filed",
    "LP",
    null,
    true,
  ],
  [
    "bluebird-close",
    "2026-09-12",
    "Bluebird Bakery",
    "Aug close",
    "close",
    "In progress",
    "MA",
    null,
  ],
  [
    "ridgeline-1065",
    "2026-09-15",
    "Ridgeline Property Partners, LP",
    "Form 1065",
    "tax_return",
    "In review · Partner",
    "OB/SI",
    "15th day, 3rd month + 6 mo (7004)",
    false,
    true,
  ],
  [
    "harborview-1065",
    "2026-09-15",
    "Harborview Dental Properties, LP",
    "Form 1065 · 8879-PE to send",
    "tax_return",
    "Ready",
    "DS/TR",
    "15th day, 3rd month + 6 mo (7004)",
    false,
    true,
  ],
  [
    "marlowe-1065",
    "2026-09-15",
    "Marlowe Street Holdings",
    "Form 1065",
    "tax_return",
    "In review · Manager",
    "OB/SI",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "northgate-1065",
    "2026-09-15",
    "Northgate Medical Partners",
    "Form 1065",
    "tax_return",
    "Prepared",
    "DS/TR",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "kestrel-1065",
    "2026-09-15",
    "Kestrel Ventures Fund I",
    "Form 1065",
    "tax_return",
    "Prepared",
    "OB/SI",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "bramble-1065",
    "2026-09-15",
    "Bramble & Finch Design",
    "Form 1065",
    "tax_return",
    "Ready",
    "DS/TR",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "sept15-1065-a",
    "2026-09-15",
    "Cedar Hollow Farms, LLC",
    "Form 1065",
    "tax_return",
    "Prepared",
    "LP/OB",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "sept15-1065-b",
    "2026-09-15",
    "Vantage Point Realty, LLC",
    "Form 1065",
    "tax_return",
    "Prepared",
    "LP/OB",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "hollis-1120s",
    "2026-09-15",
    "Hollis Creek Veterinary",
    "Form 1120-S",
    "tax_return",
    "Ready",
    "LP/OB",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "pinecrest-1120s",
    "2026-09-15",
    "Pinecrest Pediatrics, PC",
    "Form 1120-S",
    "tax_return",
    "Ready",
    "LP/OB",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "larkspur-1120s",
    "2026-09-15",
    "Larkspur Floral, Inc.",
    "Form 1120-S · 8879-S",
    "tax_return",
    "Awaiting signature",
    "GT/YK",
    "15th day, 3rd month + 6 mo (7004)",
  ],
  [
    "q3-estimates",
    "2026-09-15",
    "Q3 2026 individual estimates",
    "1040-ES",
    "estimate_batch",
    "Scheduled",
    "KO",
    "15th day, 9th month",
  ],
  [
    "granite-letter",
    "2026-09-16",
    "Granite Peak",
    "engagement letter",
    "envelope",
    "Awaiting signature",
    "HL",
    null,
  ],
  [
    "fairhaven-letter",
    "2026-09-18",
    "Fairhaven Foods 401(k)",
    "engagement letter",
    "envelope",
    "Awaiting signature",
    "MO",
    null,
  ],
  [
    "kowal-cp14",
    "2026-09-21",
    "Thomas & Irene Kowal",
    "IRS CP14 · TY2024",
    "notice_response",
    "Response drafted",
    "MA",
    "Date on notice",
  ],
  [
    "whitley-cp2000",
    "2026-09-23",
    "Marcus & Dana Whitley",
    "IRS CP2000 · TY2024",
    "notice_response",
    "Analyzing",
    "KO",
    "Date on notice (30 days from Aug 24)",
    false,
    true,
  ],
  [
    "ferris-consents",
    "2026-09-23",
    "Morgan & Kai Ferris",
    "§7216 consents",
    "envelope",
    "Awaiting signature",
    "DS",
    null,
  ],
  [
    "ridgeline-costseg",
    "2026-09-24",
    "Ridgeline",
    "cost segregation letter",
    "envelope",
    "Awaiting signature",
    "OB",
    null,
    false,
    true,
  ],
  [
    "bluestem-letter",
    "2026-09-25",
    "Bluestem Analytics",
    "2026 Close letter",
    "envelope",
    "Awaiting signature",
    "MA",
    null,
  ],
  [
    "quintero-cp501",
    "2026-09-28",
    "Rafael Quintero",
    "CP501 response",
    "notice_response",
    "Analyzing",
    "KO",
    "Date on notice",
  ],
  [
    "pryor-8879f",
    "2026-09-28",
    "Pryor Irrevocable Trust",
    "8879-F",
    "envelope",
    "Awaiting signature",
    "KO",
    null,
  ],
  [
    "calloway-1041",
    "2026-09-30",
    "Calloway Family Trust",
    "Form 1041",
    "tax_return",
    "Prepared",
    "KO/SI",
    "15th day, 4th month + 5½ mo (7004)",
    false,
    true,
  ],
  [
    "pryor-1041",
    "2026-09-30",
    "Pryor Irrevocable Trust",
    "Form 1041",
    "tax_return",
    "Preparing",
    "KO/SI",
    "15th day, 4th month + 5½ mo (7004)",
  ],
  [
    "barlow-1041",
    "2026-09-30",
    "Estate of Eugene Barlow",
    "Form 1041",
    "tax_return",
    "Preparing",
    "KO/SI",
    "15th day, 4th month + 5½ mo (7004)",
  ],
  [
    "stein-cp2000",
    "2026-09-30",
    "Harold Stein",
    "CP2000 response",
    "notice_response",
    "Analyzing",
    "KO",
    "Date on notice",
  ],
  [
    "santos-cp14",
    "2026-10-01",
    "Aurelio Santos",
    "CP14 response",
    "notice_response",
    "Analyzing",
    "MA",
    "Date on notice",
  ],
  [
    "varga-8879",
    "2026-10-01",
    "Elena Varga",
    "8879",
    "envelope",
    "Awaiting signature",
    "KO",
    null,
  ],
  [
    "kowal-8879",
    "2026-10-01",
    "Thomas & Irene Kowal",
    "8879",
    "envelope",
    "Awaiting signature",
    "MA",
    null,
  ],
  [
    "copperleaf-co",
    "2026-10-03",
    "Copperleaf",
    "CO DOR notice",
    "notice_response",
    "Analyzing",
    "MA",
    "Date on notice",
  ],
  [
    "feld-1040",
    "2026-10-15",
    "Jonah & Claire Feld",
    "Form 1040",
    "tax_return",
    "In review · Manager",
    "KO/SI",
    "15th day, 4th month + 6 mo (4868)",
  ],
  [
    "northwind-5500",
    "2026-10-15",
    "Northwind Robotics 401(k) Plan",
    "Form 5500 (filed by Summit Plan Administrators; our audit report attaches)",
    "form_5500",
    "Audit: Planning · report target Oct 9",
    "MO",
    "Last day, 7th month + 2½ mo (5558)",
  ],
  [
    "thornbury-706",
    "2026-11-02",
    "Estate of Walter Thornbury",
    "Form 706",
    "tax_return",
    "Not started",
    "DR",
    "9 months after death (2/2/2026); 4768 → May 3, 2027",
  ],
  [
    "lakeshore-990",
    "2026-11-16",
    "Lakeshore Literacy Alliance",
    "2025 Form 990 (FYE Jun 30, 2026)",
    "tax_return",
    "Gathering",
    "CM",
    "15th day, 5th month after FYE 6/30 (Nov 15 is a Sunday); 8868 → May 17, 2027",
  ],
];

const ms = (iso: string): number => Date.parse(`${iso}T12:00:00Z`);
const daysLeft = (due: string): number => Math.round((ms(due) - ms(TODAY)) / 86_400_000);

function risk(due: string, done: boolean): [FilingDeadlineItemOut["risk"], string] {
  const d = daysLeft(due);
  if (done) return ["done", "Done"];
  if (d < 0) return ["overdue", `${String(-d)} days past due`];
  if (d <= 7) return ["due_7", d === 1 ? "1 day" : `${String(d)} days`];
  if (d <= 30) return ["due_30", `${String(d)} days`];
  return ["later", `${String(d)} days`];
}

function item(
  [key, due, client, filing, kind, stage, owners, rule, done = false, daniel = false]: I,
  variant: Home03Variant,
): FilingDeadlineItemOut {
  const [r, label] = risk(due, done);
  const postponed = variant === "postponed" && key === "kowal-cp14";
  return {
    filing_deadline_id: stableId(`deadline:${key}`),
    source_kind: kind,
    client_id: stableId(`client:${key.split("-")[0] ?? key}`),
    client_name: client,
    filing_label: filing,
    due_on: postponed ? "2026-09-28" : due, // x2: inside the September board
    original_due_on: due,
    postponed_from: postponed ? due : null,
    rule_text: rule,
    stage_code: done
      ? "done"
      : stage
          .toLowerCase()
          .replace(/[^a-z]+/gu, "_")
          .replace(/_$/u, "")
          .slice(0, 40) || "open",
    stage_label: stage,
    risk: r,
    days_left: daysLeft(due),
    risk_label: label,
    owners: owners.split("/").map((o) => ({
      user_id: o === "DR" || daniel ? DANIEL : stableId(`user:${o}`),
      initials: o,
    })),
    signer: key === "ridgeline-1065" ? { user_id: DANIEL, initials: "DR" } : null,
    work_item_id: stableId(`work-item:${key}`),
    href: null,
  };
}

export function calendar(
  variant: Home03Variant = "e0",
  view: FilingDeadlineCalendarOut["view"] = "month",
): FilingDeadlineCalendarOut {
  let items = ITEMS.map((i) => item(i, variant));
  if (variant === "daniel") {
    const keep = new Set([
      "ridgeline-1065",
      "harborview-1065",
      "whitley-cp2000",
      "ridgeline-costseg",
      "calloway-1041",
    ]);
    items = items.filter((_i, n) => keep.has(ITEMS[n]?.[0] ?? ""));
  }
  if (variant === "emptyFilter") items = [];
  const byDay = new Map<string, FilingDeadlineItemOut[]>();
  for (const i of items) byDay.set(i.due_on, [...(byDay.get(i.due_on) ?? []), i]);
  const days: FilingDeadlineDayOut[] = [...byDay.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([on, list]) => ({
      on,
      total: list.length,
      shown: list.slice(0, 3).map((i) => i.filing_deadline_id),
      holiday: null,
    }));
  return {
    view,
    window_from: "2026-08-30",
    window_to: view === "list" ? "2026-11-30" : "2026-10-03",
    today: TODAY,
    firm_zone: "America/Chicago",
    items:
      view === "list"
        ? items.filter(
            (i) =>
              i.risk !== "done" &&
              [
                "ridgeline-1065",
                "harborview-1065",
                "pinecrest-1120s",
                "larkspur-1120s",
                "kowal-cp14",
                "whitley-cp2000",
                "calloway-1041",
                "feld-1040",
                "northwind-5500",
                "thornbury-706",
                "lakeshore-990",
              ].some((k) => i.filing_deadline_id === stableId(`deadline:${k}`)),
          )
        : items,
    days,
    remaining: 0,
    next_cursor: null,
  };
}

export function ridgelineDetail(): FilingDeadlineDetailOut {
  const it = calendar().items.find(
    (i) => i.filing_deadline_id === stableId("deadline:ridgeline-1065"),
  );
  if (it === undefined) throw new Error("seed");
  return {
    item: {
      ...it,
      rule_text: "15th day, 3rd month + 6 months (Form 7004)",
      stage_label: "In review · Partner",
    },
    original_due_on: "2026-03-16",
    extended_due_on: "2026-09-15",
    extension_filed_on: "2026-03-12",
    postponement_notice_id: null,
    internal_target_on: null,
    reference_set_version_ids: [stableId("reference-set:due-dates:2026")],
    computed_at: "2026-09-14T06:00:00-05:00",
  };
}
