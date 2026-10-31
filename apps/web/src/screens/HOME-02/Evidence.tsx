import type { HumanGateOut } from "@abacus/api-client";
import { AgentMonogram, AgentText, Button, Pill, Segmented, TallyStrip, cn } from "@abacus/ui";
import { type JSX, useState } from "react";
import { useOpenSourceViewer } from "../../app-core/overlay-host";
import { PLANNED_VISIBLE } from "../../app-core/planned";
import type { EvidenceCell, EvidenceSummary, EvidenceSummaryOf } from "../../domain/home";
import { ViewerPane } from "../SHL-08";
import { COPY } from "./copy";
import { type GateSource, useGateSources } from "./sources";

// HOME-02's evidence pane (I-01-T18; docs/screens/HOME-02.md; I-01 §3 F7, AC7.7), the 576 pane
// beside the review pane. For the selected gate it shows, under a centred title:
//
//   - the owner's evidence summary where one exists: a TallyStrip, the statement table with the row
//     the decision turns on lit in the match purple, the calc card, the agent's proposed fix
//     (AgentText, no control), the preparer memo on its paper, the cited items of a source;
//   - each cited source through the E5 SourceViewer (SHL-08's dock host), opened on the cited
//     region in the match purple, with "Open source ↗" to the SHL-08 drawer;
//   - a small segmented between the summary and the sources that carry a short label.
//
// Tax summaries are fixture-only until T-05 (DV-4): no owner serves one yet, so a live gate shows
// its cited sources. "Open in workpaper ↗" and "Open memo ↗" are planned links (TXP-08, TXP-01),
// shown in fixtures only. HOME-02 computes no figure: the owner's numbers are laid out as given.

export interface EvidencePaneProps {
  gate: HumanGateOut | undefined;
  /** The owner's summary for the gate's subject (fixtures today; DV-4). */
  summaryOf?: EvidenceSummaryOf;
}

interface Segment {
  label: string;
  source: GateSource | null;
}

function segmentsOf(
  summary: EvidenceSummary | undefined,
  sources: readonly GateSource[],
): Segment[] {
  if (summary === undefined) return sources.map((s) => ({ label: s.title, source: s }));
  const labelled = sources.flatMap((s) => {
    const label = summary.sources?.[s.versionId];
    return label === undefined ? [] : [{ label, source: s }];
  });
  return [{ label: summary.segment, source: null }, ...labelled];
}

export function EvidencePane({ gate, summaryOf }: EvidencePaneProps): JSX.Element {
  return gate === undefined ? (
    <Frame title={COPY.evidence} />
  ) : (
    <GateEvidence key={gate.id} gate={gate} {...(summaryOf === undefined ? {} : { summaryOf })} />
  );
}

function GateEvidence({
  gate,
  summaryOf,
}: {
  gate: HumanGateOut;
  summaryOf?: EvidenceSummaryOf;
}): JSX.Element {
  const sources = useGateSources(gate);
  const summary = summaryOf?.(gate.subject.id);
  const segments = segmentsOf(summary, sources);
  const [active, setActive] = useState<string | null>(null);
  const openViewer = useOpenSourceViewer();
  const chosen = segments.find((s) => s.label === active) ?? segments[0];
  if (chosen === undefined) return <Frame title={COPY.evidence} />;
  const source = chosen.source;
  const right =
    source !== null ? (
      <Button
        variant="ghost"
        size="sm"
        iconAfter="arrow-up-right"
        aria-haspopup="dialog"
        onClick={() => {
          openViewer({
            evidenceVersionId: source.versionId,
            matchId: source.matchId,
            engagementId: gate.engagement_id,
          });
        }}
      >
        {COPY.evidencePane.openSource}
      </Button>
    ) : summary?.planned !== undefined && PLANNED_VISIBLE ? (
      // TXP-08 / TXP-01 are later waves: the link is drawn, planned, and goes nowhere yet.
      <span data-planned="" className="text-body text-ink-2">
        {summary.planned}
      </span>
    ) : null;
  return (
    <Frame
      title={source === null ? (summary?.title ?? COPY.evidence) : source.title}
      right={right}
    >
      {segments.length > 1 && (
        <div className="flex h-[50px] flex-none items-center justify-center hairline-b">
          <Segmented
            size="small"
            label={COPY.evidencePane.sources}
            options={segments.map((s) => s.label)}
            active={chosen.label}
            onChange={setActive}
          />
        </div>
      )}
      {source === null && summary !== undefined ? (
        <Summary summary={summary} />
      ) : source !== null ? (
        <ViewerPane
          target={{
            versionId: source.versionId,
            matchId: source.matchId,
            engagementId: gate.engagement_id,
          }}
        />
      ) : null}
    </Frame>
  );
}

function Frame({
  title,
  right,
  children,
}: {
  title: string;
  right?: JSX.Element | null;
  children?: React.ReactNode;
}): JSX.Element {
  return (
    <section
      aria-label={COPY.evidence}
      data-home02="evidence"
      className="pane flex min-h-0 flex-1 flex-col"
    >
      <div className="relative flex h-(--pane-hd-h) flex-none items-center justify-center bg-card hairline-b">
        <h2 className="max-w-[60%] truncate text-pane font-medium tracking-[-0.012em]">{title}</h2>
        {right != null && <span className="absolute right-[14px]">{right}</span>}
      </div>
      <div className="flex min-h-0 flex-1 flex-col overflow-auto">{children}</div>
    </section>
  );
}

// ---- The summary ------------------------------------------------------------------------------

function Cell({ cell, first }: { cell: EvidenceCell; first: boolean }): JSX.Element {
  if (cell.pill !== undefined) {
    return (
      <Pill
        variant={cell.pill.variant}
        size="sm"
        {...(cell.pill.check === true ? { check: true } : {})}
      >
        {cell.text}
      </Pill>
    );
  }
  return (
    <span
      className={cn(
        cell.match === true && "text-match-ink",
        cell.negative === true && "text-red",
        first && "text-body",
      )}
    >
      {cell.text}
    </span>
  );
}

function Summary({ summary }: { summary: EvidenceSummary }): JSX.Element {
  const table = summary.table;
  return (
    <div data-home02="summary" className="flex flex-col">
      {(summary.tally !== undefined || summary.aside !== undefined) && (
        <div className="flex items-center gap-[8px] px-[12px] py-[8px] hairline-b">
          {summary.tally !== undefined && (
            <TallyStrip
              label={summary.title}
              items={summary.tally}
              className="max-w-[420px] flex-1"
            />
          )}
          {summary.aside !== undefined && (
            <Pill variant={summary.aside.variant} size="sm">
              {summary.aside.text}
            </Pill>
          )}
        </div>
      )}
      {table !== undefined && (
        <table aria-label={table.label} className="w-full border-collapse tabular-nums">
          <thead>
            <tr className="h-[30px] bg-band-hd">
              {table.columns.map((c, i) => (
                <th
                  key={c}
                  scope="col"
                  className={cn(
                    "px-[12px] text-th font-medium text-ink-3 hairline-b",
                    i === 0 ? "text-left" : "text-right",
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.rows.map((row, r) => (
              <tr
                // biome-ignore lint/suspicious/noArrayIndexKey: rows are positional (owner's order)
                key={r}
                {...(row.lit === true ? { "data-lit": "" } : {})}
                className={cn(
                  "h-[30px] text-cell",
                  row.lit === true && "bg-match-bg ring-1 ring-match-line ring-inset",
                  row.total === true && "font-medium shadow-[inset_0_0.5px_0_var(--color-stroke)]",
                )}
              >
                {row.cells.map((cell, i) => (
                  <td
                    // biome-ignore lint/suspicious/noArrayIndexKey: cells follow the columns
                    key={i}
                    className={cn("px-[12px] hairline-b", i === 0 ? "text-left" : "text-right")}
                  >
                    <Cell cell={cell} first={i === 0} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {summary.calc !== undefined && (
        <div
          data-home02="calc"
          className="mx-[12px] my-[12px] flex flex-col gap-[4px] rounded-nested bg-shell p-[12px] text-dense leading-[1.6]"
        >
          {summary.calc.lines.map((l) => (
            <p
              key={l.label}
              className={cn(
                "flex justify-between gap-[12px] tabular-nums",
                l.result === true &&
                  "font-medium shadow-[inset_0_0.5px_0_var(--color-hair)] pt-[4px]",
              )}
            >
              <span>{l.label}</span>
              <span
                className={cn(
                  l.result === true &&
                    "rounded-[4px] bg-match-bg px-[4px] text-match-ink ring-1 ring-match-line",
                )}
              >
                {l.value}
              </span>
            </p>
          ))}
          {summary.calc.note !== undefined && (
            <p className="text-meta text-ink-3">{summary.calc.note}</p>
          )}
        </div>
      )}
      {summary.proposal !== undefined && (
        <section
          aria-label={summary.proposal.by}
          className="mx-[12px] my-[12px] flex flex-col gap-[6px] rounded-nested bg-shell p-[16px] shadow-e1"
        >
          <p className="flex items-center gap-[8px] text-body font-medium" data-actor="agent">
            <AgentMonogram size={16} label={COPY.detailPane.agent} />
            {summary.proposal.by}
          </p>
          <AgentText text={summary.proposal.text} className="text-para text-ink-2" />
        </section>
      )}
      {summary.paper !== undefined && (
        <article
          data-home02="paper"
          className="mx-[12px] my-[12px] flex flex-col gap-[10px] bg-card px-[36px] py-[28px] shadow-e1"
        >
          <h3 className="font-legal text-brand leading-[1.3]">{summary.paper.title}</h3>
          <p className="text-meta text-ink-3">{summary.paper.byline}</p>
          {summary.paper.paragraphs.map((p) => (
            <p key={p} className="text-dense leading-[1.55]">
              {p}
            </p>
          ))}
        </article>
      )}
      {summary.cited !== undefined && (
        <section
          aria-label={summary.cited.title}
          className="mx-[12px] my-[12px] flex flex-col gap-[8px] rounded-nested bg-shell p-[16px]"
        >
          <h3 className="text-body font-medium">{summary.cited.title}</h3>
          <ol className="flex flex-col gap-[6px]">
            {summary.cited.items.map((item, i) => (
              <li key={item} className="flex items-center gap-[8px] text-body text-ink-2">
                <span
                  aria-hidden
                  className="flex size-[18px] items-center justify-center rounded-full bg-match-bg text-pill-sm text-match-ink"
                >
                  {i + 1}
                </span>
                {item}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
