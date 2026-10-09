import type { RequestItemOut } from "@abacus/api-client";
import type { BoardRow } from "./join";

/** The Board's filters (SPEC-022 AC-5), kept in the URL's search params. */
export interface BoardFilters {
  status?: string;
  area?: string;
  tier?: string; // A to E, or "none" for unclassified
  source?: string; // retrieved | uploaded | none
  assignee?: string; // "assigned" | "unassigned"
  q?: string;
}

export const FILTER_KEYS = ["status", "area", "tier", "source", "assignee", "q"] as const;

export function readFilters(search: Record<string, unknown>): BoardFilters {
  const filters: BoardFilters = {};
  for (const key of FILTER_KEYS) {
    const value = search[key];
    if (typeof value === "string" && value !== "") filters[key] = value;
  }
  return filters;
}

function source(row: BoardRow): string {
  return row.evidence === null ? "none" : row.evidence.method;
}

function assigned(item: RequestItemOut): string {
  return item.client_assignee_user_id === null ? "unassigned" : "assigned";
}

export function applyFilters(rows: BoardRow[], f: BoardFilters): BoardRow[] {
  const text = f.q?.toLocaleLowerCase();
  return rows.filter(
    (row) =>
      (f.status === undefined || row.item.status === f.status) &&
      (f.area === undefined || row.item.audit_area === f.area) &&
      (f.tier === undefined ||
        (f.tier === "none"
          ? row.item.retrievability_tier == null
          : row.item.retrievability_tier === f.tier)) &&
      (f.source === undefined || source(row) === f.source) &&
      (f.assignee === undefined || assigned(row.item) === f.assignee) &&
      (text === undefined || row.item.description.toLocaleLowerCase().includes(text)),
  );
}

export const TIER_MEANING: Record<string, string> = {
  A: "A standard report the connected system produces as is",
  B: "Derivable by code from retrieved ledger data",
  C: "A document attached to records in the connected system",
  D: "Held by the client, not in the connected system",
  E: "From third parties or physical records",
};
