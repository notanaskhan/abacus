// TXP-07 · Review › Capital Accounts (T-05-T55; docs/screens/TXP-07.md; handoff TXP-07 a–e): T6
// inside the entity return's layout. The control bar (By partner · By movement, the title, the pager,
// Open in Excel and Sign off…), the tally strip and either the partner panes (683 wide, Tax · 704(b)
// · Book) or the movement table with its tie-out to Schedule L. Every figure, total and tie is the
// server's (`GET …/capital-accounts`, `…/partners`); the screen formats and lays out and adds
// nothing (ADR-050). a2: an amber tax-exempt cell opens its provenance (SHL-09); a3: a transfer opens
// the Allocation Structure (TXP-06); off 6,200 opens the issue (TXP-10); b2: Sign off… while a
// tie-out is off asks for a note (SHL-12); d: values reveal 45 ms apart, rows 70 ms (still under
// reduced motion); e: signed off.
import type {
  WorkbookCapitalAccountsOut,
  WorkbookCapitalRowOut,
  WorkbookPartnersOut,
} from "@abacus/api-client";
import {
  Button,
  DataGrid,
  Icon,
  Pill,
  Reveal,
  Segmented,
  SkeletonRows,
  Spinner,
  type TableColumn,
  type TableRow,
  type TallyItem,
  TallyStrip,
  Tag,
  amount,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { COPY, GP_NAMES, PANE_NOTE } from "./copy";

export type Txp07View = "by_partner" | "by_movement";

export const PANE_WIDTH = 683;
export const PANES_VISIBLE = 2;
const TALLY_STAGGER_MS = 45;
const ROW_STAGGER_MS = 70;

function money(value: string | null | undefined, negate = false): string {
  if (value === null || value === undefined) return "—";
  if (Number(value) === 0) return "—";
  const shown = negate && !value.startsWith("-") ? `-${value}` : value;
  return amount(shown, "whole").text;
}

function tieCard(label: string, state: string | undefined, difference?: string): TallyItem {
  if (state === "tie") return { label, tally: "tie" };
  if (state === "off") {
    return {
      label,
      tally: "off",
      vars: {
        amount: difference === undefined ? "" : amount(difference.replace("-", ""), "whole").text,
      },
    };
  }
  return { label, pill: { text: COPY.pending, variant: "neutral" } };
}

/** The strip: four checks then the movement totals with their derivations (the server's). */
export function tallyItems(
  capital: WorkbookCapitalAccountsOut | undefined,
  computing: boolean,
  onOff?: () => void,
): TallyItem[] {
  const pending = { pill: { text: COPY.pending, variant: "neutral" as const } };
  if (computing || capital === undefined) {
    return Object.values(COPY.cards)
      .filter((label) => label !== COPY.cards.other)
      .map((label) => ({ label, ...pending }));
  }
  const l = capital.item_l;
  const m2 = tieCard(COPY.cards.m2, l?.tie, l?.difference);
  const m2Card: TallyItem =
    "tally" in m2 && m2.tally === "off" && onOff !== undefined
      ? { ...m2, link: { text: COPY.offLink, onClick: onOff } }
      : m2;
  const t = capital.totals;
  const value = (label: string, v: string | null | undefined, info: string): TallyItem =>
    v === null || v === undefined
      ? { label, ...pending }
      : { label, value: amount(v, "whole").text, info };
  const items: TallyItem[] = [
    tieCard(COPY.cards.foots, capital.tie),
    m2Card,
    tieCard(COPY.cards.book, capital.book_tie),
    tieCard(COPY.cards.derives, capital.derives_tie),
    value(COPY.cards.begin, t?.beginning, COPY.derivation.begin),
    value(COPY.cards.contributions, t?.contributions, COPY.derivation.contributions),
    value(COPY.cards.income, t?.income, COPY.derivation.income),
  ];
  if (t?.tax_exempt !== null && t?.tax_exempt !== undefined) {
    items.push(value(COPY.cards.other, t.tax_exempt, COPY.derivation.other));
  }
  items.push(
    value(COPY.cards.transfers, t?.transfers ?? "0", COPY.derivation.transfers),
    value(COPY.cards.distributions, t?.distributions, COPY.derivation.distributions),
    value(COPY.cards.end, t?.ending, COPY.derivation.end),
  );
  return items;
}

// --- By partner: one pane per partner -------------------------------------------------------------

export interface PaneLine {
  id: string;
  label: string;
  kind: "item" | "group" | "total";
  tax: string;
  b704: string;
  book: string;
  /** The tax cell is blank where 704(b) carries an amount: amber, opens SHL-09. */
  amber?: string | undefined;
  /** A transfer cell: opens TXP-06. */
  transfer?: boolean | undefined;
}

/** A pane's rows as the handoff draws them; 704(b) and book are the same column (the server's
 * 704(b) values; "704(b) = book" is the footer's statement). */
export function paneLines(row: WorkbookCapitalRowOut): PaneLine[] {
  const same = (
    id: string,
    label: string,
    v: string | null | undefined,
    negate = false,
  ): PaneLine => {
    const shown = money(v, negate);
    return { id, label, kind: "item", tax: shown, b704: shown, book: shown };
  };
  const taxExempt = money(row.tax_exempt);
  const taxExempt704 = money(row.tax_exempt_704b);
  const amberCell =
    (row.tax_exempt === null || row.tax_exempt === undefined) &&
    row.tax_exempt_704b !== null &&
    row.tax_exempt_704b !== undefined &&
    Number(row.tax_exempt_704b) !== 0 &&
    row.row !== null &&
    row.row !== undefined
      ? `05 Capital!G${String(row.row)}`
      : undefined;
  const transfers = same("transfers", COPY.rows.transfers, row.transfers);
  const ending704 = money(row.ending_704b ?? row.ending);
  return [
    same("beginning", COPY.rows.beginning, row.beginning),
    {
      id: "g:contributions",
      label: COPY.groups.contributions,
      kind: "group",
      tax: "",
      b704: "",
      book: "",
    },
    same("cash", COPY.rows.cash, row.contributions),
    { id: "g:income", label: COPY.groups.income, kind: "group", tax: "", b704: "", book: "" },
    same("allocated", COPY.rows.allocated, row.income),
    {
      id: "tax_exempt",
      label: COPY.rows.taxExempt,
      kind: "item",
      tax: taxExempt,
      b704: taxExempt704,
      book: taxExempt704,
      amber: amberCell,
    },
    same("nondeductible", COPY.rows.nondeductible, row.nondeductible),
    { id: "g:other", label: COPY.groups.other, kind: "group", tax: "", b704: "", book: "" },
    { ...transfers, transfer: row.transfers !== null && row.transfers !== undefined },
    same("guaranteed", COPY.rows.guaranteed, row.guaranteed_payments),
    {
      id: "g:distributions",
      label: COPY.groups.distributions,
      kind: "group",
      tax: "",
      b704: "",
      book: "",
    },
    same("distributions", COPY.rows.distributions, row.distributions, true),
    {
      id: "ending",
      label: COPY.rows.ending,
      kind: "total",
      tax: money(row.ending),
      b704: ending704,
      book: ending704,
    },
  ];
}

interface PaneProps {
  row: WorkbookCapitalRowOut;
  fixed: boolean;
  animate: boolean;
  baseDelay: number;
  onOpenCell?: ((cell: string) => void) | undefined;
  onTransfers?: (() => void) | undefined;
}

function PartnerPane({
  row,
  fixed,
  animate,
  baseDelay,
  onOpenCell,
  onTransfers,
}: PaneProps): JSX.Element {
  const name = row.name ?? "";
  const tag = GP_NAMES.has(name) ? "GP" : "LP";
  const note = PANE_NOTE[name];
  const lines = paneLines(row);
  return (
    <section
      aria-label={name}
      data-pane={row.partner_id}
      className="flex flex-none flex-col rounded-[10px] border border-hair bg-card"
      style={{ width: PANE_WIDTH }}
    >
      <table className="w-full table-fixed border-collapse text-body tabular-nums">
        <colgroup>
          <col style={{ width: 246 }} />
          <col style={{ width: 140 }} />
          <col style={{ width: 140 }} />
          <col style={{ width: 140 }} />
        </colgroup>
        <thead>
          <tr className="h-[36px] border-b border-hair">
            <th scope="col" className="px-[12px] text-left text-[13px] font-medium text-ink">
              <span className="inline-flex items-center gap-[6px]">
                {name}
                <Tag>{tag}</Tag>
                {note ? <span className="text-ink-3">· {note}</span> : null}
              </span>
            </th>
            <th scope="col" className="px-[12px] text-right text-ink-2">
              {COPY.columns.tax}
            </th>
            <th scope="col" className="px-[12px] text-right text-ink-2">
              {COPY.columns.b704}
            </th>
            <th scope="col" className="px-[12px] text-right text-ink-2">
              {COPY.columns.book}
            </th>
          </tr>
        </thead>
        <tbody>
          {lines.map((line, i) => {
            const delay = baseDelay + i * ROW_STAGGER_MS;
            if (line.kind === "group") {
              return (
                <tr key={line.id} className="h-[24px]">
                  <th
                    scope="rowgroup"
                    colSpan={4}
                    className="px-[12px] text-left text-[10px] font-medium uppercase tracking-[0.04em] text-ink-3"
                  >
                    {line.label}
                  </th>
                </tr>
              );
            }
            const total = line.kind === "total";
            return (
              <tr
                key={line.id}
                data-line={line.id}
                className={total ? "h-[32px] border-t border-ink font-medium" : "h-[28px]"}
              >
                <th
                  scope="row"
                  className={`px-[12px] text-left font-normal ${total ? "font-medium" : "pl-[24px]"} text-ink`}
                >
                  {line.label}
                </th>
                {(["tax", "b704", "book"] as const).map((col) => {
                  const text = line[col];
                  const amber = col === "tax" && line.amber !== undefined && !fixed;
                  const transfer = line.transfer === true;
                  const body = animate ? (
                    <Reveal as="span" delay={delay}>
                      {text}
                    </Reveal>
                  ) : (
                    text
                  );
                  return (
                    <td
                      key={col}
                      className={`px-[12px] text-right ${amber ? "bg-amber-tint text-amber-ink" : "text-ink"}`}
                    >
                      {amber ? (
                        <button
                          type="button"
                          className="inline-flex w-full items-center justify-end gap-[4px]"
                          aria-label={COPY.amberCell(line.amber ?? "")}
                          onClick={() => onOpenCell?.(line.amber ?? "")}
                        >
                          <Icon name="triangle-alert" size={12} />
                          {body}
                        </button>
                      ) : transfer ? (
                        <button
                          type="button"
                          className="w-full text-right underline-offset-2 hover:underline"
                          aria-label={COPY.transfersCell}
                          onClick={onTransfers}
                        >
                          {body}
                        </button>
                      ) : (
                        body
                      )}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-auto px-[12px] pb-[10px] pt-[8px] text-[11.5px] text-ink-3">
        {fixed ? COPY.footerFixed : COPY.footer}
        {row.transfers !== null && row.transfers !== undefined ? ` ${COPY.transferNote}` : ""}
      </p>
    </section>
  );
}

// --- By movement --------------------------------------------------------------------------------

const MONEY = { type: "num", format: "whole" } as const;

export function movementColumns(): TableColumn[] {
  const c = COPY.movementColumns;
  return [
    { key: "partner", header: c.partner, type: "label", width: 240 },
    { key: "pct", header: c.pct, type: "text", width: 100 },
    { key: "beginning", header: c.beginning, ...MONEY, width: 112 },
    { key: "contributions", header: c.contributions, ...MONEY, width: 100 },
    { key: "income", header: c.income, ...MONEY, width: 112 },
    { key: "transfers", header: c.transfers, ...MONEY, width: 100 },
    { key: "distributions", header: c.distributions, ...MONEY, width: 100 },
    { key: "ending", header: c.ending, ...MONEY, width: 112 },
  ];
}

function pctOf(partners: WorkbookPartnersOut | undefined, id: string): string {
  const first = partners?.periods[0]?.shares[id];
  const last = partners?.periods.at(-1)?.shares[id];
  const pct = (v: string | undefined) => `${String(Number(v ?? "0"))}%`;
  if (first === undefined && last === undefined) return "—";
  return first === last ? pct(last) : `${pct(first)} → ${pct(last)}`;
}

const cell = (v: string | null | undefined, negate = false) => ({
  value:
    v === null || v === undefined || Number(v) === 0
      ? null
      : negate && !v.startsWith("-")
        ? `-${v}`
        : v,
});

export function movementRows(
  capital: WorkbookCapitalAccountsOut,
  partners: WorkbookPartnersOut | undefined,
): TableRow[] {
  const rows: TableRow[] = capital.rows.map((r) => ({
    id: `partner:${r.partner_id}`,
    label: r.name ?? "",
    tag: GP_NAMES.has(r.name ?? "") ? "GP" : "LP",
    cells: {
      pct: { value: pctOf(partners, r.partner_id) },
      beginning: cell(r.beginning),
      contributions: cell(r.contributions),
      income: cell(r.income),
      transfers: cell(r.transfers),
      distributions: cell(r.distributions, true),
      ending: cell(r.ending),
    },
  }));
  const t = capital.totals;
  if (t !== null && t !== undefined) {
    rows.push({
      id: "total",
      kind: "total",
      label: COPY.rows.total,
      cells: {
        beginning: { value: t.beginning },
        contributions: { value: t.contributions },
        income: { value: t.income },
        transfers: { value: t.transfers ?? "0" },
        distributions: cell(t.distributions, true),
        ending: { value: t.ending },
      },
    });
  }
  return rows;
}

// --- the screen ---------------------------------------------------------------------------------

export interface TXP07Props {
  capital?: WorkbookCapitalAccountsOut | undefined;
  partners?: WorkbookPartnersOut | undefined;
  view: Txp07View;
  /** The first visible pane (0-based); the pager moves it by two. */
  page?: number;
  /** d: the workbook agent is computing the schedule. */
  computing?: boolean;
  /** b2: Sign off… opened while a tie-out is off. */
  signOffOpen?: boolean;
  /** e: the viewer's initials once signed off. */
  signedBy?: string | undefined;
  onView?: (view: Txp07View) => void;
  onPage?: (first: number) => void;
  onOpenCell?: (cell: string) => void;
  onTransfers?: () => void;
  onOpenIssue?: () => void;
  onOpenExcel?: () => void;
  onSignOff?: (note: string | null) => void;
  onSignOffOpen?: (open: boolean) => void;
}

export function TXP07({
  capital,
  partners,
  view,
  page = 0,
  computing = false,
  signOffOpen = false,
  signedBy,
  onView,
  onPage,
  onOpenCell,
  onTransfers,
  onOpenIssue,
  onOpenExcel,
  onSignOff,
  onSignOffOpen,
}: TXP07Props): JSX.Element {
  const [note, setNote] = useState("");
  const rows = capital?.rows ?? [];
  const fixed = capital?.item_l?.tie === "tie";
  const offCount =
    capital === undefined
      ? 0
      : // Item L's tie and the capital total's tie are one check (05 against Schedule L).
        [capital.item_l?.tie ?? capital.tie, capital.book_tie].filter((s) => s === "off").length;
  const items = tallyItems(capital, computing, onOpenIssue);
  const last = Math.min(page + PANES_VISIBLE, rows.length);
  const signOff = () => {
    if (offCount > 0) onSignOffOpen?.(true);
    else onSignOff?.(null);
  };
  return (
    <div data-screen="TXP-07" className="flex min-h-0 flex-1 flex-col">
      <div className="flex h-[44px] flex-none items-center gap-[8px] px-[12px]">
        <Segmented
          size="small"
          label={COPY.views}
          options={[COPY.byPartner, COPY.byMovement]}
          active={view === "by_movement" ? COPY.byMovement : COPY.byPartner}
          {...(onView === undefined
            ? {}
            : {
                onChange: (label: string) => {
                  onView(label === COPY.byMovement ? "by_movement" : "by_partner");
                },
              })}
        />
        {computing ? <Spinner size={12} label={COPY.computing} showLabel /> : null}
        <span className="flex-1 text-center text-[14.5px] font-medium text-ink">{COPY.title}</span>
        {view === "by_partner" && rows.length > 0 ? (
          <span className="flex items-center gap-[4px]">
            <Button
              variant="ghost"
              size="sm"
              icon="chevron-left"
              aria-label={COPY.pagerPrev}
              disabled={page === 0}
              onClick={() => onPage?.(Math.max(0, page - PANES_VISIBLE))}
            />
            <span className="text-body text-ink-2">{COPY.pager(page + 1, last, rows.length)}</span>
            <Button
              variant="ghost"
              size="sm"
              icon="chevron-right"
              aria-label={COPY.pagerNext}
              disabled={last >= rows.length}
              onClick={() => onPage?.(Math.min(rows.length - 1, page + PANES_VISIBLE))}
            />
          </span>
        ) : null}
        {signedBy !== undefined ? (
          <>
            <Pill variant="neutral">{COPY.signedChip(signedBy)}</Pill>
            <Pill variant="green">{COPY.reviewed(signedBy)}</Pill>
          </>
        ) : null}
        <Button variant="ghost" size="sm" icon="file-spreadsheet" onClick={onOpenExcel}>
          {COPY.openExcel}
        </Button>
        {signedBy === undefined ? (
          <Button variant="secondary" size="sm" onClick={signOff}>
            {COPY.signOff}
          </Button>
        ) : null}
      </div>
      {computing ? (
        <Reveal>
          <TallyStrip label={COPY.tally} items={items} className="px-[12px] pb-[10px]" />
        </Reveal>
      ) : (
        <TallyStrip label={COPY.tally} items={items} className="px-[12px] pb-[10px]" />
      )}
      {signOffOpen ? (
        <div
          role="dialog"
          aria-label={COPY.signOff}
          className="mx-[12px] mb-[10px] rounded-[10px] border border-amber bg-amber-tint p-[12px]"
        >
          <p className="mb-[8px] text-body text-amber-ink">
            {COPY.blocked(Math.max(1, offCount))}
          </p>
          <label className="mb-[8px] flex flex-col gap-[4px] text-body text-ink">
            {COPY.noteLabel}
            <textarea
              value={note}
              onChange={(e) => {
                setNote(e.target.value);
              }}
              rows={2}
              className="rounded-[6px] border border-hair bg-card p-[6px]"
            />
          </label>
          <div className="flex gap-[8px]">
            <Button variant="secondary" size="sm" onClick={onOpenIssue}>
              {COPY.resolve}
            </Button>
            <Button
              variant="primary"
              size="sm"
              disabled={note.trim() === ""}
              onClick={() => onSignOff?.(note.trim())}
            >
              {COPY.signWithNote}
            </Button>
            <Button variant="ghost" size="sm" onClick={() => onSignOffOpen?.(false)}>
              {COPY.cancel}
            </Button>
          </div>
        </div>
      ) : null}
      <div className="min-h-0 flex-1 overflow-hidden px-[12px] pb-[12px]">
        {capital === undefined ? (
          <SkeletonRows type="table" immediate label={COPY.computing} />
        ) : view === "by_partner" ? (
          <div className="flex gap-[10px] overflow-x-auto pb-[6px]" data-pager-first={page}>
            {rows.slice(page, page + PANES_VISIBLE).map((r, i) => (
              <PartnerPane
                key={r.partner_id}
                row={r}
                fixed={fixed}
                animate={computing}
                baseDelay={items.length * TALLY_STAGGER_MS + i * ROW_STAGGER_MS}
                onOpenCell={onOpenCell}
                onTransfers={onTransfers}
              />
            ))}
          </div>
        ) : (
          <div className="overflow-auto">
            <DataGrid
              label={COPY.title}
              grammar="statement"
              columns={movementColumns()}
              rows={movementRows(capital, partners)}
            />
            {capital.item_l !== null && capital.item_l !== undefined ? (
              <table
                className="mt-[8px] w-[560px] border-collapse text-body tabular-nums"
                aria-label={COPY.groups.tieOut}
              >
                <thead>
                  <tr className="h-[24px]">
                    <th
                      scope="colgroup"
                      colSpan={2}
                      className="text-left text-[10px] font-medium uppercase tracking-[0.04em] text-ink-3"
                    >
                      {COPY.groups.tieOut}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  <tr className="h-[28px]">
                    <th scope="row" className="text-left font-normal text-ink">
                      {COPY.tieOut.m2}
                    </th>
                    <td className="text-right text-ink">
                      {amount(capital.item_l.capital_ending, "whole").text}
                    </td>
                  </tr>
                  <tr className="h-[28px]">
                    <th scope="row" className="text-left font-normal text-ink">
                      {COPY.tieOut.schL}
                    </th>
                    <td className="text-right text-ink">
                      {amount(capital.item_l.m2_ending, "whole").text}
                    </td>
                  </tr>
                  <tr className="h-[28px]">
                    <th scope="row" className="text-left font-medium text-ink">
                      {COPY.tieOut.difference}
                    </th>
                    <td
                      className={`text-right ${capital.item_l.tie === "off" ? "text-red-ink" : "text-ink"}`}
                    >
                      {capital.item_l.tie === "off" ? (
                        <button
                          type="button"
                          onClick={onOpenIssue}
                          aria-label={COPY.tieOut.openIssue}
                          className="inline-flex items-center gap-[6px]"
                        >
                          <Icon name="flag" size={12} />
                          {amount(capital.item_l.difference, "whole").text}
                          <span aria-hidden className="text-ink-3">
                            →
                          </span>
                        </button>
                      ) : (
                        "—"
                      )}
                    </td>
                  </tr>
                </tbody>
              </table>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
}
