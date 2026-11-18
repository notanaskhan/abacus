// CLS-04 · Close › Accounts (C-01-T37; handoff CLS-04 a, a2, b, d, e, f and the composed c′;
// SPEC-655 F5): the account tree beside the selected account's Detail or Workpaper, T2 variant
// inside the close shell's Accounts tab. Every figure is code's (`GET /v1/closes/{id}/accounts`,
// `…/workpaper`, `…/register`); the browser formats and never computes a balance. Accrued never
// posts: there is no Post AJE control (DV-1); an approved entry is recorded in QuickBooks by a
// person and the next sync reads it (c′). Bank and card leaves open their reconciliation (CLS-05).
import type { AccountNodeOut, CloseRegisterOut, CloseWorkpaperOut } from "@abacus/api-client";
import {
  closeAccountsOptions,
  closeRegisterOptions,
  closeSummaryOptions,
  closeWorkpaperOptions,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  DASH,
  Drawer,
  Segmented,
  Skeleton,
  TallyPill,
  amount,
  cn,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { closeReadFrame } from "../../domain/closes";
import { COPY as C } from "./copy";
import { useNavigate } from "@tanstack/react-router";
import { to } from "../../routes/to";

export interface CLS04Props {
  closeId: string;
  initial?: { account?: string; view?: "detail" | "workpaper"; arrangement?: boolean };
  /** A bank or card leaf: CLS-05 on that account. */
  onReconciliation?: (accountRef: string) => void;
  /** The policy citation: SHL-08 on the declarations page. */
  onCite?: (citationId: string) => void;
  /** Category ⇕ in Detail: the recategorization proposal (SHL-10). */
  onRecategorize?: (lineRef: string) => void;
  /** "off" to its review issue (CLS-06). */
  onIssue?: (issueId: string) => void;
}

const BANKISH = new Set(["Bank", "Credit Card"]);
const TH = "h-[34px] bg-nested px-[10px] text-[12.5px] font-normal text-ink-2";
const TD = "h-[37px] px-[10px] text-[13px]";

function money(v: string): JSX.Element {
  return <Amount value={v} style="money" zero="explicit" />;
}

function bankLeaves(nodes: readonly AccountNodeOut[], under = false): Set<string> {
  const out = new Set<string>();
  for (const n of nodes) {
    const bank = under || (n.kind === "account_type" && BANKISH.has(n.name));
    if (n.kind === "account" && bank && n.account_external_id) out.add(n.account_external_id);
    for (const ref of bankLeaves(n.children ?? [], bank)) out.add(ref);
  }
  return out;
}

function TreeRows({
  nodes,
  depth,
  selected,
  onSelect,
  collapsed,
  onToggle,
}: {
  nodes: readonly AccountNodeOut[];
  depth: number;
  selected: string;
  onSelect: (ref: string) => void;
  collapsed: ReadonlySet<string>;
  onToggle: (id: string) => void;
}): JSX.Element {
  return (
    <>
      {nodes.map((n) => {
        const leaf = n.kind === "account";
        const ref = n.account_external_id ?? "";
        const open = !collapsed.has(n.node_id);
        return (
          <div key={n.node_id} role="none">
            <div
              role="treeitem"
              aria-level={depth + 1}
              aria-expanded={leaf ? undefined : open}
              aria-selected={leaf ? selected === ref : undefined}
              data-node={n.name}
              data-kind={n.kind}
              data-tally={n.tally ?? undefined}
              className={cn(
                "flex h-[37px] items-center gap-[6px] pr-[12px] text-[13.5px] hairline-b",
                leaf && selected === ref && "bg-selected",
              )}
              style={{ paddingLeft: `${String(12 + depth * 18)}px` }}
            >
              {leaf ? (
                <button
                  type="button"
                  className="flex-1 truncate text-left"
                  onClick={() => {
                    onSelect(ref);
                  }}
                >
                  {n.name}
                  {n.mask ? ` ••${n.mask}` : ""}
                </button>
              ) : (
                <button
                  type="button"
                  className={cn(
                    "flex-1 truncate text-left",
                    n.kind === "classification" && "font-medium",
                  )}
                  onClick={() => {
                    onToggle(n.node_id);
                  }}
                >
                  {open ? "⌄ " : "› "}
                  {n.name}
                </button>
              )}
              <span className="tabular-nums" data-balance="">
                {money(n.balance)}
              </span>
            </div>
            {!leaf && open && (
              <TreeRows
                nodes={n.children ?? []}
                depth={depth + 1}
                selected={selected}
                onSelect={onSelect}
                collapsed={collapsed}
                onToggle={onToggle}
              />
            )}
          </div>
        );
      })}
    </>
  );
}

function Band({ title, children }: { title: string; children?: React.ReactNode }): JSX.Element {
  return (
    <div className="flex h-[34px] items-center justify-between bg-nested px-[14px] text-[14px] font-medium hairline-t">
      <span>{title}</span>
      {children}
    </div>
  );
}

function TieMark({ wp, current }: { wp: CloseWorkpaperOut; current: boolean }): JSX.Element {
  if (!current) return <TallyPill code="tie" />;
  if (wp.tally === "off")
    return <TallyPill code="off" vars={{ amount: amount(wp.off_by ?? "0", "cents").text }} />;
  if (wp.tally === "recorded" || wp.tally === "tie") return <TallyPill code="tie" />;
  return <TallyPill code="ties_once_posted" />;
}

function Workpaper({
  wp,
  period,
  onCite,
  onAdd,
  onIssue,
}: {
  wp: CloseWorkpaperOut;
  period: string;
  onCite?: ((id: string) => void) | undefined;
  onAdd: () => void;
  onIssue?: ((id: string) => void) | undefined;
}): JSX.Element {
  const current = wp.lines.find((l) => l.period === period);
  const ajeAmount = current === undefined ? "0" : current.aje.replace(/^-/u, "");
  const arrangement = wp.arrangements[0];
  return (
    <div data-cls04="workpaper" data-tally={wp.tally}>
      <Band title={C.bands.arrangements}>
        <Button variant="secondary" size="xs" onClick={onAdd}>
          {C.addArrangement}
        </Button>
      </Band>
      <table className="w-full border-collapse">
        <thead>
          <tr>
            {C.arrangementColumns.map((h) => (
              <th key={h} scope="col" className={cn(TH, "text-left")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {wp.arrangements.map((a) => (
            <tr key={a.arrangement_id} className="hairline-b">
              <td className={TD}>
                {a.description}{" "}
                {a.source_citation_id && (
                  <button
                    type="button"
                    data-cite=""
                    className="h-[17px] rounded-full bg-card px-[6px] text-[10.5px] font-medium shadow-e1"
                    onClick={() => onCite?.(a.source_citation_id ?? "")}
                  >
                    {C.cite}
                  </button>
                )}
              </td>
              <td className={TD}>{a.expense_account_ref}</td>
              <td className={cn(TD, "text-right")}>{amount(a.scheduled_total, "dollars").text}</td>
              <td className={cn(TD, "text-right")}>
                {amount("0", "dollars", { zero: "explicit" }).text}
              </td>
              <td className={TD}>{a.start_on}</td>
              <td className={TD}>{C.frequency[a.frequency]}</td>
              <td className={TD}>{a.start_on}</td>
              <td className={TD}>{a.finish_on}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <Band title={C.bands.activity} />
      <table className="w-full border-collapse" data-cls04="activity">
        <thead>
          <tr>
            <th scope="col" className={TH} />
            {wp.lines.map((l) => (
              <th key={l.period} scope="col" className={cn(TH, "text-right")}>
                {l.period}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {(
            [
              [
                C.activityRows.inflows,
                (l: (typeof wp.lines)[number]) =>
                  amount(l.inflows, "dollars", { zero: "explicit" }).text,
              ],
              [
                C.activityRows.aje,
                (l: (typeof wp.lines)[number]) => amount(l.aje, "dollars").text,
              ],
              [
                C.activityRows.ending,
                (l: (typeof wp.lines)[number]) => amount(l.ending_balance, "dollars").text,
              ],
            ] as const
          ).map(([label, cell]) => (
            <tr key={label} className="hairline-b">
              <th scope="row" className={cn(TD, "text-left font-normal text-ink-2")}>
                {label}
              </th>
              {wp.lines.map((l) => (
                <td key={l.period} className={cn(TD, "text-right tabular-nums")}>
                  {cell(l)}
                </td>
              ))}
            </tr>
          ))}
          <tr className="hairline-b">
            <th scope="row" className={cn(TD, "text-left font-normal text-ink-2")}>
              {C.activityRows.gl}
            </th>
            {wp.lines.map((l) => (
              <td key={l.period} className={cn(TD, "text-right tabular-nums")} data-gl={l.period}>
                {l.period < period
                  ? amount(l.ending_balance, "dollars").text
                  : l.period === period
                    ? amount(wp.gl_balance, "dollars").text
                    : DASH}
              </td>
            ))}
          </tr>
          <tr className="hairline-b">
            <th scope="row" className={cn(TD, "text-left font-normal text-ink-2")}>
              {C.activityRows.tie}
            </th>
            {wp.lines.map((l) => (
              <td key={l.period} className={cn(TD, "text-right")} data-tie={l.period}>
                {l.period <= period ? <TieMark wp={wp} current={l.period === period} /> : DASH}
              </td>
            ))}
          </tr>
        </tbody>
      </table>
      {wp.tally === "off" && wp.review_issue_id && (
        <p className="px-[14px] py-[6px] text-[12.5px] text-red-ink">
          <button
            type="button"
            className="underline"
            onClick={() => onIssue?.(wp.review_issue_id ?? "")}
          >
            {C.offIssue}
          </button>
        </p>
      )}
      <Band title={C.bands.aje}>
        <span
          data-cls04="aje-state"
          className={cn("text-[11.5px]", wp.approval ? "text-green-ink" : "text-amber-ink")}
        >
          {wp.recording
            ? C.recorded(wp.recording.entry_number, "10:20")
            : (wp.approval ?? (wp.pending_entry_number ? C.pending(wp.pending_entry_number) : ""))}
        </span>
      </Band>
      {arrangement !== undefined && (
        <table className="w-full border-collapse" data-cls04="aje">
          <thead>
            <tr>
              {C.ajeColumns.map((h, i) => (
                <th key={h} scope="col" className={cn(TH, i === 0 ? "text-left" : "text-right")}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr className="hairline-b">
              <td className={TD}>Expense:{arrangement.expense_account_ref}</td>
              <td className={cn(TD, "text-right")}>{money(ajeAmount)}</td>
              <td className={cn(TD, "text-right")}>{DASH}</td>
            </tr>
            <tr className="hairline-b">
              <td className={TD}>Asset:{wp.account_name}</td>
              <td className={cn(TD, "text-right")}>{DASH}</td>
              <td className={cn(TD, "text-right")}>{money(ajeAmount)}</td>
            </tr>
            <tr className="bg-nested font-medium">
              <td className={TD} />
              <td className={cn(TD, "text-right")}>{money(ajeAmount)}</td>
              <td className={cn(TD, "text-right")}>{money(ajeAmount)}</td>
            </tr>
          </tbody>
        </table>
      )}
      {wp.approval && (
        <p
          data-cls04="read-only"
          className="flex items-center gap-[8px] px-[14px] py-[6px] text-[12.5px] text-ink-2"
        >
          {C.readOnlyNote}
          <Button variant="ghost" size="xs">
            {C.exportEntry}
          </Button>
        </p>
      )}
      {wp.note && <p className="px-[14px] py-[6px] text-[11.5px] text-ink-3">{wp.note}</p>}
    </div>
  );
}

function Register({
  register,
  onRecategorize,
  balance,
}: {
  register: CloseRegisterOut;
  onRecategorize?: ((ref: string) => void) | undefined;
  balance: string;
}): JSX.Element {
  return (
    <table className="w-full border-collapse" data-cls04="register">
      <thead>
        <tr>
          {C.registerColumns.map((h, i) => (
            <th key={h} scope="col" className={cn(TH, i === 5 ? "text-right" : "text-left")}>
              {h === "Category" ? C.recategorize : h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {register.items.map((r) => (
          <tr
            key={r.line_ref}
            data-register-line={r.line_ref}
            className="h-[30px] hairline-b text-[13px]"
          >
            <td className="px-[10px]">{r.txn_date}</td>
            <td className="px-[10px]">{r.txn_type ?? DASH}</td>
            <td className="px-[10px]">
              <button type="button" onClick={() => onRecategorize?.(r.line_ref)}>
                {r.category ?? DASH}
              </button>
            </td>
            <td className="px-[10px]">{r.payee ?? DASH}</td>
            <td className="px-[10px]">{r.memo ?? DASH}</td>
            <td className="px-[10px] text-right">{money(r.amount)}</td>
          </tr>
        ))}
        <tr className="h-[30px] font-medium">
          <td className="px-[10px]" colSpan={5}>
            {C.registerBalance}
          </td>
          <td className="px-[10px] text-right">{money(balance)}</td>
        </tr>
      </tbody>
    </table>
  );
}

function ArrangementDrawer({
  open,
  onOpenChange,
  held,
}: {
  open: boolean;
  onOpenChange: (o: boolean) => void;
  held: boolean;
}) {
  const D = C.drawer;
  const field =
    "h-[34px] w-full rounded-input bg-card px-[8px] text-cell inset-ring-[0.5px] inset-ring-stroke";
  const fields = [D.description, D.expense, D.total, D.frequency, D.start, D.finish, D.source];
  return (
    <Drawer
      open={open}
      onOpenChange={onOpenChange}
      title={D.title}
      width={480}
      {...(held ? { forceState: "open" as const } : {})}
      footer={<Button variant="primary">{D.save}</Button>}
    >
      <form
        data-cls04="arrangement"
        className="flex flex-col gap-[10px] p-[16px]"
        onSubmit={(e) => {
          e.preventDefault();
        }}
      >
        {fields.map((label) => (
          <label key={label} className="flex flex-col gap-[4px] text-[12.5px] text-ink-2">
            {label}
            <input className={field} />
          </label>
        ))}
      </form>
    </Drawer>
  );
}

export function CLS04({
  closeId,
  initial = {},
  onReconciliation: reconciliationProp,
  onCite,
  onRecategorize,
  onIssue: issueProp,
}: CLS04Props): JSX.Element {
  // C-01-T43: the designed links (a bank account to CLS-05, a review issue to CLS-06) are the
  // screen's own; a caller may still pass its own handler (tests, the board).
  const navigate = useNavigate();
  const onReconciliation =
    reconciliationProp ??
    ((accountRef: string): void => {
      void navigate(to.CLS05({ closeId, accountRef }));
    });
  const onIssue =
    issueProp ??
    ((): void => {
      void navigate(to.CLS06({ closeId }));
    });
  const [selected, setSelected] = useState(initial.account ?? "prepaid-insurance");
  const [view, setView] = useState<"detail" | "workpaper">(initial.view ?? "workpaper");
  const [collapsed, setCollapsed] = useState<ReadonlySet<string>>(new Set());
  const [adding, setAdding] = useState(initial.arrangement === true);
  const tree = useQuery(closeAccountsOptions({ path: { close_id: closeId } }));
  const summary = useQuery(closeSummaryOptions({ path: { close_id: closeId } }));
  const banks = bankLeaves(tree.data?.nodes ?? []);
  const isBank = banks.has(selected);
  const path = { close_id: closeId, account_ref: selected };
  const workpaper = useQuery({
    ...closeWorkpaperOptions({ path }),
    enabled: !isBank && view === "workpaper",
  });
  const register = useQuery({
    ...closeRegisterOptions({ path }),
    enabled: !isBank && view === "detail",
  });
  const leafName = (function find(nodes: readonly AccountNodeOut[]): AccountNodeOut | undefined {
    for (const n of nodes) {
      if (n.kind === "account" && n.account_external_id === selected) return n;
      const hit = find(n.children ?? []);
      if (hit) return hit;
    }
    return undefined;
  })(tree.data?.nodes ?? []);
  // C-01-T43: a refused or failed account-tree read is the C-20 frame, with no account data.
  const frame = closeReadFrame("CLS-04", tree);
  if (frame !== null) return frame;
  return (
    <div
      data-screen="CLS-04"
      data-account={selected}
      className="flex gap-[10px] bg-shell p-[12px]"
    >
      <section
        aria-label={C.tree}
        className="flex w-[420px] flex-col rounded-pane bg-card shadow-e1"
      >
        <header className="relative flex h-[46px] items-center justify-center px-[12px]">
          <Button
            variant="secondary"
            size="xs"
            className="absolute left-[12px]"
            aria-label={C.filter}
          >
            ⚙
          </Button>
          <h2 className="text-[14.5px] font-medium">{C.tree}</h2>
        </header>
        <div className="flex h-[31px] items-center justify-between bg-nested px-[12px] text-[13px] text-ink-2">
          <span>{C.columns.account}</span>
          <span>{C.columns.balance}</span>
        </div>
        {tree.isPending ? (
          <Skeleton className="m-[12px] h-[200px]" />
        ) : (
          <div role="tree" aria-label={C.tree} data-cls04="tree">
            <TreeRows
              nodes={tree.data?.nodes ?? []}
              depth={0}
              selected={selected}
              onSelect={(ref) => {
                setSelected(ref);
                if (banks.has(ref)) onReconciliation(ref);
              }}
              collapsed={collapsed}
              onToggle={(id) => {
                setCollapsed((c) => {
                  const next = new Set(c);
                  if (next.has(id)) next.delete(id);
                  else next.add(id);
                  return next;
                });
              }}
            />
          </div>
        )}
      </section>
      <section
        aria-label={leafName?.name ?? ""}
        className="flex w-[946px] flex-col rounded-pane bg-card shadow-e1"
      >
        <header className="relative flex h-[46px] items-center justify-center">
          <h2 className="text-[14.5px] font-medium">{leafName?.name ?? ""}</h2>
          <Button variant="ghost" className="absolute right-[12px]">
            {C.excel}
          </Button>
        </header>
        <div className="flex h-[54px] items-center justify-center">
          <Segmented
            size="small"
            label={C.viewLabel}
            options={[C.views.detail, isBank ? C.views.reconciliation : C.views.workpaper]}
            active={
              view === "detail"
                ? C.views.detail
                : isBank
                  ? C.views.reconciliation
                  : C.views.workpaper
            }
            onChange={(label) => {
              setView(label === C.views.detail ? "detail" : "workpaper");
            }}
          />
        </div>
        {isBank ? (
          <p
            data-cls04="bank"
            className="flex items-center gap-[8px] px-[14px] py-[12px] text-[12.5px] text-ink-2"
          >
            {C.bankNote}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                onReconciliation(selected);
              }}
            >
              {C.openReconciliation}
            </Button>
          </p>
        ) : view === "workpaper" ? (
          workpaper.data && summary.data ? (
            <Workpaper
              wp={workpaper.data}
              period={summary.data.period}
              onCite={onCite}
              onAdd={() => {
                setAdding(true);
              }}
              onIssue={onIssue}
            />
          ) : (
            <Skeleton className="m-[12px] h-[240px]" />
          )
        ) : register.data ? (
          <Register
            register={register.data}
            onRecategorize={onRecategorize}
            balance={leafName?.balance ?? "0"}
          />
        ) : (
          <Skeleton className="m-[12px] h-[240px]" />
        )}
      </section>
      <ArrangementDrawer
        open={adding}
        onOpenChange={setAdding}
        held={initial.arrangement === true}
      />
    </div>
  );
}
