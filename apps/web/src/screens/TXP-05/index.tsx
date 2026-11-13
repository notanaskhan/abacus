// TXP-05 · Review › Schedule K (T-05-T43; docs/screens/TXP-05.md; handoff TXP-05 A–D): T6 inside
// the entity return's layout: the control bar (Federal · State K-1 amounts, the title, Allocation
// Structure… and Form preview), the tally strip and the Schedule K and K-1 matrix in the statement
// grammar (no "$"). Every figure, total and tie is the server's (`GET …/schedules/k`, its Form 8825
// breakdown, `…/capital-accounts` for Item L, `…/partners` for Item J and `…/allocation-structure`
// for the card); the screen formats and lays out and adds nothing (ADR-050). A2: line 2 opens the
// Form 8825 popover; A4: Item L off opens its popover to TXP-07 and TXP-10; A5: the partner menu
// opens TXP-12 (TAX-11 is planned); B: the state view; C: after the fix Item L ties; D: Building.
import type {
  WorkbookAllocationStructureOut,
  WorkbookBreakdownOut,
  WorkbookCapitalAccountsOut,
  WorkbookPartnerOut,
  WorkbookPartnersOut,
  WorkbookScheduleKLineOut,
  WorkbookScheduleKOut,
} from "@abacus/api-client";
import {
  Button,
  DataGrid,
  Menu,
  Pill,
  Popover,
  Segmented,
  SkeletonRows,
  Spinner,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  amount,
} from "@abacus/ui";
import type { JSX } from "react";
import { COPY, PARTNER_NOTE } from "./copy";

export type Txp05View = "federal" | "state";

const MONEY = { type: "num", format: "whole" } as const;
const DASH = { value: "—" };

function tagOf(p: WorkbookPartnerOut): "GP" | "LP" {
  return p.kind === "general" ? "GP" : "LP";
}

/** Line, Item, Schedule K, one column per partner (its name, GP or LP and any period), Σ, Tie. */
export function columns(partners: readonly WorkbookPartnerOut[]): TableColumn[] {
  return [
    { key: "line", header: COPY.columns.line, type: "text", width: 52, line: true },
    { key: "item", header: COPY.columns.item, type: "label", width: 300 },
    { key: "total", header: COPY.columns.total, ...MONEY, width: 116 },
    ...partners.map((p, i): TableColumn => ({
      key: `p${String(i)}`,
      header: [p.name, tagOf(p), PARTNER_NOTE[p.name]].filter(Boolean).join(" · "),
      ...MONEY,
      width: 112,
    })),
    { key: "sum", header: COPY.columns.sum, ...MONEY, width: 116 },
    { key: "tie", header: COPY.columns.tie, type: "chip", width: 60 },
  ];
}

function tieText(state: string, difference?: string | null): string {
  if (state === "tie") return "tie";
  if (state === "off") {
    const off = difference == null ? "" : ` ${amount(difference.replace("-", ""), "whole").text}`;
    return `off${off}`;
  }
  return COPY.pending;
}

function lineRow(
  l: WorkbookScheduleKLineOut,
  partners: readonly WorkbookPartnerOut[],
  label?: string,
): TableRow {
  const empty = l.by_partner.length === 0 && Number(l.total) === 0;
  const cells: Record<string, { value: string | null }> = {
    line: { value: l.line.startsWith("analysis") ? "1" : l.line },
    total: empty ? DASH : { value: l.total },
    sum: empty ? DASH : l.tie === "tie" ? { value: l.total } : DASH,
    tie: empty ? DASH : { value: tieText(l.tie) },
  };
  partners.forEach((p, i) => {
    const share = l.by_partner.find((c) => c.partner_id === p.id);
    cells[`p${String(i)}`] = empty ? DASH : { value: share?.amount ?? null };
  });
  return { id: `line:${l.line}`, label: label ?? l.label, cells };
}

function stmtRow(partners: readonly WorkbookPartnerOut[]): TableRow {
  const cells: Record<string, { value: string | null }> = {
    line: { value: "20c" },
    total: { value: COPY.stmt },
    sum: DASH,
    tie: DASH,
  };
  partners.forEach((_p, i) => {
    cells[`p${String(i)}`] = { value: COPY.stmt };
  });
  return { id: "line:20c", label: COPY.rows.qbi, cells };
}

function group(id: string, label: string): TableRow {
  return { id: `group:${id}`, kind: "group", label, cells: {} };
}

/** Item J: each partner's percentage in the first and the last period (the server's periods). */
function itemJ(p: WorkbookPartnersOut): TableRow {
  const first = p.periods[0]?.shares ?? {};
  const last = p.periods.at(-1)?.shares ?? {};
  const pct = (v: string | undefined) => `${String(Number(v ?? "0"))}%`;
  const cells: Record<string, { value: string | null }> = {
    line: { value: "J" },
    total: DASH,
    sum: { value: "100%" },
    tie: { value: "tie" },
  };
  p.partners.forEach((partner, i) => {
    cells[`p${String(i)}`] = { value: `${pct(first[partner.id])} → ${pct(last[partner.id])}` };
  });
  return { id: "item:J", label: COPY.rows.itemJ, cells };
}

/** Item L: the partners' ending capital (05) against Schedule L's (the M-2's line 9). */
function itemL(
  capital: WorkbookCapitalAccountsOut,
  partners: readonly WorkbookPartnerOut[],
): TableRow {
  const l = capital.item_l;
  const cells: Record<string, { value: string | null }> = {
    line: { value: "L" },
    total: {
      value:
        l === undefined || l === null
          ? null
          : `${amount(l.m2_ending, "whole").text} ${COPY.rows.schL}`,
    },
    sum: { value: l?.capital_ending ?? null },
    tie: { value: l === undefined || l === null ? COPY.pending : tieText(l.tie, l.difference) },
  };
  partners.forEach((p, i) => {
    const row = capital.rows.find((r) => r.partner_id === p.id);
    cells[`p${String(i)}`] = { value: row?.ending ?? null };
  });
  const ties = l?.tie === "tie";
  return { id: "item:L", label: ties ? COPY.rows.itemLFixed : COPY.rows.itemL, cells };
}

function itemK(partners: readonly WorkbookPartnerOut[]): TableRow {
  // Item K's §752 shares are TXP-08's basis reads (T-06); until then the row is Pending.
  const cells: Record<string, { value: string | null }> = {
    line: { value: "K" },
    total: { value: COPY.pending },
    sum: DASH,
    tie: { value: COPY.pending },
  };
  partners.forEach((_p, i) => {
    cells[`p${String(i)}`] = DASH;
  });
  return { id: "item:K", label: COPY.rows.itemK, cells };
}

const OTHER_FROM = 14;

/** The matrix in the server's line order, grouped as the handoff draws it. */
export function tableRows(
  k: WorkbookScheduleKOut,
  partners: WorkbookPartnersOut | undefined,
  capital: WorkbookCapitalAccountsOut | undefined,
): TableRow[] {
  const ps = partners?.partners ?? [];
  if (k.view === "state") {
    return [group("states", COPY.groups.states), ...k.lines.map((l) => lineRow(l, ps))];
  }
  const income = k.lines.filter((l) => Number.parseInt(l.line, 10) < OTHER_FROM);
  const other = k.lines.filter((l) => !(Number.parseInt(l.line, 10) < OTHER_FROM));
  const out: TableRow[] = [
    group("income", COPY.groups.income),
    ...income.map((l) => lineRow(l, ps)),
  ];
  out.push(group("other", COPY.groups.other));
  for (const l of other) {
    out.push(lineRow(l, ps));
    if (l.line === "20a") out.push(stmtRow(ps));
  }
  if (k.analysis !== undefined && k.analysis !== null) {
    out.push(group("analysis", COPY.groups.analysis), lineRow(k.analysis, ps, COPY.rows.analysis));
  }
  out.push(group("items", COPY.groups.items));
  if (partners !== undefined) out.push(itemJ(partners));
  out.push(itemK(ps));
  if (capital !== undefined) out.push(itemL(capital, ps));
  return out;
}

/** The strip: Σ K-1s per line, the K-1 count, Analysis of Net Income, Item K, Item L and the
 * allocation structure's kind and status (all the server's). */
export function tallyItems(
  k: WorkbookScheduleKOut | undefined,
  partners: WorkbookPartnersOut | undefined,
  capital: WorkbookCapitalAccountsOut | undefined,
  allocation: WorkbookAllocationStructureOut | undefined,
  building: boolean,
  onItemL?: () => void,
): TallyItem[] {
  const pending = { pill: { text: COPY.pending, variant: "neutral" as const } };
  if (building || k === undefined) {
    return [
      { label: COPY.cards.sumK1, ...pending },
      { label: COPY.cards.count, ...pending },
      { label: COPY.cards.analysis, ...pending },
      { label: COPY.cards.itemK, ...pending },
      { label: COPY.cards.itemL, ...pending },
      { label: COPY.cards.allocation, ...pending },
    ];
  }
  const allTie = k.lines.every((l) => l.tie === "tie");
  const l = capital?.item_l;
  const itemLCard: TallyItem =
    l === undefined || l === null
      ? { label: COPY.cards.itemL, ...pending }
      : l.tie === "tie"
        ? { label: COPY.cards.itemL, tally: "tie" }
        : {
            label: COPY.cards.itemL,
            tally: "off",
            vars: { amount: amount(l.difference.replace("-", ""), "whole").text },
            ...(onItemL === undefined ? {} : { link: { text: COPY.itemLOff, onClick: onItemL } }),
          };
  const tag =
    allocation === undefined
      ? null
      : `${COPY.allocationTag[allocation.kind]} · ${COPY.allocationStatus[allocation.status]}`;
  return [
    { label: COPY.cards.sumK1, tally: allTie ? "tie" : "off", vars: { amount: "" } },
    partners === undefined
      ? { label: COPY.cards.count, ...pending }
      : {
          label: COPY.cards.count,
          value: String(partners.partners.length),
          pill: { text: "tie", variant: "green" },
        },
    k.analysis === undefined || k.analysis === null
      ? { label: COPY.cards.analysis, ...pending }
      : { label: COPY.cards.analysis, value: amount(k.analysis.total, "whole").text },
    { label: COPY.cards.itemK, ...pending },
    itemLCard,
    tag === null
      ? { label: COPY.cards.allocation, ...pending }
      : { label: COPY.cards.allocation, pill: { text: tag, variant: "neutral" } },
  ];
}

export interface TXP05Props {
  k?: WorkbookScheduleKOut | undefined;
  partners?: WorkbookPartnersOut | undefined;
  capital?: WorkbookCapitalAccountsOut | undefined;
  allocation?: WorkbookAllocationStructureOut | undefined;
  view: Txp05View;
  /** The K-1 steps are running (D). */
  building?: boolean;
  /** A2: the Form 8825 breakdown shown for line 2. */
  breakdown?: WorkbookBreakdownOut | undefined;
  /** A4: Item L's popover is open. */
  itemLOpen?: boolean;
  onView?: (view: Txp05View) => void;
  onAllocation?: () => void;
  onFormPreview?: () => void;
  /** A line's row: line 2 opens its Form 8825 popover; any other the cell's provenance (SHL-09). */
  onOpenLine?: (line: string) => void;
  onCloseBreakdown?: () => void;
  onItemL?: (open: boolean) => void;
  onOpenCapital?: () => void;
  onOpenIssues?: () => void;
  /** A5: the partner's K-1 package (TXP-12). */
  onPartner?: (partnerId: string) => void;
}

export function TXP05({
  k,
  partners,
  capital,
  allocation,
  view,
  building = false,
  breakdown,
  itemLOpen = false,
  onView,
  onAllocation,
  onFormPreview,
  onOpenLine,
  onCloseBreakdown,
  onItemL,
  onOpenCapital,
  onOpenIssues,
  onPartner,
}: TXP05Props): JSX.Element {
  const ps = partners?.partners ?? [];
  const rows = k === undefined ? [] : tableRows(k, partners, capital);
  return (
    <div data-screen="TXP-05" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.federal, COPY.state]}
          active={view === "state" ? COPY.state : COPY.federal}
          {...(onView === undefined
            ? {}
            : {
                onChange: (label: string) => {
                  onView(label === COPY.state ? "state" : "federal");
                },
              })}
        />
        {building ? <Spinner size={12} label={COPY.building} showLabel /> : null}
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.title}</span>
        <Button variant="secondary" size="sm" icon="sliders-horizontal" onClick={onAllocation}>
          {COPY.allocation}
        </Button>
        <Button variant="ghost" size="sm" icon="file-text" onClick={onFormPreview}>
          {COPY.formPreview}
        </Button>
      </div>
      <div className="relative flex-none">
        <TallyStrip
          label={COPY.tally}
          items={tallyItems(k, partners, capital, allocation, building, () => onItemL?.(true))}
          className="px-[12px] pb-[10px]"
        />
        {itemLOpen ? (
          <div className="absolute right-[12px] top-0">
            <Popover
              open
              onOpenChange={(open) => onItemL?.(open)}
              label={COPY.itemLOff}
              width={300}
              trigger={<span aria-hidden className="block h-[1px] w-[1px]" />}
            >
              <p className="mb-[8px] text-body text-ink">{COPY.itemLOff}</p>
              <div className="flex gap-[8px]">
                <Button variant="secondary" size="sm" onClick={onOpenCapital}>
                  {COPY.openCapital}
                </Button>
                <Button variant="secondary" size="sm" onClick={onOpenIssues}>
                  {COPY.openIssues}
                </Button>
              </div>
            </Popover>
          </div>
        ) : null}
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-[12px] pb-[12px]">
        <div className="mb-[8px] flex items-center gap-[8px]">
          <span className="text-body font-medium text-ink">{COPY.pane}</span>
          <span className="flex-1" />
          {ps.length > 0 ? (
            <Menu
              label={COPY.partnerMenu}
              trigger={
                <Button variant="ghost" size="sm" icon="users">
                  {COPY.partners}
                </Button>
              }
              sections={[
                ps.map((p) => ({
                  label: `${p.name} · ${COPY.k1Package}`,
                  onSelect: () => onPartner?.(p.id),
                })),
              ]}
            />
          ) : null}
          <Pill variant="amber">{COPY.draft}</Pill>
        </div>
        {breakdown !== undefined ? (
          <div className="relative">
            <Popover
              open
              onOpenChange={(open) => {
                if (!open) onCloseBreakdown?.();
              }}
              label={COPY.breakdown}
              align="start"
              width={320}
              trigger={<span aria-hidden className="block h-[1px] w-[1px]" />}
            >
              <p className="mb-[6px] text-body font-medium text-ink">{COPY.breakdown}</p>
              <ul className="flex flex-col gap-[4px]">
                {breakdown.rows.map((r) => (
                  <li key={r.property_name} className="flex justify-between gap-[12px] text-body">
                    <span>{r.property_name}</span>
                    <span className="tabular-nums">{amount(r.amount, "whole").text}</span>
                  </li>
                ))}
              </ul>
            </Popover>
          </div>
        ) : null}
        {building || k === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.building} />
        ) : (
          <>
            <DataGrid
              label={COPY.table}
              grammar="statement"
              columns={columns(ps)}
              rows={rows}
              onOpen={(row) => {
                if (row.id.startsWith("line:")) onOpenLine?.(row.id.slice(5));
              }}
            />
            {view === "federal" ? (
              <p className="mt-[8px] text-[11.5px] text-ink-3">{COPY.footnote}</p>
            ) : null}
          </>
        )}
      </div>
    </div>
  );
}
