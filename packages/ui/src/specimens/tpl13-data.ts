// TPL-13's September 2026 (F-07-T12; handoff TPL-13 spec.md "CELLS (exact content)"; blueprint §9.3,
// §9.5, §9.7). Viewer Grace Holloway, clock Mon Sep 14, 2026 9:24 AM CT. Tiers are the server's,
// relative to Sep 14: overdue (Copperleaf's close, the only one), ≤ 7 days red-tint, ≤ 30 amber,
// done green with a check. Sep 15 = 8 × 1065 + 3 × 1120-S + 2 envelopes = 13; Denver = 7 items.
// The blueprint names six of the eight open 1065s and leaves "one unnamed In review and one unnamed
// Ready": those two carry TPL-13's own words for them ("open row in TAX-01"), never a made-up
// client (DEC-4730). Rule text exists only where the handoff gives it (C21 data, DEC-76).
import type {
  CalendarCopy,
  CalendarFilter,
  CalendarHoliday,
  CalendarListCopy,
  DeadlineChip,
  ExpandedDay,
} from "../templates/calendar";

export const TPL13_TODAY = "2026-09-14";
export const TPL13_MONTH = "2026-09";

export const TPL13_COPY: CalendarCopy = {
  today: "Today",
  views: "Calendar view",
  month: "Month",
  week: "Week",
  list: "List",
  export: "Export",
  previous: "Previous month",
  next: "Next month",
  more: (n) => `+${String(n)} more`,
  deadlines: (n) => `${String(n)} deadlines`,
  empty: "No deadlines match these filters.",
  clearFilters: "Clear filters",
  postponed: (d) => `Postponed → ${d}`,
};

export const TPL13_LIST_COPY: CalendarListCopy = {
  title: "Deadlines",
  noun: "deadlines",
  due: "Due",
  client: "Client",
  filing: "Filing",
  rule: "Rule",
  stage: "Stage",
  team: "Team",
  risk: "Risk",
  blockers: "Blockers",
  openReturn: "Open return →",
};

export const TPL13_HOLIDAYS: readonly CalendarHoliday[] = [
  { date: "2026-09-07", label: "Labor Day" },
];

/** The kind of item, for the Sep 15 footing (8 × 1065 + 3 × 1120-S + 2 envelopes). */
export type Tpl13Kind =
  "1065" | "1120-S" | "1041" | "envelope" | "notice" | "letter" | "close" | "1040" | "consent";

export interface Tpl13Item {
  chip: DeadlineChip;
  kind: Tpl13Kind;
  /** In the Denver office (TPL-13d's seven). */
  denver: boolean;
}

const item = (
  id: string,
  date: string,
  client: string,
  filing: string,
  tier: DeadlineChip["tier"],
  kind: Tpl13Kind,
  denver = false,
  extra: Partial<DeadlineChip> = {},
  label = `${client} · ${filing}`,
): Tpl13Item => ({ chip: { id, date, label, client, filing, tier, ...extra }, kind, denver });

const RULE_1065 =
  "15th day of the 3rd month (Mar 15, 2026 was a Sunday, so Mon Mar 16) + 6-month extension to Sep 15 via Form 7004, filed Mar 12";
const OPEN_1065 = "open row in TAX-01";

export const TPL13_ITEMS: readonly Tpl13Item[] = [
  item(
    "meridian-il",
    "2026-09-02",
    "Meridian Tool & Die",
    "IL notice response sent",
    "done",
    "notice",
  ),
  item("copperleaf-close", "2026-09-10", "Copperleaf", "August close", "overdue", "close", true, {
    note: "4 days past due",
  }),
  item("rao-1040", "2026-09-11", "Sunil & Asha Rao", "1040 filed", "done", "1040"),
  item("summit-1120s", "2026-09-12", "Summit Line Logistics", "1120-S filed", "done", "1120-S"),
  // Sep 15: three shown, "+10 more"; 13 in all.
  item("ridgeline-1065", "2026-09-15", "Ridgeline", "Form 1065", "due_7", "1065", false, {
    title: "2025 Form 1065 · Ridgeline Property Partners, LP",
    rule: RULE_1065,
    stage: "In review · Partner",
    team: "OB / SI · signer DR",
    blockers: "11 open issues",
  }),
  item("harborview-1065", "2026-09-15", "Harborview Dental", "Form 1065", "due_7", "1065"),
  item("kestrel-8879pe", "2026-09-15", "Kestrel Ventures", "8879-PE", "due_7", "envelope"),
  item("kestrel-1065", "2026-09-15", "Kestrel Ventures Fund I", "1065", "due_7", "1065"),
  item("northgate-1065", "2026-09-15", "Northgate Medical Partners", "1065", "due_7", "1065"),
  item("marlowe-1065", "2026-09-15", "Marlowe Street Holdings", "1065", "due_7", "1065"),
  item("bramble-1065", "2026-09-15", "Bramble & Finch Design", "1065", "due_7", "1065"),
  item(
    "open-1065-a",
    "2026-09-15",
    OPEN_1065,
    "1065",
    "due_7",
    "1065",
    false,
    {},
    `1065 · ${OPEN_1065}`,
  ),
  item(
    "open-1065-b",
    "2026-09-15",
    OPEN_1065,
    "1065",
    "due_7",
    "1065",
    false,
    {},
    `1065 · ${OPEN_1065}`,
  ),
  item("hollis-1120s", "2026-09-15", "Hollis Creek Veterinary", "1120-S", "due_7", "1120-S", true),
  item("pinecrest-1120s", "2026-09-15", "Pinecrest Pediatrics", "1120-S", "due_7", "1120-S", true),
  item("larkspur-1120s", "2026-09-15", "Larkspur Floral", "1120-S", "due_7", "1120-S"),
  item("larkspur-8879s", "2026-09-15", "Larkspur Floral", "8879-S", "due_7", "envelope"),
  item(
    "granite-letter",
    "2026-09-16",
    "Granite Peak",
    "Engagement letter",
    "due_7",
    "letter",
    true,
  ),
  item(
    "fairhaven-letter",
    "2026-09-18",
    "Fairhaven Foods 401(k)",
    "Engagement letter",
    "due_7",
    "letter",
  ),
  item("kowal-cp14", "2026-09-21", "Kowal", "CP14 response", "due_7", "notice"),
  item("whitley-cp2000", "2026-09-23", "Whitley", "CP2000 response", "due_30", "notice", true),
  item("ferris-7216", "2026-09-23", "Ferris", "§7216 consents", "due_30", "consent"),
  item(
    "ridgeline-letter",
    "2026-09-24",
    "Ridgeline",
    "Engagement letter (§754)",
    "due_30",
    "letter",
  ),
  item("bluestem-letter", "2026-09-25", "Bluestem", "Engagement letter", "due_30", "letter"),
  item("quintero-cp501", "2026-09-28", "Quintero", "CP501 response", "due_30", "notice", true),
  item("pryor-8879f", "2026-09-28", "Pryor Trust", "8879-F", "due_30", "envelope"),
  item("calloway-1041", "2026-09-30", "Calloway Trust", "Form 1041", "due_30", "1041"),
  item("pryor-1041", "2026-09-30", "Pryor Trust", "Form 1041", "due_30", "1041"),
  item("barlow-1041", "2026-09-30", "Estate of Eugene Barlow", "1041", "due_30", "1041"),
  item("stein-cp2000", "2026-09-30", "Harold Stein", "CP2000 response", "due_30", "notice"),
  item("santos-cp14", "2026-10-01", "Santos", "CP14 response", "due_30", "notice"),
  item("varga-8879", "2026-10-01", "Varga", "8879", "due_30", "envelope"),
  item("kowal-8879", "2026-10-01", "Thomas & Irene Kowal", "8879", "due_30", "envelope"),
  item("copperleaf-co-dor", "2026-10-03", "Copperleaf", "CO DOR notice", "due_30", "notice", true),
];

export const TPL13_CHIPS: readonly DeadlineChip[] = TPL13_ITEMS.map((i) => i.chip);

export const SEP15_EXPANDED: ExpandedDay = {
  date: "2026-09-15",
  header:
    "Sep 15 · 13 items: 11 extended returns (8 × 1065, 3 × 1120-S) and 2 signature envelopes",
};

export const TPL13_FILTERS: readonly CalendarFilter[] = [
  { key: "office", label: "Office", value: "All offices" },
  { key: "service", label: "Service", value: "All" },
  { key: "person", label: "Person", value: "Anyone" },
];

export const TPL13_DENVER_FILTERS: readonly CalendarFilter[] = [
  { key: "office", label: "Office", value: "Denver" },
  { key: "service", label: "Service", value: "All" },
  { key: "person", label: "Person", value: "Anyone" },
];

/** TPL-13f: Denver and the viewer herself; the firm admin holds no deadline. */
export const TPL13_EMPTY_FILTERS: readonly CalendarFilter[] = [
  { key: "office", label: "Office", value: "Denver" },
  { key: "service", label: "Service", value: "All" },
  { key: "person", label: "Person", value: "Grace Holloway" },
];

export const TPL13_DENVER: readonly DeadlineChip[] = TPL13_ITEMS.filter((i) => i.denver).map(
  (i) => i.chip,
);

/** TPL-13e: Calloway Trust's 1041 postponed to Nov 2 (a declared disaster area). The relief
 * notice's citation is C21 data the firm admin enters (T-08); the specimen shows the pill. */
export const TPL13_POSTPONED: readonly DeadlineChip[] = TPL13_CHIPS.map((c) =>
  c.id === "calloway-1041" ? { ...c, tier: "postponed", postponedTo: "2026-11-02" } : c,
);

/** TPL-13c: the list runs from the overdue close (Sep 10) to Oct 3. */
export const TPL13_LIST: readonly DeadlineChip[] = TPL13_CHIPS.filter(
  (c) => c.date >= "2026-09-10",
);
