// TASK-102: "Waiting on you": the person's to-dos from several modules, joined here (the
// frontend joins; no cross-module endpoint). Pure, so it's tested without a server.

export interface FieldworkWaiting {
  engagement_id: string;
  procedure_id: string;
  definition: string;
  kind: "approve_sample" | "prepare_rows" | "review_rows" | "respond_notes" | "clear_notes";
  count: number;
}

export interface EngagementCount {
  engagement_id: string;
  count: number;
}

export interface EngagementName {
  id: string;
  name: string;
  client_name: string;
}

export type Destination = "fieldwork" | "review" | "requests";

export interface QueueRow {
  key: string;
  engagementId: string;
  engagement: string;
  client: string;
  what: string;
  action: string;
  to: Destination;
  /** Lower comes first: approvals unblock others, then reviews, then the rest. */
  rank: number;
  count: number;
}

const PROCEDURE: Record<string, string> = {
  journal_entry_testing: "journal entry testing",
  unrecorded_liabilities: "the search for unrecorded liabilities",
};

function plural(n: number, one: string, many: string): string {
  return `${String(n)} ${n === 1 ? one : many}`;
}

export function queueRows(
  fieldwork: FieldworkWaiting[],
  review: EngagementCount[],
  overdue: EngagementCount[],
  engagements: EngagementName[],
): QueueRow[] {
  const byId = new Map(engagements.map((e) => [e.id, e]));
  const rows: QueueRow[] = [];
  const base = (id: string): Pick<QueueRow, "engagementId" | "engagement" | "client"> => {
    const e = byId.get(id);
    return {
      engagementId: id,
      engagement: e?.name ?? "An engagement",
      client: e?.client_name ?? "",
    };
  };
  for (const w of fieldwork) {
    const procedure = PROCEDURE[w.definition] ?? "a procedure";
    const common = { ...base(w.engagement_id), to: "fieldwork" as const, count: w.count };
    if (w.kind === "approve_sample") {
      rows.push({
        ...common,
        key: `${w.procedure_id}-approve`,
        what: `Approve the sample for ${procedure} (${plural(w.count, "item", "items")})`,
        action: "Approve",
        rank: 0,
      });
    } else if (w.kind === "respond_notes") {
      rows.push({
        ...common,
        key: `${w.procedure_id}-respond`,
        what: `Respond to ${plural(w.count, "review note", "review notes")} on ${procedure}`,
        action: "Respond",
        rank: 1,
      });
    } else if (w.kind === "clear_notes") {
      rows.push({
        ...common,
        key: `${w.procedure_id}-clear`,
        what: `Clear ${plural(w.count, "answered review note", "answered review notes")} on ${procedure}`,
        action: "Clear",
        rank: 1,
      });
    } else if (w.kind === "review_rows") {
      rows.push({
        ...common,
        key: `${w.procedure_id}-review`,
        what: `Review ${plural(w.count, "row", "rows")} of ${procedure}`,
        action: "Review",
        rank: 1,
      });
    } else {
      rows.push({
        ...common,
        key: `${w.procedure_id}-prepare`,
        what: `Sign ${plural(w.count, "tested row", "tested rows")} of ${procedure} as preparer`,
        action: "Sign off",
        rank: 2,
      });
    }
  }
  for (const r of review) {
    rows.push({
      ...base(r.engagement_id),
      key: `${r.engagement_id}-review`,
      what: `Decide ${plural(r.count, "piece of evidence", "pieces of evidence")}`,
      action: "Decide",
      to: "review",
      rank: 1,
      count: r.count,
    });
  }
  for (const o of overdue) {
    rows.push({
      ...base(o.engagement_id),
      key: `${o.engagement_id}-overdue`,
      what: `${plural(o.count, "client item is", "client items are")} past due`,
      action: "Follow up",
      to: "requests",
      rank: 3,
      count: o.count,
    });
  }
  return rows.sort((a, b) => a.rank - b.rank || b.count - a.count);
}
