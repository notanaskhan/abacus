// The binder export's reads and writes (A-01-T24; docs/contracts/engagement-export-v1.md), over
// the generated client only. Create carries an Idempotency-Key and opens the 10-second Undo toast
// (P-35); the sheet polls the export every 3 seconds while it is open and the export is still
// moving (P-15: polling first). The download asks the API for the bytes (no presigned link,
// ADR-104) and hands them to the browser as a file; a stale second factor opens the step-up.

import type { EngagementExportOut, ExportScopeIn } from "@abacus/api-client";
import { downloadExport } from "@abacus/api-client";
import {
  createExportMutation,
  getExportOptions,
  listExportsOptions,
  undoExportMutation,
} from "@abacus/api-client/query";
import { date, isoDate } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { nowMs } from "../../app-core/clock";

/** P-15: the sheet's poll while it is open. */
export const EXPORT_POLL_MS = 3_000;

/** Statuses that still move on their own (the sheet keeps polling). */
const MOVING = new Set<EngagementExportOut["status"]>(["queued", "packaging"]);

export function isMoving(view: Pick<EngagementExportOut, "status"> | undefined): boolean {
  return view !== undefined && MOVING.has(view.status);
}

/** A 403 that asks for a fresh sign-in (ADR-030): only the server's `mfa_required` refusal
 * (DEC-547). A role or independence refusal is a plain 403 and reads as a problem, never as a
 * step-up. */
export function needsStepUp(error: unknown): boolean {
  const e = error as { facts?: { reason?: unknown } } | null;
  return e?.facts?.reason === "mfa_required";
}

export function errorCode(error: unknown): string | null {
  const detail = (error as { detail?: unknown } | null)?.detail;
  return typeof detail === "string" ? detail : null;
}

/** `GET /v1/work-items/{id}/exports`: the sheet's history, newest first. */
export function useExportHistory(workItemId: string, enabled = true) {
  return useQuery({
    ...listExportsOptions({ path: { work_item_id: workItemId } }),
    enabled,
  });
}

/** `GET /v1/exports/{id}`: the sheet's poll, every 3 s while it moves and the sheet is open. */
export function useExportStatus(exportId: string | null, open: boolean) {
  return useQuery({
    ...getExportOptions({ path: { export_id: exportId ?? "" } }),
    enabled: open && exportId !== null,
    refetchInterval: (query) => (open && isMoving(query.state.data) ? EXPORT_POLL_MS : false),
  });
}

export interface ExportActions {
  /** Create with a fresh key per press; a retried press of the same attempt reuses it. */
  create: (scope: ExportScopeIn) => Promise<EngagementExportOut>;
  undo: (exportId: string) => Promise<EngagementExportOut>;
  creating: boolean;
}

export function useExportActions(workItemId: string): ExportActions {
  const queryClient = useQueryClient();
  const [key, setKey] = useState<string | null>(null);
  const refresh = (): void => {
    void queryClient.invalidateQueries({
      predicate: (q) => {
        const id = (q.queryKey[0] as { _id?: string } | undefined)?._id ?? "";
        return id === "listExports" || id === "getExport";
      },
    });
  };
  const create = useMutation({ ...createExportMutation(), onSettled: refresh });
  const undo = useMutation({ ...undoExportMutation(), onSettled: refresh });
  return {
    create: async (scope) => {
      const attempt = key ?? crypto.randomUUID();
      setKey(attempt);
      const view = await create.mutateAsync({
        path: { work_item_id: workItemId },
        headers: { "Idempotency-Key": attempt },
        body: { kind: "binder", scope },
      });
      setKey(null); // the next press is a new export
      return view;
    },
    undo: (exportId) => undo.mutateAsync({ path: { export_id: exportId } }),
    creating: create.isPending,
  };
}

/** How long the downloaded ZIP's object URL stays valid after the click. */
export const REVOKE_AFTER_MS = 60_000;

/** `GET /v1/exports/{id}/download`: the ZIP as a file named by the server (ASCII, no names).
 * The request carries the bearer token, so it can't be a plain link: the bytes come through the
 * generated client as a Blob (DEC-547; a service-worker stream is a follow-up). */
export async function downloadBundle(exportId: string): Promise<void> {
  const { data, response } = await downloadExport({
    path: { export_id: exportId },
    parseAs: "blob",
    throwOnError: true,
  });
  const header = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/.exec(header)?.[1] ?? `accrued-binder-${exportId}.zip`;
  const url = URL.createObjectURL(data);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  // L9 (DEC-547): the browser reads the object URL after the click returns; free it later.
  window.setTimeout(() => {
    URL.revokeObjectURL(url);
  }, REVOKE_AFTER_MS);
}

const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"] as const;

/** "Mon Sep 21": the expiry as the sheet words it, on the firm's calendar. */
export function expiryLabel(iso: string, now: number = nowMs()): string {
  const day = isoDate(new Date(iso));
  const weekday = WEEKDAYS[new Date(`${day}T12:00:00Z`).getUTCDay()] ?? "";
  return `${weekday} ${date(day, { now })}`;
}
