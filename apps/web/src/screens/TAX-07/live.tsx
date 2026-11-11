// T-04-T29 (TASK-6828): TAX-07 Activity and Checkpoints on a live build. Activity is P-05's
// engagement activity for this return (`POST /v1/engagements/{id}/audit-events/query` with the
// return's `work_item_id`; an agent's row names its person "… via Agent"); Checkpoints is C3's
// history on the return (`GET /v1/checkpoints?target_type=tax_return…`), with Approve and Reject
// (a reason) on a proposed checkpoint through the review domain (never optimistic). A refusal
// shows its words.
import { engagementActivityQueryMutation } from "@abacus/api-client/query";
import type { AuditEventRow, CheckpointItemOut } from "@abacus/api-client";
import { Button, EmptyState, Pill, dateTime } from "@abacus/ui";
import { useMutation } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { useCheckpointHistory, useCheckpointWrites } from "../../domain/review";
import { blockerWords, useReturnLive } from "../TAX-04/live-core";
import { COPY } from "./copy";

export const ACTIVITY_LIVE_COPY = {
  loading: "Loading activity…",
  reject: "Reject…",
  reason: "Reason",
  confirmReject: "Reject",
  noCheckpoints: "No checkpoints yet.",
  viaAgent: (name: string) => `${name} via Agent`,
} as const;

export interface ActivityLiveProps {
  returnId: string;
  engagementId: string | undefined;
}

/** "document.approval_reversed" → "Document · approval reversed" (the row's own action). */
function actionWords(action: string): string {
  const [noun = "", verb = ""] = action.split(".");
  const head = noun.replaceAll("_", " ");
  return `${head.charAt(0).toUpperCase()}${head.slice(1)} · ${verb.replaceAll("_", " ")}`;
}

function actorWords(row: AuditEventRow): string {
  const a = row.actor;
  if (a.kind === "via_agent") {
    return ACTIVITY_LIVE_COPY.viaAgent(
      a.on_behalf_of?.display_name ?? a.person?.display_name ?? "",
    );
  }
  return a.person?.display_name ?? (a.kind === "policy" ? (a.policy_ref ?? "") : "");
}

function Checkpoint({ cp }: { cp: CheckpointItemOut }): JSX.Element {
  const writes = useCheckpointWrites();
  const [asking, setAsking] = useState(false);
  const [reason, setReason] = useState("");
  const [words, setWords] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const act = async (run: () => Promise<unknown>): Promise<void> => {
    setWords([]);
    setBusy(true);
    try {
      await run();
      setAsking(false);
    } catch (error) {
      setWords(blockerWords(error));
    } finally {
      setBusy(false);
    }
  };
  const proposed = cp.status === "proposed";
  return (
    <li
      data-checkpoint={cp.id}
      data-status={cp.status}
      className="flex flex-col gap-[4px] border-b border-hairline px-[12px] py-[8px]"
    >
      <div className="flex items-center gap-[8px]">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="truncate text-[13px] font-medium">{cp.name ?? cp.summary ?? ""}</span>
          <span className="text-[11.5px] text-ink-3">{cp.author_name}</span>
        </span>
        <Pill variant={cp.current ? "green-tint" : proposed ? "amber" : "neutral"} size="state">
          {cp.current ? COPY.current : proposed ? COPY.proposed : COPY.approved}
        </Pill>
        {proposed && cp.allowed_actions.includes("checkpoint.approve") ? (
          <>
            <Button
              variant="primary"
              size="sm"
              disabled={busy}
              onClick={() => void act(() => writes.approve(cp))}
            >
              {COPY.approve}
            </Button>
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={asking}
              onClick={() => {
                setAsking(!asking);
              }}
            >
              {ACTIVITY_LIVE_COPY.reject}
            </Button>
          </>
        ) : null}
      </div>
      {asking ? (
        <div className="flex gap-[6px]">
          <input
            aria-label={ACTIVITY_LIVE_COPY.reason}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
            }}
            className="flex-1 rounded-[6px] border border-hairline px-[6px] text-[12.5px]"
          />
          <Button
            variant="secondary"
            size="sm"
            disabled={busy || reason.trim() === ""}
            onClick={() => void act(() => writes.reject(cp, reason.trim()))}
          >
            {ACTIVITY_LIVE_COPY.confirmReject}
          </Button>
        </div>
      ) : null}
      {words.map((w) => (
        <p key={w} role="alert" className="text-[12.5px] text-red-ink">
          {w}
        </p>
      ))}
    </li>
  );
}

export function ActivityLive({ returnId, engagementId }: ActivityLiveProps): JSX.Element {
  const interval = useReturnLive(engagementId);
  const checkpoints = useCheckpointHistory({ type: "tax_return", id: returnId }, "all");
  const query = useMutation({ ...engagementActivityQueryMutation() });
  const [rows, setRows] = useState<readonly AuditEventRow[] | null>(null);
  const { mutateAsync } = query;
  useEffect(() => {
    if (engagementId === undefined) return undefined;
    let live = true;
    const load = (): void => {
      void mutateAsync({
        path: { engagement_id: engagementId },
        body: { work_item_id: returnId, limit: 100 },
      }).then((page) => {
        if (live) setRows(page.items);
      });
    };
    load();
    // The activity query is a POST: it refreshes on the record's poll, and on the stream's
    // refetch of the checkpoint history (a decided checkpoint is a new event).
    const timer = interval === false ? undefined : window.setInterval(load, interval);
    return () => {
      live = false;
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, [engagementId, returnId, interval, mutateAsync, checkpoints.dataUpdatedAt]);
  return (
    <div data-screen="TAX-07" data-live className="flex gap-[10px] p-[12px]">
      <section
        aria-label={COPY.activity}
        className="flex min-w-0 flex-1 flex-col rounded-pane bg-card shadow-e1"
      >
        <div className="flex h-[46px] items-center px-[12px] font-medium">{COPY.activity}</div>
        {rows === null ? (
          <p className="p-[12px] text-ink-3">{ACTIVITY_LIVE_COPY.loading}</p>
        ) : rows.length === 0 ? (
          <EmptyState title={COPY.emptyFilter} />
        ) : (
          <ol className="flex flex-col">
            {rows.map((r) => (
              <li
                key={r.seq}
                data-event={r.action}
                className="flex flex-col border-b border-hairline px-[12px] py-[6px]"
              >
                <span className="text-[13px]">
                  {actionWords(r.action)}
                  {r.target.label ? ` · ${r.target.label}` : ""}
                </span>
                <span className="text-[11.5px] text-ink-3">
                  {actorWords(r)} · {dateTime(r.effective_at)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
      <section
        aria-label={COPY.checkpoints}
        className="flex w-[377px] shrink-0 flex-col rounded-pane bg-card shadow-e1"
      >
        <div className="flex h-[46px] items-center px-[12px] font-medium">{COPY.checkpoints}</div>
        {(checkpoints.data?.items ?? []).length === 0 ? (
          <p className="p-[12px] text-ink-3">{ACTIVITY_LIVE_COPY.noCheckpoints}</p>
        ) : (
          <ul className="flex flex-col">
            {(checkpoints.data?.items ?? []).map((cp) => (
              <Checkpoint key={cp.id} cp={cp} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
