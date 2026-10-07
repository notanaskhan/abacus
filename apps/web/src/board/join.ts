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

/** How the evidence came in, as SPEC-000 words it ("Retrieved", "Uploaded"). */
export function sourceLabel(evidence: EvidenceVersionOut): string {
  return evidence.method === "retrieved" ? "Retrieved" : "Uploaded";
}

const STATUS_LABELS: Record<RequestItemOut["status"], string> = {
  open: "Open",
  received: "Received",
  ready_for_review: "Ready for review",
  needs_revision: "Needs revision",
};

export function statusLabel(status: RequestItemOut["status"]): string {
  return STATUS_LABELS[status];
}

export function confidencePercent(confidence: string): string {
  const value = Number(confidence);
  return Number.isFinite(value) ? `${String(Math.round(value * 100))}%` : "—";
}
