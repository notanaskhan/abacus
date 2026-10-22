// Record keys in the design handoff's links (F-04-T14; chapter 04 section 2.6, rule 4). A link
// to "AJE-06", "BH-26-0958" or "SURL-03" opens a record, not a screen: the key's prefix maps to the
// record route that shows it. Path is the route's full path with the record's `$param`, or null
// until the screen that shows the record is built (AJE-06 opens in CLS-07; the BH-26 invoices are
// listed on POR-10; SURL rows are on the unrecorded-liabilities procedure).

export interface RecordRoute {
  /** What the key names, in the handoff's words. */
  readonly record: string;
  readonly path: string | null;
}

export const RECORD_ROUTES = {
  AJE: { record: "Adjusting journal entry", path: null },
  BH: { record: "Invoice", path: null },
  SURL: { record: "Search for unrecorded liabilities item", path: null },
} as const satisfies Readonly<Record<string, RecordRoute>>;

/** "BH-26-0958" -> "BH". */
export function recordPrefix(key: string): string {
  return key.split("-")[0] ?? key;
}
