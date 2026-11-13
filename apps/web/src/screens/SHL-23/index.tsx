// SHL-23 · Today brief panel (I-02-T15; docs/screens/SHL-23.md; SPEC-654 §3.1–§3.11; handoff
// SHL-23 1, 4, 6, 7 and the composed states). The panel on the C-00 Pane: the header (greeting,
// items and engagements line, History, ··· Rebuild brief), the Today card's count cells linking to
// HOME-02's bands with the code fact paragraph (DEC-4608), Needs you first with each row's verified
// why line (AgentBlocks) or, without one, its code context line, the collapsible group bands (High
// risk card, Late, Due tomorrow, Ready for sign-off, Needs attention, Running), the composer slot
// and the footer. Building draws the skeleton with its counts; the quiet day the empty state;
// DF-04 states and per-card fallbacks keep every count and row (they are code). Every count is
// the server's, equal to HOME-01 and HOME-02 (I-COUNT); nothing here counts or composes figures.
import type { Card, GateRow, Group, TodayVm } from "@abacus/api-client";
import {
  type AgentBlocksPayload,
  AgentBlocks,
  Button,
  EmptyState,
  Icon,
  Menu,
  SkeletonRows,
  time as clockTime,
} from "@abacus/ui";
import { type JSX, useState } from "react";
import { CELL_LABELS, COPY, GROUP_LABELS, REASON_COPY, leadSentence } from "./copy";

export type TodayLayout = "focus" | "by_engagement";

/** The code fact paragraph from the registered lead facts (DEC-4608). */
export function factParagraph(vm: TodayVm): string {
  return vm.lead_facts
    .map((f) => leadSentence(f.key, f.values as Readonly<Record<string, unknown>>))
    .filter((s): s is string => s !== null)
    .join(" ");
}

function Why({ row }: { row: GateRow }): JSX.Element {
  const docs = (row.why_blocks ?? []) as unknown as AgentBlocksPayload[];
  if (docs.length === 0) {
    // No verified why line: the row's words are HOME-01's code context line.
    return <p className="text-[12px] text-ink-2">{row.context_line}</p>;
  }
  return (
    <div data-why={row.gate_id} className="text-[12px] text-ink-2">
      {docs.map((doc, i) => (
        <AgentBlocks key={String(i)} blocks={doc} facts={{}} />
      ))}
    </div>
  );
}

function RowLink({
  row,
  onOpen,
  onHover,
}: {
  row: GateRow;
  onOpen?: ((href: string) => void) | undefined;
  onHover?: ((refs: readonly string[] | null) => void) | undefined;
}): JSX.Element {
  return (
    <li
      data-row={row.gate_id}
      className="rounded-[8px] data-[lit=true]:bg-match-bg"
      onMouseEnter={() => onHover?.(row.highlight_refs ?? [])}
      onMouseLeave={() => onHover?.(null)}
      onFocus={() => onHover?.(row.highlight_refs ?? [])}
      onBlur={() => onHover?.(null)}
    >
      <button
        type="button"
        onClick={() => onOpen?.(row.deep_link)}
        className="flex w-full flex-col gap-[2px] rounded-[8px] px-[10px] py-[8px] text-left hover:bg-nested"
      >
        <span className="flex items-center gap-[6px]">
          <span className="flex-1 truncate text-[13px] font-medium text-ink">{row.title}</span>
          {row.state === "blocked" ? (
            <span className="rounded-pill bg-amber-tint px-[6px] text-[11px] text-amber-ink">
              Blocked
            </span>
          ) : null}
          {row.due ? (
            <span
              className={`rounded-pill px-[6px] text-[11px] ${row.due.tone === "red_tint" ? "bg-red-tint text-red-ink" : "bg-nested text-ink-2"}`}
            >
              {row.due.days <= 0
                ? "Today"
                : row.due.days === 1
                  ? "Tomorrow"
                  : `${String(row.due.days)} days`}
            </span>
          ) : null}
        </span>
        <Why row={row} />
        {row.folded ? (
          <span className="text-[11px] text-ink-3">{COPY.more_rows(row.folded)}</span>
        ) : null}
      </button>
    </li>
  );
}

function CardView({ card }: { card: Card }): JSX.Element {
  const reason = card.unavailable_reason ?? null;
  const summary = (card.summary_blocks ?? []) as unknown as AgentBlocksPayload[];
  return (
    <section aria-label={card.label} className="rounded-[10px] bg-card p-[10px] shadow-e1">
      <p className="text-[12px] font-medium text-ink">{card.label}</p>
      {card.briefing_status === "ready" && summary.length > 0 ? (
        summary.map((doc, i) => <AgentBlocks key={String(i)} blocks={doc} facts={{}} />)
      ) : (
        <p className="text-[12px] text-ink-3">
          {reason !== null
            ? (REASON_COPY[reason] ?? COPY.summaryUnavailable)
            : COPY.summaryUnavailable}
        </p>
      )}
    </section>
  );
}

function GroupBand({
  group,
  onOpen,
}: {
  group: Group;
  onOpen?: ((href: string) => void) | undefined;
}): JSX.Element {
  const [open, setOpen] = useState(group.key === "high_risk");
  const label = GROUP_LABELS[group.key] ?? group.key;
  return (
    <section data-group={group.key} className="border-t border-hair">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
        className="flex h-[32px] w-full items-center gap-[6px] px-[10px] text-left"
      >
        <Icon name={open ? "chevron-down" : "chevron-right"} size={12} />
        <span className="flex-1 text-[12px] font-medium text-ink">{label}</span>
        <span className="text-[12px] text-ink-2 tabular-nums">{group.count}</span>
      </button>
      {open ? (
        <div className="px-[10px] pb-[8px]">
          {group.count === 0 && group.key === "late" ? (
            <p className="text-[12px] text-ink-3">{COPY.nothingLate}</p>
          ) : group.summary ? (
            group.href ? (
              <button
                type="button"
                onClick={() => onOpen?.(group.href ?? "")}
                className="text-left text-[12px] text-ink-2 hover:underline"
              >
                {group.summary}
              </button>
            ) : (
              <p className="text-[12px] text-ink-2">{group.summary}</p>
            )
          ) : null}
          {(group.items ?? []).map((item) => (
            <button
              key={item.ref_id}
              type="button"
              onClick={() => onOpen?.(item.deep_link ?? "")}
              className="mt-[4px] flex w-full flex-col rounded-[8px] bg-card p-[8px] text-left shadow-e1"
            >
              <span className="text-[12px] font-medium text-ink">{item.title}</span>
              {item.detail ? <span className="text-[12px] text-ink-2">{item.detail}</span> : null}
            </button>
          ))}
        </div>
      ) : null}
    </section>
  );
}

export interface TodayPanelProps {
  vm: TodayVm | undefined;
  /** The firm's time zone for the footer's time. */
  timeZone?: string;
  onOpen?: (href: string) => void;
  onHistory?: () => void;
  onRebuild?: () => void;
  onAsk?: (question: string) => void;
  /** The linked highlight (HOME-05 a, d): the HOME-01 rows lit by the hovered or focused row. */
  onHighlight?: (refs: readonly string[] | null) => void;
}

export function TodayPanel({
  vm,
  timeZone = "America/Chicago",
  onOpen,
  onHistory,
  onRebuild,
  onAsk,
  onHighlight,
}: TodayPanelProps): JSX.Element {
  const [question, setQuestion] = useState("");
  if (vm === undefined || vm.status === "building") {
    const c = vm?.building_counts ?? {};
    return (
      <div
        data-screen="SHL-23"
        data-state="building"
        className="flex flex-col gap-[10px] p-[12px]"
      >
        <p className="text-[13px] text-ink-2">
          {COPY.building(c["items"] ?? 0, c["deadlines"] ?? 0, c["runs"] ?? 0)}
        </p>
        <SkeletonRows type="card" immediate label={COPY.title} />
      </div>
    );
  }
  const quiet = vm.items === 0;
  const paragraph = factParagraph(vm);
  const unavailable = !vm.availability.narrative
    ? (REASON_COPY[vm.availability.narrative_reason ?? "boundary_refused"] ?? COPY.aiUnavailable)
    : null;
  return (
    <div data-screen="SHL-23" className="flex min-h-0 flex-1 flex-col">
      <header className="flex h-[46px] flex-none items-center gap-[8px] px-[12px]">
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-[14px] font-medium text-ink">{COPY.greeting(vm.first_name)}</span>
          <span className="text-[11.5px] text-ink-3">{COPY.line(vm.items, vm.engagements)}</span>
        </span>
        <Button variant="ghost" size="sm" onClick={onHistory}>
          {COPY.history}
        </Button>
        <Menu
          label={COPY.more}
          trigger={<Button variant="ghost" size="sm" icon="ellipsis" aria-label={COPY.more} />}
          sections={[[{ label: COPY.rebuild, onSelect: () => onRebuild?.() }]]}
        />
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-[12px] pb-[12px]">
        {unavailable !== null ? (
          <p
            role="note"
            className="mb-[8px] rounded-[8px] bg-amber-tint p-[8px] text-[12px] text-amber-ink"
          >
            {unavailable}
          </p>
        ) : null}
        <section aria-label={COPY.title} className="rounded-[12px] bg-card p-[12px] shadow-e1">
          <div className="flex flex-wrap gap-[6px]">
            {vm.cells.map((cell) => (
              <button
                key={cell.kind}
                type="button"
                data-cell={cell.kind}
                onClick={() => onOpen?.(cell.href)}
                className="flex min-w-[88px] flex-col rounded-[8px] bg-nested px-[10px] py-[6px] text-left"
              >
                <span
                  className={`text-[18px] font-medium tabular-nums ${cell.count === 0 ? "text-ink-4" : "text-ink"}`}
                >
                  {cell.count}
                </span>
                <span className="text-[11px] text-ink-3">
                  {CELL_LABELS[cell.kind] ?? cell.kind}
                </span>
              </button>
            ))}
          </div>
          {paragraph !== "" ? (
            <p data-fact-paragraph className="mt-[8px] text-[13px] text-ink">
              {paragraph}
            </p>
          ) : null}
        </section>
        <h2 className="mt-[12px] text-[12px] font-medium text-ink-3">{COPY.needsYouFirst}</h2>
        {quiet || vm.needs_you_first.length === 0 ? (
          <EmptyState title={COPY.nothingFirst}>{COPY.quietBody}</EmptyState>
        ) : (
          <ul aria-label={COPY.needsYouFirst} className="flex flex-col">
            {vm.needs_you_first.map((row) => (
              <RowLink key={row.gate_id} row={row} onOpen={onOpen} onHover={onHighlight} />
            ))}
          </ul>
        )}
        {vm.layout === "by_engagement" ? (
          <div className="mt-[10px] flex flex-col gap-[8px]">
            {vm.cards.map((card) => (
              <CardView key={card.engagement_id} card={card} />
            ))}
          </div>
        ) : null}
        <div className="mt-[10px]">
          {vm.groups.map((g) => (
            <GroupBand key={g.key} group={g} onOpen={onOpen} />
          ))}
        </div>
      </div>
      {vm.availability.ask ? (
        <form
          className="flex h-[38px] flex-none items-center gap-[6px] border-t border-hair px-[12px]"
          onSubmit={(e) => {
            e.preventDefault();
            if (question.trim() !== "") {
              onAsk?.(question.trim());
              setQuestion("");
            }
          }}
        >
          <input
            aria-label={COPY.ask}
            placeholder={COPY.ask}
            value={question}
            onChange={(e) => {
              setQuestion(e.target.value);
            }}
            className="h-[28px] flex-1 rounded-[7px] bg-card px-[8px] text-[12.5px] shadow-e1"
          />
        </form>
      ) : null}
      {vm.built_at ? (
        <p className="flex-none px-[12px] pb-[8px] text-[11px] text-ink-3">
          {COPY.footer(clockTime(vm.built_at, { tz: timeZone }))}
        </p>
      ) : null}
    </div>
  );
}
