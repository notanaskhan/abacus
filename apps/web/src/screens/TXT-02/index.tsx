// TXT-02 · Review › Trust Calculation (T-07-T17; SPEC-656 AC-6.1 to AC-7.2; handoff TXT-02 A–E,
// composed f1). T6 WorkbookLayout with the calc-tree grammar: the tally strip (every figure with
// its derivation, from the read model), the header with Calculation · By character, Open in Excel
// and Sign off… (Re-approve… on a changed version), then the tree: rails per level, chevrons that
// open in 340 ms (height) and 220 ms (opacity), muted DNI row, the full-bleed lavender row, the box
// label column, clause chips to TXT-01 (?clause=), Changed micro-pills with struck priors, and the
// by-character table. The browser never sums; no "$" renders in the tree.
import type { FiduciaryComputationOut, FiduciaryTreeNodeOut } from "@abacus/api-client";
import { fiduciaryComputationOptions } from "@abacus/api-client/query";
import { Button, EmptyState, ErrorState, Icon, Skeleton } from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { to } from "../../routes/to";
import { type JSX, useState } from "react";
import { COPY, amountWords } from "./copy";

export interface TXT02Props {
  returnId: string;
  /** Start collapsed to the four top rows (b) or on the character table (c). */
  initial?: { collapsed?: boolean; view?: "tree" | "character" };
  onClause?: (clause: string) => void;
  onRow?: (key: string) => void;
  onSignOff?: () => void;
  onOpenInExcel?: () => void;
}

/** A clause chip's target: TXT-01 with the clause lit (the handoff's TXT-02 → TXT-01 link). */
export function instrumentLink(returnId: string): ReturnType<typeof to.TXT01> {
  return to.TXT01({ returnId });
}

function childrenOf(nodes: readonly FiduciaryTreeNodeOut[], parent: string | null): FiduciaryTreeNodeOut[] {
  return nodes.filter((n) => (n.parent_key ?? null) === parent);
}

/** The four top rows of state b. */
export function topRows(nodes: readonly FiduciaryTreeNodeOut[]): FiduciaryTreeNodeOut[] {
  return childrenOf(nodes, null);
}

function Row({
  node,
  nodes,
  open,
  toggle,
  props,
}: {
  node: FiduciaryTreeNodeOut;
  nodes: readonly FiduciaryTreeNodeOut[];
  open: ReadonlySet<string>;
  toggle: (key: string) => void;
  props: TXT02Props;
}): JSX.Element {
  const kids = childrenOf(nodes, node.key);
  const isOpen = open.has(node.key);
  const muted = node.key === "dni";
  return (
    <li data-row={node.key} data-level={node.level}>
      <div
        data-highlighted={node.highlighted ? "true" : undefined}
        style={{ paddingLeft: 21 + node.level * 31 }}
        className={`flex min-h-[34px] items-center gap-[8px] pr-[16px] text-[13.5px] ${
          node.highlighted ? "-ml-[12px] bg-match-soft pl-[33px]" : ""
        } ${muted ? "text-ink-2" : ""}`}
      >
        {kids.length > 0 ? (
          <button
            type="button"
            aria-expanded={isOpen}
            aria-label={node.label}
            onClick={() => toggle(node.key)}
            className="flex size-[16px] items-center justify-center"
          >
            <Icon
              name="chevron-right"
              size={12}
              className={`text-ink-3 transition-transform duration-[340ms] ${isOpen ? "rotate-90" : ""}`}
            />
          </button>
        ) : (
          <span className="size-[16px]" />
        )}
        <button type="button" onClick={() => props.onRow?.(node.key)} className="min-w-0 flex-1 text-left">
          {node.label}
        </button>
        {node.changed ? (
          <span data-changed className="rounded-pill bg-amber-tint px-[6px] text-[10.5px] text-amber-ink">
            {COPY.changed}
          </span>
        ) : null}
        {node.box_label ? <span className="w-[63px] text-right text-[12px] text-ink-3">{node.box_label}</span> : null}
        <span className="w-[140px] text-right tabular-nums">
          {node.changed && node.prior_value !== null && node.prior_value !== undefined ? (
            <s data-prior className="mr-[8px] text-ink-4">
              {amountWords(node.prior_value)}
            </s>
          ) : null}
          {amountWords(node.value)}
        </span>
        <span className="flex w-[60px] gap-[4px]">
          {(node.clause_labels ?? []).map((c) => (
            <button
              key={c}
              type="button"
              data-clause={c}
              onClick={() => props.onClause?.(c)}
              className="h-[19px] rounded-pill bg-chip px-[6px] text-[10.5px] font-medium hover:text-purple"
            >
              {c}
            </button>
          ))}
        </span>
      </div>
      {kids.length > 0 ? (
        <ul
          className={`overflow-hidden border-l-[1px] border-hair transition-[opacity,max-height] duration-[220ms] ${
            isOpen ? "max-h-[4000px] opacity-100" : "max-h-0 opacity-0"
          }`}
          style={{ marginLeft: 29 + node.level * 31 }}
        >
          {kids.map((k) => (
            <Row key={k.key} node={k} nodes={nodes} open={open} toggle={toggle} props={props} />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function Tally({ data }: { data: FiduciaryComputationOut }): JSX.Element {
  return (
    <div data-kit="TallyStrip" className="flex h-[52px] items-center gap-[20px] px-[16px] hairline-b">
      {data.tallies.map((t) => (
        <span key={t.key} data-tally={t.key} className="flex flex-col">
          <span className="text-[10.5px] uppercase tracking-wide text-ink-3">{t.label}</span>
          <span className="text-[14px] tabular-nums">
            {t.state === "tie" ? <span className="rounded-pill bg-green-tint px-[6px] text-[11.5px]">tie</span> : amountWords(t.value)}
          </span>
        </span>
      ))}
      {data.signed_by_initials && !data.sign_off_stale ? (
        <span data-reviewed className="ml-auto rounded-pill bg-green-tint px-[8px] text-[12px]">
          {COPY.reviewed(data.signed_by_initials)}
        </span>
      ) : null}
    </div>
  );
}

export function TXT02(props: TXT02Props): JSX.Element {
  const [view, setView] = useState<"tree" | "character">(props.initial?.view ?? "tree");
  const query = useQuery({
    ...fiduciaryComputationOptions({ path: { return_id: props.returnId }, query: { view } }),
    retry: false,
  });
  const nodes = query.data?.nodes ?? [];
  const [open, setOpen] = useState<Set<string> | null>(null);
  const opened =
    open ?? new Set(props.initial?.collapsed === true ? [] : nodes.filter((n) => n.key !== "theo_k1").map((n) => n.key));
  const toggle = (key: string): void => {
    const next = new Set(opened);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setOpen(next);
  };
  if (query.isPending) {
    return (
      <div data-screen="TXT-02" data-state="loading" className="flex flex-1 items-center justify-center">
        <Skeleton className="h-[9px] w-[320px]" />
      </div>
    );
  }
  if (query.isError) {
    const status = (query.error as { status?: number } | null)?.status;
    const code = (query.error as { code?: string; detail?: { code?: string } } | null);
    const waiting = status === 409 || code?.code === "interpretation_not_approved";
    return waiting ? (
      <div data-screen="TXT-02" data-state="f1" className="flex flex-1 flex-col">
        <div className="flex h-[52px] items-center gap-[20px] px-[16px] text-ink-4 hairline-b">— · — · —</div>
        <EmptyState icon="scale" title={COPY.waiting} />
      </div>
    ) : (
      <div data-screen="TXT-02" data-state="error" className="flex flex-1 items-center justify-center">
        <ErrorState title={COPY.error} />
      </div>
    );
  }
  const data = query.data;
  return (
    <div data-screen="TXT-02" data-version={data.version_no} className="flex min-h-0 flex-1 flex-col">
      <Tally data={data} />
      <section className="m-[10px] flex min-h-0 flex-1 flex-col rounded-pane bg-card shadow-e2">
        <header className="flex h-[46px] items-center gap-[10px] px-[14px] hairline-b">
          <span className="flex-1 text-[14px] font-medium">{COPY.header}</span>
          <span role="radiogroup" aria-label={COPY.calculation} className="flex rounded-pill bg-nested p-[2px] text-[12.5px]">
            {(["tree", "character"] as const).map((v) => (
              <button
                key={v}
                type="button"
                role="radio"
                aria-checked={view === v}
                onClick={() => setView(v)}
                className={`rounded-pill px-[10px] py-[2px] ${view === v ? "bg-card font-medium shadow-e1" : ""}`}
              >
                {v === "tree" ? COPY.calculation : COPY.byCharacter}
              </button>
            ))}
          </span>
          <Button variant="ghost" size="sm" onClick={props.onOpenInExcel}>
            {COPY.openInExcel}
          </Button>
          <Button variant="secondary" size="sm" onClick={props.onSignOff}>
            {data.sign_off_stale ? COPY.reapprove : COPY.signOff}
          </Button>
        </header>
        {data.banner ? (
          <p data-banner className="bg-amber-tint px-[14px] py-[8px] text-[12.5px] text-amber-ink">
            {data.banner}
          </p>
        ) : null}
        <div className="min-h-0 flex-1 overflow-y-auto py-[6px]">
          {view === "tree" ? (
            <ul aria-label={COPY.header}>
              {topRows(nodes).map((n) => (
                <Row key={n.key} node={n} nodes={nodes} open={opened} toggle={toggle} props={props} />
              ))}
            </ul>
          ) : (
            <table data-by-character className="mx-[16px] w-[calc(100%-32px)] text-[13px] tabular-nums">
              <thead>
                <tr className="text-ink-3">
                  <th className="py-[6px] text-left font-normal">{COPY.columns.character}</th>
                  <th className="text-right font-normal">{COPY.columns.dni}</th>
                  {(data.by_character[0]?.by_party ?? []).map((p) => (
                    <th key={p.party} className="text-right font-normal">
                      {p.party.split(" ")[0]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.by_character.map((r) => (
                  <tr key={r.kind} data-character={r.kind} className={`hairline-t ${r.kind === "total" ? "font-medium" : ""}`}>
                    <td className="py-[6px]">{COPY.character[r.kind]}</td>
                    <td className="text-right">{amountWords(r.total)}</td>
                    {r.by_party.map((p) => (
                      <td key={p.party} className="text-right">
                        {amountWords(p.amount)}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {view === "tree"
            ? data.notes.map((n) => (
                <p key={n} className="px-[21px] pt-[6px] text-[11.5px] text-ink-3">
                  {n}
                </p>
              ))
            : null}
        </div>
      </section>
    </div>
  );
}
