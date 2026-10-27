// The binder export routes in fixture mode (A-01-T24; docs/contracts/engagement-export-v1.md), for
// the AUD-02 export sheet (DV-9: no artboard, so these are the sheet's frames, not artboards).
// One in-memory export per create: each status read moves it one step, Queued → Packaging… →
// Ready, as the workflow would; Undo before the build marks it Undone. `stepUp` answers the first
// create with the 403 a stale second factor gets. Figures: Northwind's 12 files and 24 requests
// (A-01 §3.6), 7 days to expiry on the seed's clock. No content is invented: the download is an
// empty ZIP's bytes.

import type { EngagementExportOut } from "@abacus/api-client";
import { type FixtureHandler, type FixtureRequest, json } from "../../app-core/fixture-mode";
import { stableId } from "../seed/prng";

const NOT_FOUND = { detail: "not_found" };
/** An empty ZIP (the end-of-central-directory record alone). */
const EMPTY_ZIP = new Uint8Array([80, 75, 5, 6, ...new Array<number>(18).fill(0)]);

export type ExportFrame = "packaging" | "ready" | "expired" | "failed" | "undone";

export interface ExportFixtureOptions {
  workItemId: string;
  engagementId: string;
  /** The seed's clock (ms). */
  now: number;
  /** The first create answers 403 (a stale second factor), as the step-up frame shows. */
  stepUp?: boolean;
  /** An export already in this state when the sheet opens (the sheet's frames). */
  existing?: ExportFrame;
}

const HANNAH = { user_id: stableId("user:hannah-leclerc"), display_name: "Hannah Leclerc" };

function base(options: ExportFixtureOptions, id: string): EngagementExportOut {
  const at = new Date(options.now).toISOString();
  return {
    id,
    engagement_id: options.engagementId,
    work_item_id: options.workItemId,
    kind: "binder",
    scope: { binder_ids: [], include_unaccepted: false, include_audit_trail: true },
    format_version: "1.0",
    status: "queued",
    requested_by: HANNAH,
    requested_at: at,
    not_before: new Date(options.now + 10_000).toISOString(),
    allowed_actions: ["undo"],
  };
}

function moved(view: EngagementExportOut, to: ExportFrame, now: number): EngagementExportOut {
  const at = new Date(now).toISOString();
  switch (to) {
    case "packaging":
      return { ...view, status: "packaging", allowed_actions: [] };
    case "ready":
      return {
        ...view,
        status: "ready",
        ready_at: at,
        expires_at: new Date(now + 7 * 86_400_000).toISOString(),
        request_count: 24,
        file_count: 12,
        size_bytes: 1_258_291,
        manifest_sha256: "a".repeat(64),
        bundle_sha256: "b".repeat(64),
        allowed_actions: ["download"],
      };
    case "expired":
      return {
        ...moved(view, "ready", now),
        status: "expired",
        void_reason: "expired",
        allowed_actions: [],
      };
    case "failed":
      return { ...view, status: "failed", failure_code: "build_error", allowed_actions: [] };
    case "undone":
      return { ...view, status: "undone", allowed_actions: [] };
  }
}

export function exportHandlers(options: ExportFixtureOptions): Record<string, FixtureHandler> {
  const exports = new Map<string, EngagementExportOut>();
  let refusedOnce = options.stepUp !== true;
  let n = 0;
  const reads = new Map<string, number>();
  if (options.existing !== undefined) {
    const id = stableId(`export:${options.workItemId}:existing`);
    exports.set(id, moved(base(options, id), options.existing, options.now));
  }
  const mine = (request: FixtureRequest): boolean =>
    request.params.work_item_id === options.workItemId;
  return {
    "POST /v1/work-items/{work_item_id}/exports": (request) => {
      if (!mine(request)) return json(NOT_FOUND, 404);
      if (!refusedOnce) {
        refusedOnce = true;
        return json({ detail: "forbidden", facts: { reason: "mfa_required" } }, 403); // DEC-547
      }
      n += 1;
      const id = stableId(`export:${options.workItemId}:${String(n)}`);
      const view = base(options, id);
      exports.set(id, view);
      return json(view, 202);
    },
    "GET /v1/work-items/{work_item_id}/exports": (request) =>
      mine(request)
        ? json({ items: [...exports.values()].reverse(), next_cursor: null })
        : json(NOT_FOUND, 404),
    "GET /v1/exports/{export_id}": (request) => {
      const view = exports.get(request.params.export_id ?? "");
      if (view === undefined) return json(NOT_FOUND, 404);
      // Each read is the next moment of the build: Queued (for two reads: the Undo window) →
      // Packaging… → Ready.
      const read = (reads.get(view.id) ?? 0) + 1;
      reads.set(view.id, read);
      const next =
        view.status === "queued"
          ? read < 2
            ? view
            : moved(view, "packaging", options.now)
          : view.status === "packaging"
            ? moved(view, "ready", options.now)
            : view;
      exports.set(view.id, next);
      return json(view);
    },
    "POST /v1/exports/{export_id}/undo": (request) => {
      const view = exports.get(request.params.export_id ?? "");
      if (view === undefined) return json(NOT_FOUND, 404);
      if (view.status !== "queued") return json({ detail: "undo_window_closed" }, 409);
      const undone = moved(view, "undone", options.now);
      exports.set(view.id, undone);
      return json(undone);
    },
    "GET /v1/exports/{export_id}/download": (request) => {
      const view = exports.get(request.params.export_id ?? "");
      if (view === undefined) return json(NOT_FOUND, 404);
      if (view.status === "expired") return json({ detail: "export_expired" }, 410);
      if (view.status !== "ready") return json({ detail: "export_not_ready" }, 409);
      return new Response(EMPTY_ZIP, {
        status: 200,
        headers: {
          "Content-Type": "application/zip",
          "Content-Disposition": `attachment; filename="accrued-binder-${view.id}.zip"`,
          "Cache-Control": "no-store",
        },
      });
    },
  };
}
