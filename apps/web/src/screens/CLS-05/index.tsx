// CLS-05 · Close › Reconciliation (C-01-T38; handoff CLS-05 a, a2, a3, b, c, d, e, f, g;
// SPEC-655 F6): the two-sided rec sheet beside the bank statement, T3 two-pane inside the close
// shell's Accounts tab. Every figure is code's (`GET /v1/closes/{id}/reconciliations/{ref}`); the
// browser formats and never computes. Hovering or focusing a reconciling line lights its statement
// line and back (one match id per pair). The agent drafts an entry; only a person's Propose in the
// drawer proposes it (ADR-005). "Reconciled ✓" shows only after the L1 sign-off (`signed_off_by`).
// The entry is recorded in QuickBooks by a person, never posted (DV-2).
import type {
  CloseReconciliationOut,
  CloseStatementLineOut,
  ReconcilingItemOut,
} from "@abacus/api-client";
import { closeReconciliationOptions, closeRegisterOptions } from "@abacus/api-client/query";
import {
  AgentText,
  Amount,
  Button,
  DASH,
  Dialog,
  Drawer,
  Pill,
  Picker,
  Segmented,
  Skeleton,
  TallyPill,
  amount,
  cn,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, type ReactNode, useState } from "react";
import { closeReadFrame } from "../../domain/closes";
import { AJE_06_DRAFT } from "../kit-close-data";
import { COPY as C } from "./copy";

export interface CLS05Props {
  closeId: string;
  accountRef: string;
  initial?: {
    account?: string;
    view?: "detail" | "reconciliation";
    propose?: boolean;
    signOff?: boolean;
    loadingPages?: boolean;
  };
  onAccount?: (ref: string) => void;
  /** The drawer's Propose: the only path to a proposed entry. */
  onPropose?: (itemId: string) => void;
  onIssue?: (issueId: string) => void;
  /** "Review required": SHL-10 on the proposal until CLS-07 lands (C-02). */
  onReview?: (proposalId: string) => void;
}

const ROW = "h-[30px] px-[10px] text-[12.5px]";

function money(v: string | null | undefined): JSX.Element {
  if (v === null || v === undefined) return <span className="text-ink-3">{DASH}</span>;
  return <Amount value={v} style="money" zero="explicit" />;
}

function matchOf(
  item: ReconcilingItemOut,
  lines: readonly CloseStatementLineOut[],
): string | null {
  if (item.region == null) return null;
  const hit = lines.find(
    (l) =>
      l.region.page_no === item.region?.page_no &&
      l.region.bbox.join() === item.region.bbox.join(),
  );
  return hit?.statement_line_id ?? null;
}

function itemLabel(i: ReconcilingItemOut): string {
  const date = amountDate(i.txn_date);
  return i.ref ? `${C.kind[i.kind]} ${i.ref} · ${date}` : `${C.kind[i.kind]} · ${date}`;
}

function amountDate(iso: string): string {
  const [y, m, d] = iso.split("-");
  const MONTHS = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${MONTHS[Number(m) - 1] ?? ""} ${String(Number(d))}, ${y ?? ""}`;
}

function Tally({ label, children }: { label: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[52px] min-w-[150px] flex-col justify-center rounded-[10px] bg-card px-[12px] shadow-e1">
      <span className="text-[9.5px] font-medium tracking-[0.07em] text-ink-3 uppercase">
        {label}
      </span>
      <span className="flex items-center gap-[6px] text-[15px] tabular-nums">{children}</span>
    </div>
  );
}

function RecSheet({
  rec,
  lit,
  onLight,
  onPropose,
  onIssue,
  onReview,
}: {
  rec: CloseReconciliationOut;
  lit: string | null;
  onLight: (id: string | null) => void;
  onPropose: (itemId: string) => void;
  onIssue?: ((id: string) => void) | undefined;
  onReview?: ((id: string) => void) | undefined;
}): JSX.Element {
  const signed = rec.signed_off_by != null;
  const open = rec.items.filter((i) => i.issue_id != null && i.resolution == null).length;
  const bank = rec.items.filter((i) => i.side === "bank");
  const book = rec.items.filter((i) => i.side === "book");
  const period = amountDate(rec.period_end);
  const line = (i: ReconcilingItemOut): JSX.Element => {
    const match = matchOf(i, rec.statement_lines);
    return (
      <tr
        key={i.item_id}
        tabIndex={0}
        data-item={i.item_id}
        data-match={match ?? undefined}
        data-lit={match !== null && lit === match ? "" : undefined}
        className={cn(
          "hairline-b outline-none",
          match !== null && lit === match && "bg-match-bg inset-ring-[1px] inset-ring-match-line",
        )}
        onMouseEnter={() => {
          onLight(match);
        }}
        onMouseLeave={() => {
          onLight(null);
        }}
        onFocus={() => {
          onLight(match);
        }}
        onBlur={() => {
          onLight(null);
        }}
      >
        <td className={ROW}>{itemLabel(i)}</td>
        <td className={cn(ROW, "text-right")}>{money(i.amount)}</td>
      </tr>
    );
  };
  return (
    <div className="flex flex-col gap-[12px] px-[12px] pb-[12px]">
      <div className="flex flex-wrap gap-[8px]" data-cls05="tallies">
        <Tally label={C.tally.bank}>{money(rec.balance_per_bank)}</Tally>
        <Tally label={C.tally.adjustedBank}>{money(rec.adjusted_bank)}</Tally>
        <Tally label={C.tally.adjustedBooks}>{money(rec.adjusted_book)}</Tally>
        <Tally label={C.tally.difference}>
          {signed && rec.tally === "reconciled" ? (
            <Pill variant="green" data-cls05="reconciled">
              {C.reconciled}
            </Pill>
          ) : (
            <>
              {money(rec.difference)}
              {rec.tally === "off" ? (
                <TallyPill
                  code="off"
                  vars={{ amount: amount(rec.difference ?? "0", "cents").text }}
                />
              ) : rec.tally === "tie" ? (
                <TallyPill code="tie" />
              ) : null}
            </>
          )}
        </Tally>
        <Tally label={C.tally.open}>
          {open > 0 ? <Pill variant="red-tint">{open}</Pill> : DASH}
        </Tally>
      </div>
      <div className="flex gap-[12px]">
        <table className="w-[420px] rounded-[12px] bg-card shadow-e1" data-cls05="bank-side">
          <caption className="h-[32px] text-left text-[13px] font-medium">{C.bankSide}</caption>
          <tbody>
            <tr className="hairline-b">
              <td className={ROW}>{C.balancePerBank(period)}</td>
              <td className={cn(ROW, "text-right")}>{money(rec.balance_per_bank)}</td>
            </tr>
            {bank.map(line)}
            <tr className="bg-nested font-medium">
              <td className={ROW}>{C.adjustedBank}</td>
              <td className={cn(ROW, "text-right")}>{money(rec.adjusted_bank)}</td>
            </tr>
          </tbody>
        </table>
        <table className="w-[420px] rounded-[12px] bg-card shadow-e1" data-cls05="book-side">
          <caption className="h-[32px] text-left text-[13px] font-medium">{C.bookSide}</caption>
          <tbody>
            <tr className="hairline-b">
              <td className={ROW}>{C.balancePerBooks(period)}</td>
              <td className={cn(ROW, "text-right")}>{money(rec.book_balance)}</td>
            </tr>
            {book.map(line)}
            <tr className="bg-nested font-medium">
              <td className={ROW}>{C.adjustedBook}</td>
              <td className={cn(ROW, "text-right")}>{money(rec.adjusted_book)}</td>
            </tr>
            <tr className="font-medium">
              <td className={ROW}>{C.differenceRow}</td>
              <td className={cn(ROW, "text-right")}>{money(rec.difference)}</td>
            </tr>
          </tbody>
        </table>
      </div>
      {signed && (
        <p className="text-[12.5px] text-ink-2" data-cls05="recorded">
          {C.recordedNote}
        </p>
      )}
      <table className="w-full rounded-[12px] bg-card shadow-e1" data-cls05="aging">
        <caption className="h-[32px] text-left text-[13px] font-medium">{C.aging}</caption>
        <thead>
          <tr>
            {C.agingColumns.map((h) => (
              <th
                key={h}
                scope="col"
                className={cn(ROW, "bg-nested text-left font-normal text-ink-2")}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rec.items.map((i) => (
            <tr key={i.item_id} className="hairline-b" data-aging={i.item_id}>
              <td className={ROW}>{itemLabel(i)}</td>
              <td className={ROW}>{C.side[i.side]}</td>
              <td className={ROW}>{amountDate(i.txn_date)}</td>
              <td className={cn(ROW, "tabular-nums")}>{i.days_at_period_end}</td>
              <td className={cn(ROW, "text-right")}>{money(i.amount)}</td>
              <td className={ROW}>
                <span className="flex items-center gap-[8px]">
                  {i.resolution === "carry_forward" ? (
                    <span className="text-ink-3">{C.carryForward}</span>
                  ) : (
                    <>
                      {i.stale === true && <Pill variant="red-tint">{C.stale}</Pill>}
                      {i.side === "book" &&
                        !signed &&
                        (i.proposed_entry_id ? (
                          <button
                            type="button"
                            className="text-[11.5px] text-amber-ink underline"
                            onClick={() => onReview?.(i.proposed_entry_id ?? "")}
                          >
                            {C.proposed}
                          </button>
                        ) : (
                          <Button
                            variant="secondary"
                            size="xs"
                            onClick={() => {
                              onPropose(i.item_id);
                            }}
                          >
                            {C.proposeAje}
                          </Button>
                        ))}
                      {i.issue_id && !signed && (
                        <button
                          type="button"
                          className="text-[12px] underline"
                          onClick={() => onIssue?.(i.issue_id ?? "")}
                        >
                          {C.issue}
                        </button>
                      )}
                    </>
                  )}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Viewer({
  rec,
  lit,
  onLight,
  loading,
}: {
  rec: CloseReconciliationOut | undefined;
  lit: string | null;
  onLight: (id: string | null) => void;
  loading: boolean;
}): JSX.Element {
  return (
    <section
      aria-label={C.viewerTitle}
      className="flex w-[490px] flex-col rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[46px] items-center justify-center text-[13px] font-medium">
        {rec?.statement_evidence_version_id ? C.viewerTitle : ""}
      </header>
      <div className="flex-1 bg-shell p-[12px]" data-cls05="viewer">
        {loading || rec === undefined ? (
          <Skeleton className="h-[560px]" />
        ) : rec.statement_evidence_version_id == null ? (
          <p data-cls05="requested" className="p-[24px] text-center text-[12.5px] text-ink-3">
            {C.requested(amountDate(rec.statement_requested_on ?? rec.period_end))}
          </p>
        ) : (
          <table className="w-full bg-card font-mono text-[10px]">
            <thead>
              <tr>
                {C.statementColumns.map((h) => (
                  <th key={h} scope="col" className="px-[6px] py-[4px] text-left">
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rec.statement_lines.map((l) => (
                <tr
                  key={l.statement_line_id}
                  tabIndex={0}
                  data-statement-line={l.statement_line_id}
                  data-lit={lit === l.statement_line_id ? "" : undefined}
                  className={cn(
                    "outline-none",
                    lit === l.statement_line_id &&
                      "bg-match-bg inset-ring-[1px] inset-ring-match-line",
                  )}
                  onMouseEnter={() => {
                    onLight(l.statement_line_id);
                  }}
                  onMouseLeave={() => {
                    onLight(null);
                  }}
                  onFocus={() => {
                    onLight(l.statement_line_id);
                  }}
                  onBlur={() => {
                    onLight(null);
                  }}
                >
                  <td className="px-[6px] py-[3px]">{l.txn_date.slice(5).replace("-", "/")}</td>
                  <td className="px-[6px] py-[3px]">
                    {l.description}
                    {!l.matched && <span className="ml-[6px] text-amber-ink">{C.unmatched}</span>}
                  </td>
                  <td className="px-[6px] py-[3px] text-right">{l.withdrawal ?? ""}</td>
                  <td className="px-[6px] py-[3px] text-right">{l.deposit ?? ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

export function CLS05({
  closeId,
  accountRef,
  initial = {},
  onAccount,
  onPropose,
  onIssue,
  onReview,
}: CLS05Props): JSX.Element {
  const [account, setAccount] = useState(initial.account ?? accountRef);
  const [view, setView] = useState(initial.view ?? "reconciliation");
  const [lit, setLit] = useState<string | null>(null);
  const [drawer, setDrawer] = useState<string | null>(initial.propose === true ? "refund" : null);
  const [blocked, setBlocked] = useState(initial.signOff === true);
  const path = { close_id: closeId, account_ref: account };
  const rec = useQuery(closeReconciliationOptions({ path }));
  const register = useQuery({ ...closeRegisterOptions({ path }), enabled: view === "detail" });
  const data = rec.data;
  const signed = data?.signed_off_by != null;
  const blockers = data?.sign_off_blockers ?? [];
  // C-01-T43: a refused or failed read is the C-20 frame, with no record data.
  const frame = closeReadFrame("CLS-05", rec);
  if (frame !== null) return frame;
  return (
    <div data-screen="CLS-05" data-account={account} className="flex gap-[10px] bg-shell p-[12px]">
      <section
        aria-label={data?.account_name ?? ""}
        className="flex w-[876px] flex-col rounded-pane bg-card shadow-e1"
      >
        <header className="flex h-[46px] items-center justify-between px-[12px]">
          <Picker
            label={C.account}
            options={C.accounts.map((a) => ({ value: a.ref, label: a.label }))}
            value={account}
            onChange={(v) => {
              setAccount(v);
              onAccount?.(v);
            }}
          />
          <h2 className="text-[14.5px] font-medium">{data?.account_name ?? ""}</h2>
          <span className="flex items-center gap-[8px]">
            {signed ? (
              <span data-cls05="signed" className="text-[12.5px] text-ink-3">
                ✓ RM · {C.signedBy(data.signed_off_by?.name ?? "", "2:31 PM")}
              </span>
            ) : (
              <Button
                variant="secondary"
                size="sm"
                onClick={() => {
                  setBlocked(true);
                }}
              >
                {C.signOff}
              </Button>
            )}
            <Button variant="ghost" size="sm">
              {C.excel}
            </Button>
          </span>
        </header>
        <div className="flex h-[54px] items-center justify-center">
          <Segmented
            size="small"
            label={C.viewLabel}
            options={[C.views.detail, C.views.reconciliation]}
            active={view === "detail" ? C.views.detail : C.views.reconciliation}
            onChange={(l) => {
              setView(l === C.views.detail ? "detail" : "reconciliation");
            }}
          />
        </div>
        {data === undefined ? (
          <Skeleton className="m-[12px] h-[400px]" />
        ) : view === "detail" ? (
          <table
            className="mx-[12px] mb-[12px] rounded-[12px] bg-card shadow-e1"
            data-cls05="register"
          >
            <tbody>
              {(register.data?.items ?? []).map((r) => (
                <tr key={r.line_ref} data-register-line={r.line_ref} className="hairline-b">
                  <td className={ROW}>{r.txn_date}</td>
                  <td className={ROW}>{r.txn_type ?? DASH}</td>
                  <td className={ROW}>{r.payee ?? DASH}</td>
                  <td className={ROW}>{r.memo ?? DASH}</td>
                  <td className={cn(ROW, "text-right")}>{money(r.amount)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <RecSheet
            rec={data}
            lit={lit}
            onLight={setLit}
            onPropose={(id) => {
              setDrawer(id);
            }}
            onIssue={onIssue}
            onReview={onReview}
          />
        )}
      </section>
      <Viewer rec={data} lit={lit} onLight={setLit} loading={initial.loadingPages === true} />
      <Drawer
        open={drawer !== null}
        onOpenChange={(o) => {
          if (!o) setDrawer(null);
        }}
        title={C.drawer.title}
        width={480}
        {...(initial.propose === true ? { forceState: "open" as const } : {})}
        footer={
          <Button
            variant="primary"
            onClick={() => {
              const item = data?.items.find((i) => i.side === "book");
              if (item) onPropose?.(item.item_id);
              setDrawer(null);
            }}
          >
            {C.drawer.propose}
          </Button>
        }
      >
        <dl data-cls05="propose" className="flex flex-col gap-[8px] p-[16px] text-[12.5px]">
          <dt className="text-ink-3">{C.drawer.draft}</dt>
          <dd>
            <AgentText text={AJE_06_DRAFT.entry} />
          </dd>
          <dt className="text-ink-3">{C.drawer.reasoning}</dt>
          <dd>
            <AgentText text={AJE_06_DRAFT.reasoning} />
          </dd>
          <dt className="text-ink-3">{C.drawer.citation}</dt>
          <dd>{AJE_06_DRAFT.citation}</dd>
        </dl>
      </Drawer>
      <Dialog
        open={blocked}
        onOpenChange={setBlocked}
        title={C.blocked.title}
        {...(initial.signOff === true ? { forceState: "open" as const } : {})}
      >
        <ul data-cls05="blockers" className="list-disc px-[24px] py-[12px] text-[12.5px]">
          {blockers.map((b) => (
            <li key={b}>
              {b in C.blocked.reasons ? C.blocked.reasons[b as keyof typeof C.blocked.reasons] : b}
            </li>
          ))}
        </ul>
      </Dialog>
    </div>
  );
}
