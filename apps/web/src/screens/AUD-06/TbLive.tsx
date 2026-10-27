// AUD-06's live actions (A-02-T24; TASK-1472): adopt a trial balance of record from the empty
// state (AC-1), the newer-TB banner and its re-version with a reason (AC-7.1, AC-7.2), Open in
// Excel (AC-8.1), and the source menu's Pull latest and Ask client to reconnect (AC-11.1, AC-12.1).
// Loaded on demand by TrialBalance.tsx (the firm entry is at its budget). Every figure is the
// server's; this file adds and compares no amount.

import type { SnapshotOut, TbLayerViewOut } from "@abacus/api-client";
import {
  adoptTbVersionMutation,
  adoptTrialBalanceMutation,
  connectionOptions,
  ledgerPullMutation,
  reconnectRequestMutation,
  tbCandidatesOptions,
} from "@abacus/api-client/query";
import { tbExport } from "@abacus/api-client";
import { Button, PaneAction, useFormat } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

const SOURCES = COPY.sources;

function idempotency(): { "Idempotency-Key": string } {
  return { "Idempotency-Key": crypto.randomUUID() };
}

/** Open in Excel: the server's file, saved under its own name. */
export async function downloadExport(
  engagementId: string,
  tbId: string,
  layer: TbLayerViewOut["layer"],
  version: number,
): Promise<void> {
  const { data, response } = await tbExport({
    path: { engagement_id: engagementId, tb_id: tbId },
    query: { layer, version },
    parseAs: "blob",
    throwOnError: true,
  });
  const header = response.headers.get("Content-Disposition") ?? "";
  const name = /filename="([^"]+)"/u.exec(header)?.[1] ?? "trial-balance.xlsx";
  const url = URL.createObjectURL(data as Blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

/** AC-1: the empty state's action. The newest pulled snapshot is offered first. */
export function AdoptAction({
  engagementId,
  snapshots,
}: {
  engagementId: string;
  snapshots: readonly SnapshotOut[];
}): JSX.Element {
  const f = useFormat();
  const queryClient = useQueryClient();
  const [chosen, setChosen] = useState(snapshots[0]?.id ?? "");
  const adopt = useMutation({
    ...adoptTrialBalanceMutation(),
    onSuccess: () => {
      void queryClient.invalidateQueries();
    },
  });
  const describe = (s: SnapshotOut): string =>
    COPY.snapshotOption(
      `${s.period_start} – ${s.period_end}`,
      SOURCES[s.source] ?? COPY.otherSource,
      `${f.date(s.pulled_at)} ${f.time(s.pulled_at)}`,
    );
  return (
    <div data-aud06="adopt" className="flex flex-col items-center gap-[8px]">
      <p className="text-meta text-ink-3">{COPY.adoptBody}</p>
      {snapshots.length > 1 ? (
        <label className="flex flex-col gap-[4px] text-meta text-ink-2">
          {COPY.snapshotChoice}
          <select
            value={chosen}
            onChange={(e) => {
              setChosen(e.target.value);
            }}
            className="h-[28px] rounded-tile bg-nested px-[8px] text-body text-ink"
          >
            {snapshots.map((s) => (
              <option key={s.id} value={s.id}>
                {describe(s)}
              </option>
            ))}
          </select>
        </label>
      ) : snapshots[0] !== undefined ? (
        <p className="text-meta text-ink-2">{describe(snapshots[0])}</p>
      ) : null}
      <Button
        size="sm"
        loading={adopt.isPending}
        disabled={chosen === ""}
        onClick={() => {
          adopt.mutate({
            path: { engagement_id: engagementId },
            body: { snapshot_id: chosen, label: "standard" },
          });
        }}
      >
        {COPY.adopt}
      </Button>
      {adopt.isError && (
        <p role="alert" className="text-meta text-red-ink">
          {COPY.failed}
        </p>
      )}
    </div>
  );
}

/** AC-7.1, AC-7.2: the newer pull, its code-computed change count, and Use vN… with a reason. */
export function NewerBanner({
  engagementId,
  view,
}: {
  engagementId: string;
  view: TbLayerViewOut;
}): JSX.Element | null {
  const f = useFormat();
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const path = { engagement_id: engagementId, tb_id: view.trial_balance_id };
  const candidates = useQuery({ ...tbCandidatesOptions({ path }), retry: false });
  const adopt = useMutation({
    ...adoptTbVersionMutation(),
    onSuccess: () => {
      setOpen(false);
      void queryClient.invalidateQueries();
    },
  });
  // Newest first (the server's order): the first pull that differs is the newer one.
  const newer = (candidates.data ?? []).find((c) => (c.lines_changed ?? 0) > 0);
  if (newer === undefined) return null;
  const next = view.current_version_no + 1;
  const may = view.allowed_actions?.includes("trial_balance.adopt") ?? false;
  return (
    <div
      role="status"
      data-aud06="newer"
      className="flex flex-none flex-wrap items-center gap-[8px] bg-nested px-[12px] py-[8px] text-meta text-ink-2"
    >
      <span>{COPY.newer(f.time(newer.pulled_at), newer.lines_changed ?? 0)}</span>
      {may && !open && (
        <PaneAction
          label={COPY.useVersion(next)}
          opensDialog
          onClick={() => {
            setOpen(true);
          }}
        />
      )}
      {open && (
        <span className="flex items-center gap-[6px]">
          <input
            aria-label={COPY.reason}
            placeholder={COPY.reason}
            value={reason}
            maxLength={500}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="h-[26px] w-[220px] rounded-tile bg-card px-[8px] text-body text-ink"
          />
          <Button
            size="xs"
            loading={adopt.isPending}
            disabled={reason.trim() === ""}
            onClick={() => {
              adopt.mutate({
                path,
                body: {
                  snapshot_id: newer.id,
                  reason: reason.trim(),
                  seen_version: view.current_version_no,
                },
              });
            }}
          >
            {COPY.adoptVersion}
          </Button>
          <Button
            size="xs"
            variant="ghost"
            onClick={() => {
              setOpen(false);
            }}
          >
            {COPY.cancel}
          </Button>
        </span>
      )}
      {adopt.isError && (
        <span role="alert" className="text-red-ink">
          {COPY.failed}
        </span>
      )}
    </div>
  );
}

/** The source menu: Pull latest through a live ledger (`ledger.pull`), Ask client to reconnect a
 * connection that needs it (`connection.reconnect_request`). Neither appears for an import. */
export function SourceActions({
  engagementId,
  view,
}: {
  engagementId: string;
  view: TbLayerViewOut;
}): JSX.Element | null {
  const allowed = new Set(view.allowed_actions ?? []);
  const wanted = allowed.has("ledger.pull") || allowed.has("connection.reconnect_request");
  const live = useQuery({
    ...connectionOptions({ path: { engagement_id: engagementId } }),
    enabled: wanted,
    retry: false,
  });
  const [done, setDone] = useState<string | null>(null);
  const pull = useMutation({
    ...ledgerPullMutation(),
    onSuccess: () => {
      setDone(COPY.pullStarted);
    },
  });
  const ask = useMutation({
    ...reconnectRequestMutation(),
    onSuccess: () => {
      setDone(COPY.reconnectAsked);
    },
  });
  const c = live.data;
  if (!wanted || c == null || c.provider === "import") return null;
  const canPull = allowed.has("ledger.pull") && c.status === "active";
  const canAsk = allowed.has("connection.reconnect_request") && c.status === "needs_attention";
  if (!canPull && !canAsk) return null;
  return (
    <span role="group" aria-label={COPY.source} data-aud06="source" className="flex gap-[6px]">
      {canPull && (
        <PaneAction
          icon="refresh-cw"
          label={COPY.pullLatest}
          disabled={pull.isPending}
          onClick={() => {
            pull.mutate({
              path: { engagement_id: engagementId },
              headers: idempotency(),
              body: { period_end: view.period_end, label: view.label },
            });
          }}
        />
      )}
      {canAsk && (
        <PaneAction
          icon="rotate-cw"
          label={COPY.askReconnect}
          disabled={ask.isPending || done === COPY.reconnectAsked}
          onClick={() => {
            ask.mutate({ path: { connection_id: c.id }, headers: idempotency() });
          }}
        />
      )}
      {done !== null && (
        <span role="status" className="text-meta text-ink-3">
          {done}
        </span>
      )}
      {(pull.isError || ask.isError) && (
        <span role="alert" className="text-meta text-red-ink">
          {COPY.failed}
        </span>
      )}
    </span>
  );
}
