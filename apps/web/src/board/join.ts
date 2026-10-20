import { statusWord } from "@abacus/ui";
// The evidence board's rows: each request item with its evidence and screening (AC-18), joined
// on the item's evidence version (three reads keep module boundaries; TASK-012 Q1).
import type { EvidenceVersionOut, RequestItemOut, ScreeningResultOut } from "@abacus/api-client";

export type Screening =
  | { kind: "none" } // no evidence yet: nothing to screen
  | { kind: "pending" } // evidence is in, the agent hasn't proposed yet
  | { kind: "result"; result: ScreeningResultOut };

export interface BoardRow {
  item: RequestItemOut;
  evidence: EvidenceVersionOut | null;
  screening: Screening;
}

export function boardRows(
  items: readonly RequestItemOut[],
  versions: readonly EvidenceVersionOut[],
  results: readonly ScreeningResultOut[],
): BoardRow[] {
  const versionById = new Map(versions.map((v) => [v.id, v]));
  const resultByVersion = new Map(results.map((r) => [r.evidence_version_id, r]));
  return items.map((item) => {
    const versionId = item.evidence_version_id ?? null;
    const evidence = versionId === null ? null : (versionById.get(versionId) ?? null);
    const result = versionId === null ? undefined : resultByVersion.get(versionId);
    const screening: Screening =
      versionId === null
        ? { kind: "none" }
        : result === undefined
          ? { kind: "pending" }
          : { kind: "result", result };
    return { item, evidence, screening };
  });
}

/** Whether the board should keep polling: evidence waiting for its screening. */
export function awaitingScreening(rows: readonly BoardRow[]): boolean {
  return rows.some((row) => row.screening.kind === "pending");
}

const SYSTEMS: [string, string][] = [
  ["import_qbo_", "a QuickBooks Online export"],
  ["import_qbd_", "a QuickBooks Desktop export"],
  ["import_xero_", "a Xero export"],
  ["import_netsuite_", "a NetSuite export"],
  ["import_intacct_", "a Sage Intacct export"],
];

/** Where evidence came from, in words a person reads (TASK-097), never a source code. */
export function systemName(source: string): string {
  const known = SYSTEMS.find(([prefix]) => source.startsWith(prefix));
  if (known !== undefined) return known[1];
  return source.startsWith("import_") ? "an accounting system export" : source;
}

/** How the evidence came in, as SPEC-000 words it ("Retrieved", "Uploaded"). */
export function sourceLabel(evidence: EvidenceVersionOut): string {
  return evidence.method === "retrieved" ? "Retrieved" : "Uploaded";
}

// TASK-105: the request words live in the design system's status vocabulary.
const STATUS_LABELS: Record<RequestItemOut["status"], string> = {
  open: statusWord("request", "open").label,
  received: statusWord("request", "received").label,
  ready_for_review: statusWord("request", "ready_for_review").label,
  needs_revision: statusWord("request", "needs_revision").label,
};

export function statusLabel(status: RequestItemOut["status"]): string {
  return STATUS_LABELS[status];
}

export function confidencePercent(confidence: string): string {
  const value = Number(confidence);
  return Number.isFinite(value) ? `${String(Math.round(value * 100))}%` : "—";
}
