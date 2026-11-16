import type { ConsolidatedTbOut, EliminationOut, GroupTalliesOut } from "@abacus/api-client";
import {
  groupConsolidatedTbOptions,
  groupListEliminationsOptions,
} from "@abacus/api-client/query";
import {
  Amount,
  Button,
  ConsolidationWorksheet,
  EliminationCard,
  EmptyState,
  Icon,
  MatchScope,
  type MatchId,
  Pill,
  Segmented,
  Skeleton,
  TallyStrip,
  type TallyItem,
  cn,
  prose,
} from "@abacus/ui";
import { useQuery } from "@tanstack/react-query";
import { type JSX, useState } from "react";
import { COPY } from "./copy";

// AUD-33 Consolidated trial balance (A-09-T15; SPEC-658; handoff AUD-33): T6 in the Focus layout.
// The level segmented, the tally strip (the server's tallies: no total is summed in the browser),
// the ConsolidationWorksheet with tag chips, the sheet tabs, and the docked Eliminations drawer of
// EliminationCards with its counts and the server's Dr = Cr. A proposed entry is the agent's; a
// Manager approves and posts (Approve is disabled while the server says it is off). Adjustments
// empty state, Locked with Reopen, and the entity tab.

export type Aud33Mode = "posted" | "proposed" | "off" | "adjustments" | "locked" | "entity";

const NAMES: Record<string, string> = {
  holdings: "Holdings",
  operating: "Operating Co.",
  manufacturing: "Manufacturing",
  distribution: "Distribution",
  real_estate: "Real Estate",
  eliminations: "Eliminations",
  consolidated: "Consolidated",
};
const SECTIONS = {
  assets: "Assets",
  liabilities_equity: "Liabilities and equity",
  income: "Income statement · 8 months",
};

const WORDS = {
  ...COPY.card,
  off: (amount: string) => COPY.card.off(prose(amount.replace(/^-/u, ""), "whole")),
};

function matchOf(code: string): MatchId {
  return `elim:${code}` as MatchId;
}

function tallies(t: GroupTalliesOut): TallyItem[] {
  const T = COPY.tallies;
  return [
    { label: T.totalAssets, value: prose(t.total_assets, "whole") },
    { label: T.netIncome, value: prose(t.net_income, "whole") },
    t.balanced === "tie"
      ? {
          label: T.balanced,
          pill: { text: prose(t.total_assets, "whole"), variant: "green-tint", check: true },
        }
      : t.balanced === "off"
        ? {
            label: T.balanced,
            pill: { text: T.off(prose(t.off_by ?? "0", "whole")), variant: "amber" },
          }
        : { label: T.balanced, pill: { text: T.pending, variant: "muted" } },
    t.intercompany === "tie"
      ? { label: T.intercompany, pill: { text: T.afterE4, variant: "green-tint", check: true } }
      : t.intercompany === "off"
        ? {
            label: T.intercompany,
            pill: { text: T.off(prose(t.intercompany_off_by ?? "0", "whole")), variant: "amber" },
          }
        : { label: T.intercompany, pill: { text: T.pending, variant: "muted" } },
    { label: T.eliminations, value: T.posted(t.eliminations_posted) },
    {
      label: T.mapping,
      pill: {
        text: `${String(t.mapped)} of ${String(t.accounts)}`,
        variant: "green-tint",
        check: t.mapped === t.accounts,
      },
    },
  ];
}

function Drawer({
  items,
  proposed,
  totalDebit,
  totalCredit,
  segment,
  onSegment,
  selected,
  onSelect,
}: {
  items: readonly EliminationOut[];
  proposed: boolean;
  totalDebit: string;
  totalCredit: string;
  segment: "eliminations" | "adjustments";
  onSegment: (s: "eliminations" | "adjustments") => void;
  selected: string | null;
  onSelect: (code: string) => void;
}): JSX.Element {
  const D = COPY.drawer;
  const count = (s: string) => items.filter((e) => e.status === s).length;
  return (
    <aside
      aria-label={D.title}
      data-drawer
      className="flex w-[420px] shrink-0 flex-col overflow-hidden rounded-pane bg-card shadow-e1"
    >
      <header className="flex h-[46px] items-center gap-[8px] px-[14px] hairline-b">
        <h2 className="text-[14.5px] font-medium">{D.title}</h2>
        <span className="ml-auto" />
        {proposed && (
          <Button variant="secondary" size="sm">
            {D.approveAll(items.length)}
          </Button>
        )}
        <Button variant="ghost" size="sm">
          {D.export}
        </Button>
        <Button variant="primary" size="sm" aria-label={D.add}>
          <Icon name="plus" size={14} />
        </Button>
      </header>
      <div className="px-[12px] pt-[8px]">
        <Segmented
          size="small"
          label={D.title}
          options={[D.segment.eliminations(items.length), D.segment.adjustments]}
          active={
            segment === "eliminations"
              ? D.segment.eliminations(items.length)
              : D.segment.adjustments
          }
          onChange={(label) => {
            onSegment(label === D.segment.adjustments ? "adjustments" : "eliminations");
          }}
        />
      </div>
      {segment === "adjustments" ? (
        <div data-adjustments-empty className="flex flex-1 items-center justify-center p-[24px]">
          <EmptyState
            title={D.adjustmentsEmpty}
            action={<Button variant="primary">{D.newAdjustment}</Button>}
          />
        </div>
      ) : (
        <>
          <p className="h-[30px] px-[14px] pt-[8px] text-[11.5px] text-ink-3">
            {D.counts(count("proposed"), count("approved"), count("posted"))}
          </p>
          <div className="flex min-h-0 flex-1 flex-col gap-[8px] overflow-auto px-[12px] pb-[12px]">
            {items.map((e) => (
              <EliminationCard
                key={e.id}
                code={e.display_code}
                level={e.consolidation_level}
                description={e.description}
                amount={e.total_debit}
                status={
                  e.status === "posted" || e.status === "approved" || e.status === "proposed"
                    ? e.status
                    : "rejected"
                }
                lines={e.lines}
                computation={e.computation}
                offBy={e.off_by}
                expanded={selected === e.display_code}
                selected={selected === e.display_code}
                onToggle={() => {
                  onSelect(e.display_code);
                }}
                {...(e.status === "proposed"
                  ? {
                      onApprove: () => undefined,
                      onEdit: () => undefined,
                      onReject: () => undefined,
                    }
                  : {})}
                {...(e.display_code === "E3" && e.status === "posted"
                  ? { citations: D.e3Citations, provenance: D.e3Provenance }
                  : {})}
                {...(e.display_code === "E3" && e.status === "proposed"
                  ? { agentNote: D.e3Note }
                  : {})}
                {...(e.display_code === "E4" ? { subline: D.e4Subline } : {})}
                words={WORDS}
              />
            ))}
          </div>
          <footer
            data-drawer-total
            className="flex h-[44px] items-center gap-[8px] px-[14px] text-[12px] shadow-[inset_0_1px_0_var(--color-hair)]"
          >
            <span>
              {D.total} <Amount value={totalDebit} style="whole" /> {D.dr} ={" "}
              <Amount value={totalCredit} style="whole" /> {D.cr}
            </span>
            {totalDebit === totalCredit && (
              <Pill variant="green-tint" check>
                {COPY.tallies.tie}
              </Pill>
            )}
          </footer>
        </>
      )}
    </aside>
  );
}

export interface Aud33Props {
  workItemId: string;
  consolidationId: string;
  level?: 1 | 2;
  mode?: Aud33Mode;
}

export function AUD33({
  workItemId,
  consolidationId,
  level: initialLevel = 1,
  mode = "posted",
}: Aud33Props): JSX.Element {
  const [level, setLevel] = useState<1 | 2>(initialLevel);
  const [segment, setSegment] = useState<"eliminations" | "adjustments">(
    mode === "adjustments" ? "adjustments" : "eliminations",
  );
  const [selected, setSelected] = useState<string | null>("E3");
  const [tab, setTab] = useState(mode === "entity" ? "manufacturing" : "consolidated");
  const tb = useQuery(
    groupConsolidatedTbOptions({
      path: { work_item_id: workItemId, consolidation_id: consolidationId },
      query: { level },
    }),
  );
  const elims = useQuery(
    groupListEliminationsOptions({ path: { consolidation_id: consolidationId } }),
  );
  const data: ConsolidatedTbOut | undefined = tb.data;
  if (data === undefined || elims.data === undefined)
    return <Skeleton className="m-[24px] h-[560px]" />;
  const proposed = elims.data.items.some((e) => e.status === "proposed");
  const locked = mode === "locked";
  const columns =
    tab === "consolidated"
      ? data.columns.map((key) => ({ key, header: NAMES[key] ?? key }))
      : [{ key: tab, header: NAMES[tab] ?? tab }];
  const L = COPY.levels;
  return (
    <MatchScope className="flex h-full flex-col">
      <div data-aud33={mode} data-level={data.level} className="flex h-full flex-col bg-shell">
        <div className="flex h-[44px] items-center gap-[12px] px-[12px]">
          <Segmented
            size="small"
            label={COPY.levelLabel}
            options={[L.one, L.two]}
            active={level === 1 ? L.one : L.two}
            onChange={(label) => {
              setLevel(label === L.two ? 2 : 1);
            }}
          />
          <h1 className="flex-1 text-center text-[14.5px] font-medium">{COPY.title}</h1>
          {locked ? (
            <>
              <Pill variant="soon">
                <Icon name="lock" size={12} /> {COPY.locked}
              </Pill>
              <Button variant="secondary" size="sm">
                {COPY.reopen}
              </Button>
            </>
          ) : (
            <Button variant="ghost" size="sm">
              {COPY.excel}
            </Button>
          )}
        </div>
        <TallyStrip
          label={COPY.tallies.label}
          items={tallies(data.tallies)}
          className="px-[12px]"
        />
        <div className="flex min-h-0 flex-1 gap-[10px] p-[12px]">
          <section
            aria-label={COPY.pane}
            className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-pane bg-card shadow-e1"
          >
            <header className="flex h-[46px] items-center gap-[8px] px-[14px] hairline-b">
              <h2 className="text-[14.5px] font-medium">
                {tab === "consolidated" ? COPY.pane : NAMES[tab]}
              </h2>
              <span className="text-[11.5px] text-ink-3">
                {level === 1 ? COPY.levelOneSub : COPY.levelTwoSub}
              </span>
            </header>
            <div className="min-h-0 flex-1 overflow-auto">
              <ConsolidationWorksheet
                label={COPY.pane}
                columns={columns}
                sections={SECTIONS}
                rows={data.rows.map((r) => ({
                  caption: r.caption,
                  section: r.section,
                  cells: r.cells.map((c) => ({
                    column: c.column,
                    amount: c.amount,
                    codes: c.elimination_codes,
                  })),
                }))}
                matchOf={matchOf}
                onTag={setSelected}
                pending={proposed}
              />
              <p className="px-[14px] py-[8px] text-[11.5px] text-ink-3">
                {level === 1 ? COPY.captionOne : COPY.captionTwo}
              </p>
            </div>
            <nav
              aria-label={COPY.tabs}
              className="flex h-[36px] items-center gap-[2px] bg-nested px-[8px] text-[12.5px] shadow-[inset_0_1px_0_var(--color-hair)]"
            >
              {[
                ...data.columns.filter((c) => c !== "eliminations" && c !== "consolidated"),
                "consolidated",
              ].map((key) => (
                <button
                  key={key}
                  type="button"
                  aria-current={tab === key ? "page" : undefined}
                  onClick={() => {
                    setTab(key);
                  }}
                  className={cn(
                    "h-[28px] rounded-[6px] px-[10px]",
                    tab === key && "bg-card font-medium shadow-e1",
                  )}
                >
                  {NAMES[key] ?? key}
                </button>
              ))}
            </nav>
          </section>
          <Drawer
            items={elims.data.items}
            proposed={proposed && !locked}
            totalDebit={elims.data.total_debit}
            totalCredit={elims.data.total_credit}
            segment={segment}
            onSegment={setSegment}
            selected={selected}
            onSelect={(code) => {
              setSelected((s) => (s === code ? null : code));
            }}
          />
        </div>
      </div>
    </MatchScope>
  );
}
