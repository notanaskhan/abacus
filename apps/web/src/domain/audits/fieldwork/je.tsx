import type {
  AbacusModulesSamplingFieldworkContractTieOut as TieOut,
  CriterionOut,
  ScoredEntryOut,
} from "@abacus/api-client";
import {
  AgentText,
  Amount,
  Button,
  IconButton,
  MATCH_CELL,
  MATCH_ROW,
  type MatchId,
  Pill,
  Spinner,
  Tick,
  cn,
  count,
  date,
  useMatch,
} from "@abacus/ui";
import type { JSX, ReactNode } from "react";
import { FIELDWORK_COPY, postedOn } from "./copy";

// The JE-testing half of the fieldwork L3 kit (A-08-T26; AUD-12 a, d to h): block cards on the
// #F8F8F6 well, the evidence grammar's th 28 / td 29 rows, value chips as the only clickable
// source links (lit purple through the MatchProvider), and a score never without its reasons.
// Every figure is the server's (ADR-050): the kit formats and never adds.

const C = FIELDWORK_COPY;
const TH = "h-[28px] bg-nested px-[8px] text-left text-[11.5px] font-normal text-ink-2";
const TD = "h-[29px] px-[8px] text-cell";

function day(iso: string): string {
  return date(iso, { now: 0, withYear: true });
}

/** A white e1 card on the well, with its 32px header and an optional right-hand meta. */
export function BlockCard({
  title,
  meta,
  children,
  className,
  label,
}: {
  title: string;
  meta?: ReactNode;
  children: ReactNode;
  className?: string;
  label?: string;
}): JSX.Element {
  return (
    <section
      aria-label={label ?? title}
      className={cn(
        "mx-[12px] mt-[12px] overflow-hidden rounded-pane bg-card shadow-e1",
        className,
      )}
    >
      <header className="flex h-[32px] items-center gap-[8px] px-[14px] hairline-b">
        <h3 className="text-[13px] font-medium">{title}</h3>
        {meta !== undefined && (
          <div className="ml-auto flex items-center gap-[8px] text-[11.5px] text-ink-3">
            {meta}
          </div>
        )}
      </header>
      {children}
    </section>
  );
}

/** The well the block cards sit on. */
export function CardWell({ children }: { children: ReactNode }): JSX.Element {
  return <div className="flex flex-col bg-shell pb-[12px]">{children}</div>;
}

// ---- Population --------------------------------------------------------------------------------

export interface PopulationCardProps {
  source: string;
  onSource?: () => void;
  entries: number;
  lines: number;
  periodStart: string;
  periodEnd: string;
  postCloseThrough?: string | undefined;
  tie: TieOut;
}

function Kv({ k, children }: { k: string; children: ReactNode }): JSX.Element {
  return (
    <div className="flex h-[33px] items-center gap-[12px] px-[14px] hairline-b last:shadow-none">
      <dt className="w-[110px] shrink-0 text-cell text-ink-2">{k}</dt>
      <dd className="flex min-w-0 items-center gap-[6px] text-cell">{children}</dd>
    </div>
  );
}

export function PopulationCard(p: PopulationCardProps): JSX.Element {
  const P = C.population;
  return (
    <BlockCard title={P.title}>
      <dl data-fieldwork="population">
        <Kv k={P.source}>
          <button
            type="button"
            className="underline-offset-2 hover:underline"
            onClick={p.onSource}
          >
            {p.source}
          </button>
          <span aria-hidden="true" className="text-ink-3">
            →
          </span>
        </Kv>
        <Kv k={P.entries}>
          <span className="tabular-nums">{count(p.entries)}</span>
        </Kv>
        <Kv k={P.lines}>
          <span className="tabular-nums">{count(p.lines)}</span>
        </Kv>
        <Kv k={P.period}>
          {`${day(p.periodStart)} – ${day(p.periodEnd)}`}
          {p.postCloseThrough !== undefined && (
            <span className="text-ink-2">{P.postClose(day(p.postCloseThrough))}</span>
          )}
        </Kv>
        <Kv k={P.completeness}>
          <span className="truncate">{P.tie(p.tie.accounts_tied, p.tie.accounts_total)}</span>
          <Pill
            variant={p.tie.result === "tie" ? "green-tint" : "red-tint"}
            check={p.tie.result === "tie"}
          >
            {p.tie.result === "tie" ? "Tie" : "Difference"}
          </Pill>
        </Kv>
        <Kv k={P.difference}>
          <Amount value={p.tie.difference} zero="explicit" />
        </Kv>
      </dl>
    </BlockCard>
  );
}

// ---- Risk criteria -----------------------------------------------------------------------------

export interface CriteriaTableProps {
  criteria: readonly CriterionOut[];
  uniqueFlagged: number;
  /** The criterion the selected-entries table is filtered to (a row click toggles it). */
  filter?: CriterionOut["key"] | null | undefined;
  onFilter?: (key: CriterionOut["key"] | null) => void;
  /** "Round dollar ≥ $50,000": the firm's parameters, as text for the label's tail. */
  detail?: Partial<Record<CriterionOut["key"], string>>;
  footer?: string | undefined;
}

export function CriteriaTable({
  criteria,
  uniqueFlagged,
  filter = null,
  onFilter,
  detail = {},
  footer,
}: CriteriaTableProps): JSX.Element {
  const K = C.criteria;
  return (
    <BlockCard title={K.title}>
      <table className="w-full border-collapse" data-fieldwork="criteria">
        <caption className="sr-only">{K.title}</caption>
        <thead>
          <tr className="hairline-b">
            <th scope="col" className={TH}>
              {K.title}
            </th>
            <th scope="col" className={cn(TH, "text-right")}>
              {K.count}
            </th>
          </tr>
        </thead>
        <tbody>
          {criteria.map((c) => {
            const on = filter === c.key;
            const usable = c.availability === "available";
            return (
              <tr
                key={c.key}
                data-criterion={c.key}
                data-filtered={on ? "" : undefined}
                className={cn("hairline-b", on && "bg-sel-bg")}
              >
                <td className={TD}>
                  <button
                    type="button"
                    aria-pressed={on}
                    disabled={!usable}
                    className="text-left disabled:cursor-default"
                    onClick={() => onFilter?.(on ? null : c.key)}
                  >
                    {K.label[c.key]}
                    {detail[c.key] !== undefined && (
                      <span className="text-ink-2"> {detail[c.key]}</span>
                    )}
                  </button>
                  {!usable && (
                    <span className="ml-[8px] text-[11.5px] text-ink-3">
                      {K.unavailable}
                      {c.missing_fields.length > 0 && ` (${c.missing_fields.join(", ")})`}
                    </span>
                  )}
                </td>
                <td className={cn(TD, "text-right tabular-nums")}>{usable ? c.hit_count : "—"}</td>
              </tr>
            );
          })}
          <tr className="shadow-[inset_0_1px_0_var(--color-stroke)]">
            <th scope="row" className={cn(TD, "text-left font-medium")}>
              {K.unique}
            </th>
            <td className={cn(TD, "text-right font-medium tabular-nums")}>{uniqueFlagged}</td>
          </tr>
        </tbody>
      </table>
      {footer !== undefined && (
        <p className="px-[14px] py-[8px] text-[11.5px] text-ink-3">{footer}</p>
      )}
    </BlockCard>
  );
}

// ---- Selected entries --------------------------------------------------------------------------

export type EntryResult =
  "pass" | "needs_human" | "agent_tested" | "not_started" | "exception" | "running";

export interface SelectedEntry {
  position: number;
  entry: ScoredEntryOut;
  /** The posting user's handle ("lferrante"): confidential, shown to the engagement team only. */
  user?: string | undefined;
  /** "Dr 5000 COGS / Cr 1450 Inventory reserve" (account numbers as the ledger prints them). */
  drcr?: string | undefined;
  result: EntryResult;
}

function Result({ result }: { result: EntryResult }): JSX.Element {
  const R = C.selected.result;
  switch (result) {
    case "pass":
      return <Tick code="MS" />;
    case "needs_human":
      return <Pill variant="amber">{R.needs_human}</Pill>;
    case "agent_tested":
      return (
        <Pill variant="outline" check>
          {R.agent_tested}
        </Pill>
      );
    case "exception":
      return <Pill variant="red-tint">{R.exception}</Pill>;
    case "running":
      return (
        <span role="status" aria-label={R.running} className="inline-flex">
          <Spinner label={C.selected.result.running} />
        </span>
      );
    case "not_started":
      return <Pill variant="muted">{R.not_started}</Pill>;
  }
}

export interface SelectedEntriesCardProps {
  rows: readonly SelectedEntry[];
  total: number;
  /** 1-based first position of this page. */
  from: number;
  onPage?: (direction: -1 | 1) => void;
  selectedRef?: string | null | undefined;
  onSelect?: (entryRef: string) => void;
  onReview?: () => void;
  pending?: { add: number; initials: string } | undefined;
}

export function SelectedEntriesCard(p: SelectedEntriesCardProps): JSX.Element {
  const S = C.selected;
  const to = p.from + p.rows.length - 1;
  const title =
    p.pending === undefined
      ? S.title(p.total)
      : S.pending(p.total, p.pending.add, p.pending.initials);
  return (
    <BlockCard
      title={title}
      label={S.title(p.total)}
      meta={
        <>
          {p.onReview !== undefined && (
            <button
              type="button"
              onClick={p.onReview}
              className="text-[12.5px] font-medium text-ink"
            >
              {S.review} <span className="text-ink-3">→</span>
            </button>
          )}
          <span className="tabular-nums">{S.page(p.from, to, p.total)}</span>
          <IconButton
            icon="chevron-left"
            label={S.previous}
            disabled={p.from <= 1}
            onClick={() => p.onPage?.(-1)}
          />
          <IconButton
            icon="chevron-right"
            label={S.next}
            disabled={to >= p.total}
            onClick={() => p.onPage?.(1)}
          />
        </>
      }
    >
      <table className="w-full border-collapse" data-fieldwork="selected">
        <caption className="sr-only">{S.title(p.total)}</caption>
        <thead>
          <tr className="hairline-b">
            {S.columns.map((h, i) => (
              <th key={h} scope="col" className={cn(TH, (i === 5 || i === 7) && "text-right")}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {p.rows.map((r) => (
            <EntryRow
              key={r.entry.entry_ref}
              row={r}
              selected={p.selectedRef === r.entry.entry_ref}
              onSelect={p.onSelect}
            />
          ))}
        </tbody>
      </table>
    </BlockCard>
  );
}

function EntryRow({
  row,
  selected,
  onSelect,
}: {
  row: SelectedEntry;
  selected: boolean;
  onSelect?: ((entryRef: string) => void) | undefined;
}): JSX.Element {
  const e = row.entry;
  return (
    <tr
      data-entry={e.entry_ref}
      data-result={row.result}
      aria-selected={selected}
      onClick={() => onSelect?.(e.entry_ref)}
      className={cn(
        "cursor-default hairline-b",
        selected && "bg-sel-bg",
        row.result === "exception" && "bg-red-tint",
      )}
    >
      <td className={cn(TD, "text-ink-3 tabular-nums")}>{row.position}</td>
      <td className={TD}>
        <button type="button" className="text-left" onClick={() => onSelect?.(e.entry_ref)}>
          {e.entry_ref}
        </button>
      </td>
      <td className={cn(TD, "whitespace-nowrap")}>{postedOn(e.posted_on, day(e.posted_on))}</td>
      <td className={TD}>{row.user ?? "—"}</td>
      <td className={cn(TD, "text-ink-2")}>{row.drcr ?? "—"}</td>
      <td className={cn(TD, "text-right")}>
        <Amount value={e.amount} />
      </td>
      <td className={cn(TD, "text-ink-2")} data-reasons={e.reason_codes.join(" ")}>
        {e.reason_codes.map((code) => C.reasons[code]).join(", ")}
      </td>
      <td className={cn(TD, "text-right tabular-nums")}>{e.score}</td>
      <td className={TD}>
        <Result result={row.result} />
      </td>
    </tr>
  );
}

// ---- Attributes --------------------------------------------------------------------------------

export interface AttributeRow {
  key: string;
  label: string;
  /** The evidence's value: a value chip when it cites a region of the document beside it. */
  value: string;
  match?: MatchId | undefined;
  /** True agreed, false an exception, null not yet tested. */
  agreed: boolean | null;
  /** The agent's note on the attribute (rendered through AgentText, amber corner). */
  agentNote?: string | undefined;
}

/** The only clickable source link: lights its region in the viewer (MatchProvider, 360 ms). */
export function ValueChipLink({
  match,
  children,
}: {
  match: MatchId;
  children: string;
}): JSX.Element {
  const { bind, pin, lit } = useMatch(match, "cell");
  return (
    <button
      type="button"
      {...bind}
      aria-pressed={lit}
      onClick={(event) => {
        pin(event.currentTarget);
      }}
      className={cn(
        MATCH_CELL,
        "inline-block max-w-full truncate rounded-prop bg-sel-bg px-[6px] py-[1px] align-middle text-cell leading-[1.3] inset-ring-[0.5px] inset-ring-stroke",
      )}
    >
      {children}
    </button>
  );
}

export function AttributesCard({
  entryRef,
  rows,
}: {
  entryRef: string;
  rows: readonly AttributeRow[];
}): JSX.Element {
  const A = C.attributes;
  return (
    <BlockCard title={A.title(entryRef)}>
      <ul data-fieldwork="attributes">
        {rows.map((r) => (
          <li
            key={r.key}
            data-attribute={r.key}
            className={cn(
              "relative flex min-h-[33px] items-start gap-[12px] px-[14px] py-[7px] hairline-b",
              r.agentNote !== undefined &&
                "after:absolute after:top-0 after:right-0 after:border-t-[8px] after:border-l-[8px] after:border-t-amber after:border-l-transparent",
            )}
          >
            <span className="w-[150px] shrink-0 text-cell text-ink-2">{r.label}</span>
            <div className="flex min-w-0 flex-1 flex-col gap-[4px]">
              <span className="text-cell">
                {r.match !== undefined ? (
                  <ValueChipLink match={r.match}>{r.value}</ValueChipLink>
                ) : (
                  r.value
                )}
              </span>
              {r.agentNote !== undefined && (
                <div className="text-[11.5px] text-ink-2">
                  <AgentText text={r.agentNote} />
                </div>
              )}
            </div>
            <span className="shrink-0">
              {r.agreed === true && <Tick code="check" />}
              {r.agreed === false && <Pill variant="red-tint">{C.selected.result.exception}</Pill>}
              {r.agreed === null && <Pill variant="muted">{A.open}</Pill>}
            </span>
          </li>
        ))}
      </ul>
    </BlockCard>
  );
}

// ---- The pinned footer -------------------------------------------------------------------------

export interface TestingFooterProps {
  onAdopt?: () => void;
  onExpand?: () => void;
  onRaise?: () => void;
  /** Awaiting approval of an expansion: the button shows who it waits on. */
  waitingOn?: string | undefined;
  /** State h: "Expand testing…" is the primary action. */
  expandPrimary?: boolean;
}

export function TestingFooter(p: TestingFooterProps): JSX.Element {
  const F = C.footer;
  return (
    <footer
      data-fieldwork="footer"
      className="sticky bottom-0 flex h-[54px] items-center gap-[8px] bg-card px-[14px] shadow-[inset_0_1px_0_var(--color-hair)]"
    >
      <Button variant={p.expandPrimary === true ? "tonal" : "primary"} onClick={p.onAdopt}>
        {F.adopt}
      </Button>
      {p.waitingOn !== undefined ? (
        <Pill variant="muted">{F.waiting(p.waitingOn)}</Pill>
      ) : (
        <Button variant={p.expandPrimary === true ? "primary" : "secondary"} onClick={p.onExpand}>
          {F.expand}
        </Button>
      )}
      <Button variant="tonal" onClick={p.onRaise}>
        {F.raise}
      </Button>
    </footer>
  );
}

/** Rows that light with the viewer's region while their entry is selected (AUD-12 a, row 5). */
export const LIT_ROW = MATCH_ROW;
