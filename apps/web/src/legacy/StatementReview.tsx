import type { StatementDecisionsBody, StatementOut } from "@abacus/api-client";
import {
  approveStatementMutation,
  statementOptions,
  statementPreviewMutation,
  statementQueryKey,
} from "@abacus/api-client/query";
import { Button, Skeleton, StatusPill, toast } from "@abacus/ui";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { type JSX, useEffect, useState } from "react";
import { errorMessage } from "../api";
import { amount } from "./amounts";
import { SourceHover } from "./SourceHover";

// SPEC-312 phase 2-3 (TASK-324): a statement's transactions, read from the file by the server
// and reconciled by code (opening + included lines = closing). The reviewer excludes lines with
// a reason, flips an export's inferred signs, and types balances the file doesn't print; the
// server applies them and reconciles again. Only a reconciled statement can be approved, and
// what was approved is kept as approved.

type Ids = { engagementId: string; itemId: string; versionId: string };

const KIND: Record<StatementOut["account_kind"], string> = {
  credit_card: "Credit card",
  bank: "Bank account",
  unknown: "Statement",
};
const AMOUNT = /^-?\d{1,14}(\.\d{1,2})?$/;

/** The body the server takes, or null while a typed balance or a reason is incomplete. */
export function decisionsBody(
  excluded: Map<number, string>,
  flip: boolean,
  opening: string,
  closing: string,
): StatementDecisionsBody | null {
  const open = opening.replace(/,/g, "").trim();
  const close = closing.replace(/,/g, "").trim();
  if ((open !== "" && !AMOUNT.test(open)) || (close !== "" && !AMOUNT.test(close))) return null;
  if ([...excluded.values()].some((r) => r.trim() === "")) return null;
  return {
    excluded: [...excluded].map(([position, reason]) => ({ position, reason: reason.trim() })),
    flip_signs: flip,
    ...(open === "" ? {} : { opening: open }),
    ...(close === "" ? {} : { closing: close }),
  };
}

export function StatementReview({
  ids,
  canApprove,
}: {
  ids: Ids;
  canApprove: boolean;
}): JSX.Element {
  const queryClient = useQueryClient();
  const path = {
    path: { engagement_id: ids.engagementId, item_id: ids.itemId, version_id: ids.versionId },
  };
  const statement = useQuery({ ...statementOptions(path), retry: false });
  const [excluded, setExcluded] = useState<Map<number, string>>(new Map());
  const [flip, setFlip] = useState(false);
  const [opening, setOpening] = useState("");
  const [closing, setClosing] = useState("");
  const preview = useMutation({ ...statementPreviewMutation() });
  const approve = useMutation({
    ...approveStatementMutation(),
    onSuccess: (data) => {
      queryClient.setQueryData(statementQueryKey(path), data);
      preview.reset();
    },
    onError: (e) => {
      const code = errorMessage(e);
      toast.show(
        code === "statement_not_reconciled"
          ? "The statement doesn't reconcile yet."
          : code === "statement_already_approved"
            ? "This statement is already approved."
            : code,
      );
    },
  });
  const body = decisionsBody(excluded, flip, opening, closing);
  const touched = excluded.size > 0 || flip || opening !== "" || closing !== "";
  const bodyKey = JSON.stringify(body);
  useEffect(() => {
    if (!touched || body === null || statement.data?.status !== "draft") return;
    const timer = setTimeout(() => {
      preview.mutate({ ...path, body });
    }, 350);
    return () => {
      clearTimeout(timer);
    };
  }, [bodyKey, touched, statement.data?.status]);
  if (statement.isPending) return <Skeleton className="h-24" />;
  if (statement.isError) {
    return (
      <p className="text-body text-muted">
        {errorMessage(statement.error) === "no_transactions"
          ? "No statement transactions found in this file."
          : "The transactions couldn't be read."}
      </p>
    );
  }
  const s = touched && preview.data !== undefined ? preview.data : statement.data;
  const approved = s.status === "approved";
  const rec = s.reconciliation;
  const included = s.lines.filter((l) => !l.excluded).length;
  /** A printed balance that points back to where it was printed (TASK-334). */
  const printed = (field: "opening" | "closing", text: string): JSX.Element | string => {
    const at = s.sources?.[field];
    if (at == null) return text;
    return (
      <SourceHover
        engagementId={ids.engagementId}
        source={{ versionId: ids.versionId, itemId: ids.itemId, page: at.page, box: at.box }}
        label={`the ${field} balance`}
      >
        {text}
      </SourceHover>
    );
  };
  const input =
    "h-[28px] w-[130px] rounded-tile border-0 bg-nested px-2 text-[12.5px] tabular-nums inset-shadow-hair";
  return (
    <div className="flex flex-col gap-2 text-[12.5px]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="font-medium">{KIND[s.account_kind]}</span>
        {s.last4 != null && <span className="tabular-nums">{`•••• ${s.last4}`}</span>}
        {s.period_end != null && (
          <span className="text-ink-3 tabular-nums">
            {`${s.period_start ?? "…"} – ${s.period_end}`}
          </span>
        )}
        <span className="text-ink-3 tabular-nums">{`${String(included)} of ${String(s.lines.length)} lines`}</span>
        <span className="flex-1" />
        {rec.reconciled ? (
          <StatusPill tone="success">Reconciled</StatusPill>
        ) : rec.difference != null ? (
          <StatusPill tone="warning">{`Off ${amount(rec.difference)}`}</StatusPill>
        ) : (
          <StatusPill tone="neutral">Needs balances</StatusPill>
        )}
      </div>
      <dl className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-4">
        <div>
          <dt className="text-ink-3">Opening balance</dt>
          <dd className="tabular-nums">
            {s.printed_opening || approved ? (
              printed("opening", amount(s.opening))
            ) : (
              <input
                aria-label="Opening balance"
                value={opening}
                placeholder="as printed"
                onChange={(e) => {
                  setOpening(e.target.value);
                }}
                className={input}
              />
            )}
          </dd>
        </div>
        <div>
          <dt className="text-ink-3">Lines</dt>
          <dd className="tabular-nums">{amount(rec.lines_total)}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Expected closing</dt>
          <dd className="tabular-nums">{amount(rec.expected_closing)}</dd>
        </div>
        <div>
          <dt className="text-ink-3">Closing balance</dt>
          <dd className="tabular-nums">
            {s.printed_closing || approved ? (
              printed("closing", amount(s.closing))
            ) : (
              <input
                aria-label="Closing balance"
                value={closing}
                placeholder="as printed"
                onChange={(e) => {
                  setClosing(e.target.value);
                }}
                className={input}
              />
            )}
          </dd>
        </div>
      </dl>
      {s.signs_inferred && !approved && (
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={flip}
            onChange={(e) => {
              setFlip(e.target.checked);
            }}
          />
          Charges and payments look reversed: flip the signs
        </label>
      )}
      {s.truncated && <p className="text-ink-3">Only the first 5,000 lines were read.</p>}
      <div className="max-h-[420px] overflow-auto rounded-nested shadow-e1">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 bg-band-hd text-ink-3">
            <tr>
              <th scope="col" className="px-2 py-1 text-left font-medium">
                Include
              </th>
              <th scope="col" className="px-2 py-1 text-left font-medium">
                Date
              </th>
              <th scope="col" className="px-2 py-1 text-left font-medium">
                Description
              </th>
              <th scope="col" className="px-2 py-1 text-right font-medium">
                Amount
              </th>
            </tr>
          </thead>
          <tbody>
            {s.lines.map((l) => {
              const reason = excluded.get(l.position);
              const off = approved ? l.excluded : reason !== undefined;
              return (
                <tr key={l.position} className="border-t-[0.5px] border-hair align-top">
                  <td className="px-2 py-1">
                    <input
                      type="checkbox"
                      aria-label={`Include line ${String(l.position)}`}
                      checked={!off}
                      disabled={approved}
                      onChange={(e) => {
                        const next = new Map(excluded);
                        if (e.target.checked) next.delete(l.position);
                        else next.set(l.position, "");
                        setExcluded(next);
                      }}
                    />
                  </td>
                  <td className="px-2 py-1 tabular-nums text-ink-2">{l.posted_on ?? "—"}</td>
                  <td className="px-2 py-1">
                    {l.page != null && l.box != null ? (
                      <SourceHover
                        engagementId={ids.engagementId}
                        source={{
                          versionId: ids.versionId,
                          itemId: ids.itemId,
                          page: l.page,
                          box: l.box,
                        }}
                        label={`line ${String(l.position)}`}
                        className={off ? "text-ink-4 line-through" : ""}
                      >
                        {l.description}
                      </SourceHover>
                    ) : (
                      <span className={off ? "text-ink-4 line-through" : ""}>{l.description}</span>
                    )}
                    {approved && l.exclusion_reason != null && (
                      <span className="block text-[11.5px] text-ink-3">{l.exclusion_reason}</span>
                    )}
                    {!approved && reason !== undefined && (
                      <input
                        aria-label={`Why line ${String(l.position)} is excluded`}
                        value={reason}
                        maxLength={200}
                        placeholder="Why it's excluded"
                        onChange={(e) => {
                          setExcluded(new Map(excluded).set(l.position, e.target.value));
                        }}
                        className="mt-1 block h-[26px] w-full rounded-tile border-0 bg-nested px-2 inset-shadow-hair"
                      />
                    )}
                  </td>
                  <td
                    className={`px-2 py-1 text-right tabular-nums ${off ? "text-ink-4 line-through" : ""}`}
                  >
                    {amount(l.amount)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {approved ? (
        <p className="text-ink-2">
          {`Approved by ${s.approved_by_name ?? ""} on ${(s.approved_at ?? "").slice(0, 10)} · ${String(included)} transactions`}
        </p>
      ) : (
        canApprove && (
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              disabled={!rec.reconciled || body === null || preview.isPending || approve.isPending}
              onClick={() => {
                if (body !== null) approve.mutate({ ...path, body });
              }}
            >
              Approve transactions
            </Button>
            {!rec.reconciled && (
              <span className="text-ink-3">Approval needs the statement to reconcile.</span>
            )}
          </div>
        )
      )}
    </div>
  );
}
