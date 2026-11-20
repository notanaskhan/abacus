// CLS-07 · Adjustments & thresholds (C-02-T17, DEC-5637; handoff CLS-07 a, a2, b, c, c2, d, e,
// f, g; SPEC-700): the close's proposed entries on T6, sorted by the firm's per-class threshold
// policy. Every figure and every status is code's (`GET …/proposed-entries:close`, C8 v2); the
// browser formats and never sums. A batch approval is the named person's (`POST
// /v1/approval-batches`, SHL-10 batch variant); a held entry is approved by a Manager or Partner
// with a 10-second Undo. The attest client never shows Post (DEC-69); with posting off the
// primary is "Export approved entries…" (DF-19). Accrued Agent never approves.
import type {
  EntryOut,
  PostingCloseEntriesOut,
  PostingCloseEntryRowOut,
} from "@abacus/api-client";
import {
  approvalBatchMutation,
  approveEntryMutation,
  closeEntriesOptions,
  closeEntriesQueryKey,
  dryRunMutation,
  postBatchMutation,
  proposedEntriesOptions,
  postingRequestApprovalMutation,
  retryEntryMutation,
  undoApprovalMutation,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  ConfirmDialog,
  DASH,
  Dialog,
  Segmented,
  Skeleton,
  StatusDisc,
  Pill,
  TallyStrip,
  amount,
  cn,
  dateTime,
  time,
  toast,
} from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY as C } from "./copy";

export interface CLS07Props {
  workItemId: string;
  /** "August 2026" (the close's period, from the close shell). */
  periodLabel: string;
  initial?: { selected?: string; batchOpen?: boolean; postOpen?: boolean };
  /** The Manager or Partner a held entry is routed to (the engagement team's). */
  approver?: { userId: string; name: string };
  /** The per-row Lines count when the read names no lines (handoff Lines column). */
  lineCount?: (ref: string) => number;
  onIssues?: () => void;
  onFlux?: () => void;
  onThresholds?: () => void;
  onReject?: (entryId: string) => void;
  onEdit?: (entryId: string) => void;
  onPost?: (entryIds: readonly string[]) => void;
  onExport?: () => void;
  onSendToClient?: () => void;
  /** CLS-07d → CLS-11: "View in ledger sync ›". */
  onLedgerSync?: (() => void) | undefined;
}

const TH = "h-[30px] bg-nested px-[10px] text-[11.5px] font-medium text-ink-2";
const TD = "px-[10px] text-[13px]";
const DONE = new Set(["approved", "posted", "client_approved", "recorded_externally"]);

function thresholdText(row: PostingCloseEntryRowOut): { text: string; over: boolean } {
  const limit = row.class_limit;
  if (limit === null || limit === undefined) return { text: C.noClass, over: false };
  const cls = C.classes[limit.account_class] ?? limit.account_class;
  const shown = amount(limit.limit, "dollars").text;
  const over = Number(row.amount) > Number(limit.limit);
  return { text: over ? C.over(shown, cls) : C.under(shown, cls), over };
}

function Disc({ row }: { row: PostingCloseEntryRowOut }): JSX.Element {
  return (
    <StatusDisc
      size={17}
      state={DONE.has(row.status) || row.status === "within_threshold" ? "done" : "todo"}
    />
  );
}

function Tallies({ view }: { view: PostingCloseEntriesOut }): JSX.Element {
  const t = view.tallies;
  const pair = (n: number, v: string): string => `${String(n)} · ${amount(v).text}`;
  return (
    <TallyStrip
      className="px-[12px]"
      label={C.tallyLabel}
      items={[
        { label: C.tally.proposed, value: pair(t.proposed.count, t.proposed.amount) },
        {
          label: C.tally.within,
          value: pair(t.within_threshold.count, t.within_threshold.amount),
        },
        { label: C.tally.review, value: pair(t.review_required.count, t.review_required.amount) },
        { label: C.tally.approved, value: `${String(t.approved)} of ${String(t.of)}` },
        {
          label: C.tally.posted,
          pill:
            t.posted_batch_code === null || t.posted_batch_code === undefined
              ? { text: C.tally.pending, variant: "neutral" }
              : { text: t.posted_batch_code, variant: "green", check: true },
        },
      ]}
    />
  );
}

function Detail({
  row,
  entry,
  view,
  props,
  onApprove,
  onRequest,
}: {
  row: PostingCloseEntryRowOut;
  entry: EntryOut | undefined;
  view: PostingCloseEntriesOut;
  props: CLS07Props;
  onApprove: () => void;
  onRequest: () => void;
}): JSX.Element {
  const may = new Set(row.allowed_actions ?? []);
  const limit = row.class_limit;
  const held = row.status === "review_required";
  const lines = entry?.lines ?? [];
  return (
    <section
      aria-label={`${row.ref} · ${row.description ?? ""}`}
      className="flex min-h-0 flex-col"
    >
      <header className="flex h-[46px] items-center justify-center text-[13px] font-medium">
        {`${row.ref} · ${row.description ?? ""}`}
      </header>
      <div className="flex min-h-0 flex-1 flex-col gap-[10px] overflow-auto bg-shell p-[10px]">
        <dl data-cls07="kv" className="rounded-card bg-card shadow-e1">
          {(
            [
              [C.detail.status, C.status[row.status] ?? row.status],
              [
                C.detail.cls,
                limit
                  ? C.detail.limit(
                      (C.classes[limit.account_class] ?? limit.account_class).replace(/^./, (c) =>
                        c.toUpperCase(),
                      ),
                      amount(limit.limit, "dollars").text,
                      view.approver.policy_label,
                    )
                  : C.noClass,
              ],
              [C.detail.amount, amount(row.amount).text],
              [C.detail.reverses, row.reverses_on ? C.detail.auto(row.reverses_on) : DASH],
              ...(held ? [[C.detail.approver, C.detail.managerOrPartner]] : []),
            ] as const
          ).map(([k, v]) => (
            <div key={k} className="flex h-[33px] items-center px-[12px] text-[13px]">
              <dt className="w-[160px] text-ink-2">{k}</dt>
              <dd>{v}</dd>
            </div>
          ))}
        </dl>
        <div data-cls07="lines" className="rounded-card bg-card shadow-e1">
          <div className="px-[12px] py-[8px] text-[13px] font-medium">{C.detail.lines}</div>
          {lines.length === 0 ? (
            <p className="px-[12px] pb-[10px] text-[12.5px] text-ink-3">{C.detail.noLines}</p>
          ) : (
            <table className="w-full">
              <thead>
                <tr>
                  {C.detail.lineColumns.map((h, i) => (
                    <th key={h} className={cn(TH, i > 0 && "text-right")}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {lines.map((l) => (
                  <tr key={l.line_no} className="h-[30px]">
                    <td className={TD}>{l.account_name ?? l.account_code}</td>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={l.debit} zero="dash" />
                    </td>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={l.credit} zero="dash" />
                    </td>
                  </tr>
                ))}
                <tr className="h-[30px] font-medium">
                  <td className={TD}>{C.detail.total}</td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={row.amount} />
                  </td>
                  <td className={cn(TD, "text-right")}>
                    <Amount value={row.amount} />
                  </td>
                </tr>
              </tbody>
            </table>
          )}
        </div>
      </div>
      {held && !view.is_attest_client ? (
        <footer className="flex flex-wrap gap-[8px] p-[10px]">
          {may.has("proposed_entry.approve") ? (
            <Button variant="primary" className="w-full" onClick={onApprove}>
              {C.actions.approve}
            </Button>
          ) : (
            <>
              <Button variant="primary" disabled>
                {C.actions.approveLocked}
              </Button>
              {may.has("proposed_entry.request_approval") && props.approver ? (
                <Button variant="secondary" onClick={onRequest}>
                  {C.actions.requestFrom(props.approver.name)}
                </Button>
              ) : null}
            </>
          )}
          <Button variant="tonal" onClick={() => props.onEdit?.(row.entry_id)}>
            {C.actions.edit}
          </Button>
          {may.has("proposed_entry.reject_close") ? (
            <Button variant="destructive" onClick={() => props.onReject?.(row.entry_id)}>
              {C.actions.reject}
            </Button>
          ) : null}
        </footer>
      ) : null}
    </section>
  );
}

/** CLS-07d: the posted batch's banner, every figure from the read. */
function PostedBanner({
  view,
  onLedgerSync,
}: {
  view: PostingCloseEntriesOut;
  onLedgerSync?: (() => void) | undefined;
}): JSX.Element {
  const t = view.tallies;
  const code = t.posted_batch_code ?? "";
  const n = t.posted_count ?? 0;
  const total = amount(t.posted_amount ?? "0.00").text;
  const text =
    t.closing_date_set && t.posted_at
      ? C.posted.banner(code, n, total, dateTime(t.closing_date_set), time(t.posted_at))
      : C.posted.bannerNoClosing(code, n, total);
  return (
    <div
      role="status"
      data-cls07="posted"
      className="mx-[10px] flex h-[36px] items-center justify-between rounded-[8px] bg-green-tint px-[12px] text-[12.5px] text-green-ink"
    >
      <span>
        {text}
        {(t.resolved_failure_count ?? 0) > 0
          ? ` · ${C.posted.resolved(t.resolved_failure_count ?? 0)}`
          : ""}
      </span>
      <button type="button" className="font-medium hover:underline" onClick={onLedgerSync}>
        {C.posted.ledgerSync}
      </button>
    </div>
  );
}

/** A row's status: d's green "Posted · QBO 48213", e's red pill with its line and Retry, g's
 * attest hold. Retry is a person's (the read names `posting_batch.post`); never an agent's. */
function StatusCell({
  row,
  attest,
  retrying,
  onRetry,
}: {
  row: PostingCloseEntryRowOut;
  attest: boolean;
  retrying: boolean;
  onRetry: () => void;
}): JSX.Element {
  if (attest && row.status === "review_required") return <>{C.attestHeld}</>;
  if (row.status === "posted" && row.external_txn_ref) {
    return <Pill variant="green-tint">{C.posted.qbo(row.external_txn_ref)}</Pill>;
  }
  if (row.status === "failed_post") {
    const may = (row.allowed_actions ?? []).includes("posting_batch.post");
    return (
      <div className="flex flex-col items-start gap-[4px] py-[4px]">
        <Pill variant="red">{C.status.failed_post}</Pill>
        {row.failure_line ? (
          <span className="text-[12.5px] text-red">{row.failure_line}</span>
        ) : null}
        {may && !attest ? (
          <Button
            variant="secondary"
            size="sm"
            disabled={retrying}
            onClick={(e) => {
              e.stopPropagation();
              onRetry();
            }}
          >
            {retrying ? C.retrying : C.retry}
          </Button>
        ) : null}
      </div>
    );
  }
  return <>{C.status[row.status] ?? row.status}</>;
}

export function CLS07(props: CLS07Props): JSX.Element {
  const { workItemId, initial = {} } = props;
  const path = { work_item_id: workItemId };
  const qc = useQueryClient();
  const view = useQuery(closeEntriesOptions({ path }));
  const lines = useQuery(proposedEntriesOptions({ path }));
  const [picked, setPicked] = useState<string | undefined>(initial.selected);
  const [batchOpen, setBatchOpen] = useState(initial.batchOpen === true);
  const [postOpen, setPostOpen] = useState(initial.postOpen === true);
  const refresh = (): void => {
    void qc.invalidateQueries({ queryKey: closeEntriesQueryKey({ path }) });
  };
  const batch = useMutation({ ...approvalBatchMutation(), onSuccess: refresh });
  const approve = useMutation({ ...approveEntryMutation(), onSuccess: refresh });
  const request = useMutation({ ...postingRequestApprovalMutation(), onSuccess: refresh });
  const undo = useMutation({ ...undoApprovalMutation(), onSuccess: refresh });
  // C-02-T31: c2 reads the dry run (preflight only, nothing written); confirming posts the batch
  // under an Idempotency-Key; e's Retry re-posts one failed entry under its own grant.
  const dry = useMutation(dryRunMutation());
  const post = useMutation({ ...postBatchMutation(), onSuccess: refresh });
  const retry = useMutation({ ...retryEntryMutation(), onSuccess: refresh });

  if (view.data === undefined) {
    return <Skeleton aria-label={C.entries} className="h-[604px] w-full" />;
  }
  const data = view.data;
  const rows = data.items;
  const within = rows.filter((r) => r.status === "within_threshold");
  const approved = rows.filter((r) => r.status === "approved" || r.status === "failed_post");
  const held = rows.filter((r) => r.status === "review_required");
  const selected =
    rows.find((r) => r.ref === picked) ?? held[0] ?? rows[rows.length - 1] ?? undefined;
  const withinTotal = data.tallies.within_threshold.amount;

  const primary = ((): JSX.Element | null => {
    if (data.is_attest_client) {
      return (
        <Button variant="primary" onClick={props.onSendToClient}>
          {C.sendToClient}
        </Button>
      );
    }
    if (within.length > 0 && data.approver.may_batch_within_threshold) {
      return (
        <Button
          variant="primary"
          onClick={() => {
            setBatchOpen(true);
          }}
        >
          {C.approveWithin(within.length)}
        </Button>
      );
    }
    if (approved.length === 0) return null;
    if (!data.posting_enabled) {
      return (
        <Button variant="primary" onClick={props.onExport}>
          {C.exportApproved}
        </Button>
      );
    }
    return (
      <Button
        variant={held.length > 0 ? "secondary" : "primary"}
        onClick={() => {
          dry.mutate({ path, body: { entry_ids: approved.map((r) => r.entry_id) } });
          setPostOpen(true);
        }}
      >
        {C.postApproved(approved.length)}
      </Button>
    );
  })();

  return (
    <div data-screen="CLS-07" className="flex min-h-0 flex-col">
      <div className="flex h-[44px] items-center justify-between px-[12px]">
        <Segmented
          size="small"
          label={C.segmentsLabel}
          active={C.segments.adjustments}
          options={[C.segments.issues, C.segments.adjustments, C.segments.flux]}
          onChange={(v) => {
            if (v === C.segments.issues) props.onIssues?.();
            if (v === C.segments.flux) props.onFlux?.();
          }}
        />
        <h1 className="text-[14.5px] font-medium">{C.title(props.periodLabel)}</h1>
        <button
          type="button"
          data-cls07="thresholds"
          onClick={props.onThresholds}
          className="h-[29px] rounded-pill bg-card px-[10px] text-[12.5px] shadow-e1"
        >
          {C.thresholds(data.approver.policy_label)}
        </button>
      </div>
      <Tallies view={data} />
      {data.tallies.posted_batch_code ? (
        <PostedBanner view={data} onLedgerSync={props.onLedgerSync} />
      ) : null}
      <div className="flex min-h-0 flex-1 gap-[10px] p-[10px]">
        <section
          aria-label={C.entries}
          className="flex min-w-0 flex-[866] flex-col rounded-card bg-card shadow-e1"
        >
          <header className="flex h-[46px] items-center justify-between px-[12px]">
            <span className="text-[13px] text-ink-3">{C.search}</span>
            <span className="text-[13px] font-medium">{C.entries}</span>
            <Button variant="ghost" size="sm">
              {C.excel}
            </Button>
          </header>
          <table className="w-full">
            <thead>
              <tr>
                <th className={cn(TH, "w-[32px]")}>
                  <span className="sr-only">{C.columns.status}</span>
                </th>
                <th className={cn(TH, "text-left")}>{C.columns.entry}</th>
                <th className={cn(TH, "text-left")}>{C.columns.threshold}</th>
                <th className={cn(TH, "text-right")}>{C.columns.lines}</th>
                <th className={cn(TH, "text-right")}>{C.columns.amount}</th>
                <th className={cn(TH, "text-left")}>{C.columns.status}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const th = thresholdText(r);
                const on = r.entry_id === selected?.entry_id;
                const n =
                  lines.data?.items.find((e) => e.ref === r.ref)?.lines.length ||
                  props.lineCount?.(r.ref) ||
                  0;
                return (
                  <tr
                    key={r.entry_id}
                    data-entry={r.ref}
                    data-status={r.status}
                    aria-selected={on}
                    onClick={() => {
                      setPicked(r.ref);
                    }}
                    className={cn(
                      "h-[52px] cursor-pointer border-b border-hair",
                      on && "bg-selected",
                    )}
                  >
                    <td className={TD}>
                      <Disc row={r} />
                    </td>
                    <td className={TD}>
                      <div className="text-[13.5px]">{`${r.ref} ${r.description ?? ""}`}</div>
                      {r.approval_label ? (
                        <div className="text-[11.5px] text-green-ink">{r.approval_label}</div>
                      ) : null}
                    </td>
                    <td className={cn(TD, th.over && "text-amber-ink")}>{th.text}</td>
                    <td className={cn(TD, "text-right")}>{n || DASH}</td>
                    <td className={cn(TD, "text-right")}>
                      <Amount value={r.amount} />
                    </td>
                    <td
                      className={cn(
                        TD,
                        r.status === "review_required" && "font-medium text-amber-ink",
                      )}
                    >
                      <StatusCell
                        row={r}
                        attest={data.is_attest_client}
                        retrying={retry.isPending}
                        onRetry={() => {
                          if (!r.posting_batch_id) return;
                          retry.mutate({
                            path: { batch_id: r.posting_batch_id, entry_id: r.entry_id },
                            headers: { "Idempotency-Key": `cls07-retry-${crypto.randomUUID()}` },
                          });
                        }}
                      />
                    </td>
                  </tr>
                );
              })}
              <tr className="h-[37px] bg-nested font-medium">
                <td className={TD} />
                <td className={TD}>{C.total(data.total)}</td>
                <td className={TD} />
                <td className={TD} />
                <td className={cn(TD, "text-right")}>
                  <Amount value={data.tallies.proposed.amount} />
                </td>
                <td className={TD} />
              </tr>
            </tbody>
          </table>
          <footer className="mt-auto flex h-[56px] items-center justify-between gap-[8px] border-t border-hair px-[12px]">
            <span className="text-[12.5px] text-ink-3">
              {C.approvingAs(
                data.approver.display_name,
                data.approver.role_label,
                data.approver.policy_label,
              )}
            </span>
            <span className="flex gap-[8px]">
              {held.length > 0 ? (
                <Button
                  variant="secondary"
                  onClick={() => {
                    setPicked(held[0]?.ref);
                  }}
                >
                  {C.reviewHeld(held.length)}
                </Button>
              ) : null}
              {primary}
            </span>
          </footer>
        </section>
        <div className="flex min-w-0 flex-[500] flex-col rounded-card bg-card shadow-e1">
          {selected ? (
            <Detail
              row={selected}
              entry={lines.data?.items.find((e) => e.ref === selected.ref)}
              view={data}
              props={props}
              onApprove={() => {
                approve.mutate(
                  {
                    path: { entry_id: selected.entry_id },
                    body: { seen_version: selected.version },
                  },
                  {
                    onSuccess: (d) => {
                      toast.undoable({
                        text: C.status.approved ?? "",
                        undo: () => {
                          undo.mutate({ path: { decision_id: d.decision_id } });
                        },
                      });
                    },
                  },
                );
              }}
              onRequest={() => {
                if (props.approver === undefined) return;
                request.mutate({
                  path: { entry_id: selected.entry_id },
                  body: { user_id: props.approver.userId },
                });
              }}
            />
          ) : null}
        </div>
      </div>
      <Dialog
        open={batchOpen}
        onOpenChange={setBatchOpen}
        title={C.batch.title(within.length, data.approver.policy_label)}
        action={
          <Button
            variant="primary"
            className="w-full"
            onClick={() => {
              batch.mutate({
                headers: { "Idempotency-Key": `cls07-batch-${crypto.randomUUID()}` },
                body: {
                  entry_ids: within.map((r) => r.entry_id),
                  policy_version_id: data.approver.policy_version_id,
                },
              });
              setBatchOpen(false);
            }}
          >
            {C.batch.confirm}
          </Button>
        }
      >
        <ul data-cls07="batch" className="flex flex-col gap-[4px] p-[16px] text-[13px]">
          {within.map((r) => (
            <li key={r.entry_id} className="flex justify-between">
              <span>{`${r.ref} ${r.description ?? ""}`}</span>
              <Amount value={r.amount} />
            </li>
          ))}
          <li className="flex justify-between font-medium">
            <span>{C.batch.total}</span>
            <Amount value={withinTotal} />
          </li>
        </ul>
      </Dialog>
      <ConfirmDialog
        open={postOpen}
        onOpenChange={setPostOpen}
        destructive={false}
        title={
          dry.data
            ? C.postTitle(
                dry.data.entry_count,
                amount(dry.data.total_amount).text,
                dry.data.client_entity_name,
              )
            : C.post.title(approved.length, amount(data.tallies.proposed.amount).text)
        }
        confirmLabel={C.post.confirm}
        onConfirm={() => {
          const ids = approved.map((r) => r.entry_id);
          post.mutate({
            path,
            headers: { "Idempotency-Key": `cls07-post-${crypto.randomUUID()}` },
            body: {
              entry_ids: ids,
              seen_versions: Object.fromEntries(approved.map((r) => [r.entry_id, r.version])),
              set_closing_date: true,
            },
          });
          props.onPost?.(ids);
        }}
      >
        {dry.data
          ? dry.data.closing_date_target
            ? C.closingSentence(dateTime(dry.data.closing_date_target))
            : C.noClosing
          : C.post.body}
      </ConfirmDialog>
    </div>
  );
}
